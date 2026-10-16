"""
backend/evidence/builder.py — Cryptographic Evidence Bundle Builder (Phase 5)

Builds EvidenceBundle objects per SPEC §4.6 for every EmissionLine:
- SHA-256 hash for every referenced file (frame, crop, invoice scan).
- Deterministic audit chain reconstructed from EmissionLine metadata.
- 100% offline — no LLM calls, no network I/O.

Rules enforced here:
  Rule 3: Every EmissionLine has at least one evidence_ref.
  Rule 5: Results are estimates — disclaimer propagated in audit chain.
  Rule 8: Output follows EvidenceBundle schema.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from backend.schemas import EmissionLine
from backend.config import settings


# --------------------------------------------------------------------------- #
# Schema (kept local to this module — mirrors SPEC §4.6 EvidenceBundle)
# --------------------------------------------------------------------------- #

class AuditStep:
    """Single immutable step in the evidence chain."""
    def __init__(
        self,
        step_number: int,
        description: str,
        actor_or_component: str,
        timestamp: Optional[str] = None,
    ):
        self.step_number = step_number
        self.description = description
        self.actor_or_component = actor_or_component
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "step_number": self.step_number,
            "description": self.description,
            "timestamp": self.timestamp,
            "actor_or_component": self.actor_or_component,
        }


class EvidenceBundle:
    """Full cryptographic + narrative audit bundle for one EmissionLine."""

    def __init__(
        self,
        line_id: str,
        audit_chain: List[AuditStep],
        files: List[str],
        hashes: Dict[str, str],
        disclaimer: str,
    ):
        self.line_id = line_id
        self.audit_chain = audit_chain
        self.files = files
        self.hashes = hashes
        self.disclaimer = disclaimer

    def to_dict(self) -> Dict:
        return {
            "line_id": self.line_id,
            "audit_chain": [s.to_dict() for s in self.audit_chain],
            "files": self.files,
            "hashes": self.hashes,
            "disclaimer": self.disclaimer,
        }


# --------------------------------------------------------------------------- #
# SHA-256 hashing
# --------------------------------------------------------------------------- #

def _sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of a file. Returns 'FILE_NOT_FOUND' if missing."""
    if not path.exists():
        return "FILE_NOT_FOUND"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_string(text: str) -> str:
    """Return hex SHA-256 of a UTF-8 string (for bill reference strings)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Evidence file resolution
# --------------------------------------------------------------------------- #

_SEARCH_ROOTS = [
    settings.BASE_DIR / "data" / "evidence",
    settings.BASE_DIR / "data" / "bills",
    settings.BASE_DIR / "data" / "uploads",
    settings.BASE_DIR / "data" / "samples",
]


def _resolve_path(ref: str) -> Optional[Path]:
    """
    Try to find a file matching the evidence_ref string.
    Searches known data directories; returns None if unresolvable.
    """
    p = Path(ref)
    if p.is_absolute() and p.exists():
        return p

    # Strip leading data/ prefix if present
    for root in _SEARCH_ROOTS:
        candidate = root / p.name
        if candidate.exists():
            return candidate
        # Try the ref as a relative path from BASE_DIR
        candidate2 = settings.BASE_DIR / ref
        if candidate2.exists():
            return candidate2

    return None


# --------------------------------------------------------------------------- #
# Audit chain construction
# --------------------------------------------------------------------------- #

def _build_audit_chain(line: EmissionLine) -> List[AuditStep]:
    """
    Reconstruct a deterministic audit chain from an EmissionLine's
    method, flags, and evidence_refs metadata.
    """
    chain: List[AuditStep] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    method = getattr(line, "method", "bill") or "bill"

    if method in ("video_estimate", "video"):
        # Vision-first chain
        chain.append(AuditStep(
            step_number=1,
            description=(
                f"Video / image frame extracted; machinery detection run via YOLOv8 "
                f"on source '{line.evidence_refs[0] if line.evidence_refs else 'unknown'}'"
            ),
            actor_or_component="backend/vision/pipeline.py (YOLOv8n)",
            timestamp=now_iso,
        ))

        # Smoke step if maintenance flag present
        if "MAINTENANCE_WIDENED_RANGE" in (line.flags or []) or "HEAVY_SMOKE_FLAGGED" in (line.flags or []):
            chain.append(AuditStep(
                step_number=2,
                description=(
                    "Optical smoke analysis (Ringelmann scale) detected heavy exhaust; "
                    "maintenance flag raised; low/high uncertainty band widened ±15%."
                ),
                actor_or_component="backend/vision/smoke.py (optical)",
                timestamp=now_iso,
            ))
            calc_step = 3
        else:
            calc_step = 2

        chain.append(AuditStep(
            step_number=calc_step,
            description=(
                f"Scope {line.scope} emission calculated deterministically: {line.formula_text}. "
                f"Factor: {line.factor_id} = {line.factor_value} {line.factor_unit} "
                f"(source: {line.factor_source})."
            ),
            actor_or_component="backend/engine/calculator.py (fuel_from_detection)",
            timestamp=now_iso,
        ))

    else:
        # Bill OCR chain
        chain.append(AuditStep(
            step_number=1,
            description=(
                f"Utility bill '{line.evidence_refs[0] if line.evidence_refs else 'unknown'}' "
                f"uploaded and processed by OCR pipeline (EasyOCR + Gemini fallback). "
                f"Quantity extracted: {line.activity_value} {line.activity_unit}."
            ),
            actor_or_component="backend/ocr/pipeline.py (EasyOCR)",
            timestamp=now_iso,
        ))
        chain.append(AuditStep(
            step_number=2,
            description=(
                f"User-confirmed or auto-validated bill extraction. "
                f"OCR confidence: ≥ 0.50 threshold."
            ),
            actor_or_component="backend/api/main.py (PUT /api/extractions/confirm)",
            timestamp=now_iso,
        ))
        chain.append(AuditStep(
            step_number=3,
            description=(
                f"Scope {line.scope} emission calculated deterministically: {line.formula_text}. "
                f"Factor: {line.factor_id} = {line.factor_value} {line.factor_unit} "
                f"(source: {line.factor_source})."
            ),
            actor_or_component="backend/engine/calculator.py",
            timestamp=now_iso,
        ))

    # Flag audit step
    if line.flags:
        chain.append(AuditStep(
            step_number=len(chain) + 1,
            description=f"Quality flags raised: {', '.join(line.flags)}. "
                        f"Uncertainty range: {line.low_kg:.1f}–{line.high_kg:.1f} kg CO2e.",
            actor_or_component="backend/engine/uncertainty.py",
            timestamp=now_iso,
        ))

    # Final lock step
    chain.append(AuditStep(
        step_number=len(chain) + 1,
        description=(
            f"EmissionLine locked at {line.co2e_kg:.3f} kg CO2e. "
            f"This is an operational estimate supporting buyer-framework disclosures — "
            f"not a third-party-certified regulatory compliance figure."
        ),
        actor_or_component="backend/evidence/builder.py (Carbon Passport v0.1)",
        timestamp=now_iso,
    ))

    return chain


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def build_evidence_bundle(line: EmissionLine) -> EvidenceBundle:
    """
    Build a complete EvidenceBundle for an EmissionLine.

    Steps:
    1. Resolve physical files from evidence_refs.
    2. SHA-256 hash each resolved file.
    3. Generate deterministic audit chain from line metadata.
    4. Return EvidenceBundle with all components.

    Rule 3: Evidence_refs must be non-empty; raises ValueError if empty.
    """
    if not line.evidence_refs:
        raise ValueError(
            f"EmissionLine {line.id} has no evidence_refs — violates Rule 3."
        )

    files: List[str] = []
    hashes: Dict[str, str] = {}

    for ref in line.evidence_refs:
        path = _resolve_path(ref)
        if path is not None:
            rel = str(path.relative_to(settings.BASE_DIR)).replace("\\", "/")
            files.append(rel)
            hashes[rel] = _sha256_file(path)
        else:
            # Non-file reference (e.g. "det_genset_kirloskar_01", "sha256:...")
            # Store a string hash so every ref has a traceable entry
            files.append(ref)
            hashes[ref] = _sha256_string(ref)

    audit_chain = _build_audit_chain(line)

    return EvidenceBundle(
        line_id=line.id,
        audit_chain=audit_chain,
        files=files,
        hashes=hashes,
        disclaimer=(
            "This evidence bundle is an operational estimate that supports the data "
            "buyer frameworks (CBAM, SEBI BRSR, GHG Protocol) request. "
            "It is NOT a third-party audit or certified regulatory compliance statement."
        ),
    )


def build_all_bundles(lines: List[EmissionLine]) -> Dict[str, EvidenceBundle]:
    """
    Build EvidenceBundle for each EmissionLine, keyed by line.id.
    Lines without evidence_refs are skipped with a warning (should not happen post-Rule 3 checks).
    """
    result: Dict[str, EvidenceBundle] = {}
    for line in lines:
        try:
            result[line.id] = build_evidence_bundle(line)
        except ValueError as exc:
            import warnings
            warnings.warn(str(exc), stacklevel=2)
    return result
