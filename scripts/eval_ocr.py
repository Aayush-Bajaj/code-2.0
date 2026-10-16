#!/usr/bin/env python3
"""
OCR Evaluation Script — Carbon Passport.

Runs the OCR pipeline on every bill in data/bills/ and compares to ground_truth.json.
Reports per-field accuracy split by clean (is_scanned_artifact=false) vs
degraded/scanned (is_scanned_artifact=true) bills, plus all failing cases.

Usage:
    py scripts/eval_ocr.py                  # live OCR + LLM fallback
    py scripts/eval_ocr.py --mock-llm       # mock LLM, real OCR
    py scripts/eval_ocr.py --no-ocr         # skip real OCR, use LLM fallback only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import settings
from backend.ocr.pipeline import extract_bill

BILLS_DIR = BASE_DIR / "data" / "bills"
GT_FILE = BASE_DIR / "data" / "bills" / "ground_truth.json"

# Fields we score
SCORED_FIELDS = ["bill_type", "period_start", "period_end", "quantity", "unit", "amount_inr", "supplier"]


# ─────────────────────────────────────────────────────────────────────────── #
#  Field-level comparison
# ─────────────────────────────────────────────────────────────────────────── #

def _norm_date(v: Optional[str]) -> Optional[str]:
    """Normalise dd/mm/yyyy → yyyy-mm-dd for comparison."""
    if not v:
        return None
    v = str(v).strip()
    # dd/mm/yyyy or dd-mm-yyyy
    import re
    m = re.match(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", v)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return v


def _norm_supplier(v: Optional[str]) -> str:
    if not v:
        return ""
    import re
    return re.sub(r"[^a-z0-9]", "", str(v).lower())


def _norm_float(v: Any) -> Optional[float]:
    try:
        return round(float(str(v).replace(",", "")), 2)
    except Exception:
        return None


def _compare_field(field: str, pred: Any, gt: Any) -> Tuple[bool, str]:
    """Returns (match, note)."""
    if pred is None:
        return False, f"missing (gt={gt})"
    if field in ("period_start", "period_end"):
        p = _norm_date(str(pred))
        g = _norm_date(str(gt))
        ok = p == g
        return ok, "" if ok else f"pred={p} gt={g}"
    if field == "supplier":
        p = _norm_supplier(pred)
        g = _norm_supplier(gt)
        # partial match: pred in gt or gt in pred
        ok = p in g or g in p or (len(p) > 6 and p[:8] in g)
        return ok, "" if ok else f"pred='{pred}' gt='{gt}'"
    if field in ("quantity", "amount_inr"):
        pf = _norm_float(pred)
        gf = _norm_float(gt)
        if pf is None or gf is None:
            return False, f"unparseable pred={pred} gt={gt}"
        # Allow 2% tolerance
        tol = abs(gf) * 0.02 + 0.5
        ok = abs(pf - gf) <= tol
        return ok, "" if ok else f"pred={pf} gt={gf} diff={abs(pf-gf):.2f}"
    if field == "unit":
        def _u(x):
            return str(x).lower().replace("-", "").replace(" ", "")
        ok = _u(pred) == _u(gt)
        return ok, "" if ok else f"pred={pred} gt={gt}"
    ok = str(pred).strip().lower() == str(gt).strip().lower()
    return ok, "" if ok else f"pred={pred} gt={gt}"


# ─────────────────────────────────────────────────────────────────────────── #
#  Main evaluation
# ─────────────────────────────────────────────────────────────────────────── #

def run_eval(mock_llm: bool = False) -> None:
    if mock_llm:
        settings.MOCK_LLM = True

    if not GT_FILE.exists():
        print(f"[ERROR] Ground truth file not found: {GT_FILE}")
        sys.exit(1)

    with open(GT_FILE, encoding="utf-8") as f:
        ground_truth: Dict[str, Dict] = json.load(f)

    bill_files = sorted(BILLS_DIR.glob("bill_*.png"))
    if not bill_files:
        print("[ERROR] No bill_*.png files found in", BILLS_DIR)
        sys.exit(1)

    # Accumulators
    results_clean: Dict[str, List[bool]] = {f: [] for f in SCORED_FIELDS}
    results_scanned: Dict[str, List[bool]] = {f: [] for f in SCORED_FIELDS}
    failures: List[Tuple[str, str, str]] = []  # (filename, field, note)

    col = [30, 12, 12, 12, 20]
    header = (f"{'Filename':<{col[0]}} {'bill_type':<{col[1]}} "
              f"{'quantity':<{col[2]}} {'amount':<{col[3]}} "
              f"{'Conf':<{col[4]}} Method")
    print("\n" + "=" * 100)
    print("  CARBON PASSPORT — OCR BILL EXTRACTION EVALUATION")
    print("=" * 100)
    print(header)
    print("-" * 100)

    for bill_path in bill_files:
        fname = bill_path.name
        gt = ground_truth.get(fname)
        if gt is None:
            print(f"  {fname:<{col[0]}} [no ground truth — skip]")
            continue

        is_scanned = bool(gt.get("is_scanned_artifact", False))
        acc = results_scanned if is_scanned else results_clean

        try:
            extraction = extract_bill(str(bill_path))
        except Exception as exc:
            print(f"  {fname:<{col[0]}} [PIPELINE ERROR: {exc}]")
            for f in SCORED_FIELDS:
                acc[f].append(False)
                failures.append((fname, f, f"exception: {exc}"))
            continue

        pred_map = {
            "bill_type": extraction.bill_type,
            "period_start": extraction.period_start,
            "period_end": extraction.period_end,
            "quantity": extraction.quantity,
            "unit": extraction.unit,
            "amount_inr": extraction.amount_inr,
            "supplier": extraction.supplier,
        }

        for field in SCORED_FIELDS:
            gt_val = gt.get(field)
            pred_val = pred_map.get(field)
            ok, note = _compare_field(field, pred_val, gt_val)
            acc[field].append(ok)
            if not ok:
                failures.append((fname, field, note))

        # Invariant check: user_confirmed must always be False
        if extraction.user_confirmed:
            failures.append((fname, "user_confirmed", "BUG: auto-confirmed!"))

        tag = "SCAN" if is_scanned else "CLEN"
        print(
            f"  {fname:<{col[0]}} "
            f"{str(extraction.bill_type):<{col[1]}} "
            f"{str(extraction.quantity):<{col[2]}} "
            f"{str(extraction.amount_inr):<{col[3]}} "
            f"{extraction.confidence_0_1:<{col[4]}.2f} "
            f"[{tag}] {extraction.method}"
        )

    print("\n" + "=" * 100)
    print("  PER-FIELD ACCURACY")
    print("=" * 100)
    header2 = f"{'Field':<18} {'Clean':>8} {'Scanned':>8} {'Overall':>8}"
    print(header2)
    print("-" * 44)

    for field in SCORED_FIELDS:
        c_list = results_clean[field]
        s_list = results_scanned[field]
        c_acc = (sum(c_list) / len(c_list) * 100) if c_list else float("nan")
        s_acc = (sum(s_list) / len(s_list) * 100) if s_list else float("nan")
        all_list = c_list + s_list
        o_acc = (sum(all_list) / len(all_list) * 100) if all_list else float("nan")
        flag = " [!]" if o_acc < 90 else ""
        print(f"  {field:<16} {c_acc:>7.1f}% {s_acc:>7.1f}% {o_acc:>7.1f}%{flag}")

    if failures:
        print("\n" + "=" * 100)
        print(f"  FAILURES ({len(failures)} total)")
        print("=" * 100)
        for fname, field, note in failures:
            print(f"  [{fname}] {field}: {note}")
    else:
        print("\n  All fields matched ground truth!")

    print()


def main():
    parser = argparse.ArgumentParser(description="Evaluate Carbon Passport OCR pipeline on bill images.")
    parser.add_argument("--mock-llm", action="store_true", help="Enable MOCK_LLM for fallback calls")
    args = parser.parse_args()
    run_eval(mock_llm=args.mock_llm)


if __name__ == "__main__":
    main()
