"""
OCR pipeline orchestrator.

Full flow:
  1. Preprocess image (grayscale, deskew, denoise, threshold)
  2. Run EasyOCR (en + hi)
  3. Parse fields (regex + keyword proximity)
  4. Check confidence thresholds (from ocr/config.py)
  5. If below threshold or fields missing → Gemini fallback
  6. Merge and return a BillExtraction (user_confirmed=False always)
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.schemas import BillExtraction
from backend.ocr.preprocess import preprocess_for_ocr
from backend.ocr.reader import run_ocr
from backend.ocr.parser import parse_ocr_results, ParseResult
from backend.ocr.fallback import gemini_fallback_extract
from backend.ocr import config as ocr_cfg

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Evidence storage helpers
# --------------------------------------------------------------------------- #

_BILLS_EVIDENCE_DIR = settings.DATA_DIR / "evidence" / "bills"


def _save_evidence(original_bytes: bytes, source_name: str) -> str:
    """Save original bill bytes to evidence dir, return relative path."""
    _BILLS_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(source_name).stem
    target = _BILLS_EVIDENCE_DIR / f"{stem}_original.jpg"
    with open(target, "wb") as f:
        f.write(original_bytes)
    return str(target.relative_to(settings.BASE_DIR)).replace("\\", "/")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- #
#  Merge helpers
# --------------------------------------------------------------------------- #

def _merge_fallback(
    parsed: ParseResult,
    fb: Dict[str, Any],
) -> ParseResult:
    """Fill missing fields in ParseResult from Gemini fallback dict."""

    def _try_float(v):
        try:
            return float(str(v).replace(",", ""))
        except Exception:
            return None

    if not parsed.bill_type and fb.get("bill_type"):
        parsed.bill_type = str(fb["bill_type"]).lower()
        parsed.bill_type_conf = float(fb.get("confidence_0_1", 0.5))
        parsed.per_field_conf["bill_type"] = parsed.bill_type_conf

    if not parsed.period_start and fb.get("period_start"):
        parsed.period_start = str(fb["period_start"])
        parsed.per_field_conf["period_start"] = 0.75

    if not parsed.period_end and fb.get("period_end"):
        parsed.period_end = str(fb["period_end"])
        parsed.per_field_conf["period_end"] = 0.75

    if not parsed.quantity and fb.get("quantity"):
        q = _try_float(fb["quantity"])
        if q is not None:
            parsed.quantity = q
            parsed.per_field_conf["quantity"] = 0.75

    if not parsed.unit and fb.get("unit"):
        parsed.unit = str(fb["unit"])
        parsed.per_field_conf["unit"] = 0.75

    if not parsed.amount_inr and fb.get("amount_inr"):
        a = _try_float(fb["amount_inr"])
        if a is not None:
            parsed.amount_inr = a
            parsed.per_field_conf["amount_inr"] = 0.75

    if not parsed.supplier and fb.get("supplier"):
        parsed.supplier = str(fb["supplier"])
        parsed.per_field_conf["supplier"] = 0.75

    # Recalculate overall confidence
    confs = list(parsed.per_field_conf.values())
    parsed.overall_confidence = round(sum(confs) / len(confs), 3) if confs else 0.0
    return parsed


def _should_trigger_fallback(parsed: ParseResult) -> bool:
    """Return True if any required field is missing or confidence is low."""
    missing = ocr_cfg.REQUIRED_FIELDS - set(
        k for k, v in {
            "bill_type": parsed.bill_type,
            "period_start": parsed.period_start,
            "period_end": parsed.period_end,
            "quantity": parsed.quantity,
            "unit": parsed.unit,
            "amount_inr": parsed.amount_inr,
            "supplier": parsed.supplier,
        }.items()
        if v is not None
    )
    if missing:
        logger.info(f"Missing fields: {missing} – triggering fallback")
        return True
    if parsed.overall_confidence < ocr_cfg.OVERALL_CONFIDENCE_THRESHOLD:
        logger.info(f"Low overall confidence {parsed.overall_confidence:.2f} – triggering fallback")
        return True
    return False


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #

def extract_bill(
    image_path: str,
    bill_id: Optional[str] = None,
) -> BillExtraction:
    """
    Full OCR pipeline. Returns a BillExtraction with user_confirmed=False.
    Never raises – on catastrophic failure returns a low-confidence placeholder.
    """
    path = Path(image_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Bill image not found: {image_path}")

    source_name = path.name
    det_id = bill_id or f"bill_{Path(source_name).stem}_{uuid.uuid4().hex[:8]}"

    try:
        # ── Step 1: Preprocess ──────────────────────────────────────────── #
        preprocessed_img, original_bytes = preprocess_for_ocr(str(path))
        evidence_path = _save_evidence(original_bytes, source_name)

        # ── Step 2: EasyOCR ─────────────────────────────────────────────── #
        ocr_results = run_ocr(preprocessed_img)
        logger.info(f"[{source_name}] EasyOCR returned {len(ocr_results)} tokens")

        # ── Step 3: Parse ───────────────────────────────────────────────── #
        parsed = parse_ocr_results(ocr_results)

        # ── Steps 4-5: Confidence gate + fallback ───────────────────────── #
        method = "ocr"
        if _should_trigger_fallback(parsed):
            logger.info(f"[{source_name}] Calling Gemini fallback…")
            fb_data = gemini_fallback_extract(str(path))
            if fb_data:
                parsed = _merge_fallback(parsed, fb_data)
                method = "gemini_fallback"

        # ── Step 6: Build BillExtraction (user_confirmed=False always) ─── #
        return _build_extraction(
            det_id=det_id,
            source_name=source_name,
            parsed=parsed,
            method=method,
            evidence_path=evidence_path,
            original_bytes=original_bytes,
        )

    except Exception as exc:
        logger.error(f"OCR pipeline failed for {source_name}: {exc}", exc_info=True)
        return _fallback_placeholder(det_id, source_name)


def _build_extraction(
    det_id: str,
    source_name: str,
    parsed: ParseResult,
    method: str,
    evidence_path: str,
    original_bytes: bytes,
) -> BillExtraction:
    """Construct a BillExtraction from parsed fields. Handles None gracefully."""

    bill_type = parsed.bill_type or "electricity"
    period_start = parsed.period_start or "1970-01-01"
    period_end = parsed.period_end or period_start
    quantity = parsed.quantity or 0.0
    unit = parsed.unit or "kWh"
    amount_inr = parsed.amount_inr or 0.0
    supplier = parsed.supplier or "UNKNOWN"

    field_boxes = dict(parsed.field_boxes)
    field_boxes["_evidence_path"] = evidence_path
    field_boxes["_sha256"] = _sha256(original_bytes)

    return BillExtraction(
        id=det_id,
        source_file=source_name,
        bill_type=bill_type,   # type: ignore[arg-type]
        period_start=period_start,
        period_end=period_end,
        quantity=quantity,
        unit=unit,
        amount_inr=amount_inr,
        supplier=supplier,
        confidence_0_1=round(parsed.overall_confidence, 3),
        field_boxes=field_boxes,
        method=method,        # type: ignore[arg-type]
        user_confirmed=False,  # INVARIANT: never auto-confirm
    )


def _fallback_placeholder(bill_id: str, source_name: str) -> BillExtraction:
    """Return a zero-value placeholder on catastrophic pipeline failure."""
    return BillExtraction(
        id=bill_id,
        source_file=source_name,
        bill_type="electricity",
        period_start="1970-01-01",
        period_end="1970-01-01",
        quantity=0.0,
        unit="kWh",
        amount_inr=0.0,
        supplier="PARSE_FAILED",
        confidence_0_1=0.0,
        field_boxes={"_error": "pipeline_failed"},
        method="ocr",
        user_confirmed=False,
    )
