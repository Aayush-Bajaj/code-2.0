"""
tests/test_evidence.py — Tests for backend/evidence/builder.py (Phase 5)

Verifies:
- SHA-256 hashes generated correctly for real and synthetic files
- Audit chains constructed deterministically per EmissionLine method
- Rule 3: ValueError raised when evidence_refs is empty
- EvidenceBundle.to_dict() schema matches SPEC §4.6
- GET /api/evidence/{line_id} returns 404 before calculate, 200 after
"""

import hashlib
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.evidence.builder import (
    EvidenceBundle,
    _sha256_file,
    _sha256_string,
    build_evidence_bundle,
    build_all_bundles,
)
from backend.schemas import EmissionLine


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def make_line(
    line_id: str = "em_test_01",
    method: str = "bill",
    scope: int = 2,
    flags: list = None,
    evidence_refs: list = None,
) -> EmissionLine:
    return EmissionLine(
        id=line_id,
        scope=scope,
        category="Test Electricity",
        activity_value=1000.0,
        activity_unit="kWh",
        factor_id="grid_india_wa",
        factor_value=0.716,
        factor_unit="kg CO2e/kWh",
        factor_source="CEA v22",
        factor_url="https://cea.nic.in",
        formula_text="1000.0 kWh x 0.716 = 716.0 kg",
        co2e_kg=716.0,
        low_kg=680.2,
        high_kg=751.8,
        evidence_refs=evidence_refs if evidence_refs is not None else ["bill_test.pdf"],
        method=method,
        flags=flags or [],
    )


# --------------------------------------------------------------------------- #
# SHA-256 tests
# --------------------------------------------------------------------------- #

def test_sha256_file_on_real_file():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"%PDF test content for hashing")
        tmp = Path(f.name)
    try:
        digest = _sha256_file(tmp)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)
        # Deterministic — same file hashes same every time
        assert _sha256_file(tmp) == digest
    finally:
        tmp.unlink()


def test_sha256_file_missing_returns_marker():
    result = _sha256_file(Path("/nonexistent/path/file.pdf"))
    assert result == "FILE_NOT_FOUND"


def test_sha256_string_deterministic():
    s = "det_genset_kirloskar_01"
    d1 = _sha256_string(s)
    d2 = _sha256_string(s)
    assert d1 == d2
    assert len(d1) == 64


def test_sha256_string_different_inputs():
    assert _sha256_string("abc") != _sha256_string("xyz")


# --------------------------------------------------------------------------- #
# EvidenceBundle construction
# --------------------------------------------------------------------------- #

def test_build_bundle_bill_method():
    line = make_line(method="bill", evidence_refs=["bescom_march_2024.pdf"])
    bundle = build_evidence_bundle(line)

    assert bundle.line_id == "em_test_01"
    assert len(bundle.audit_chain) >= 3  # at least: OCR, confirm, calc, lock
    assert bundle.files == ["bescom_march_2024.pdf"]
    assert "bescom_march_2024.pdf" in bundle.hashes
    assert "disclaimer" in bundle.to_dict()
    assert "NOT a third-party" in bundle.disclaimer


def test_build_bundle_video_method():
    line = make_line(
        method="video_estimate",
        scope=1,
        evidence_refs=["det_genset_kirloskar_01"],
    )
    bundle = build_evidence_bundle(line)
    assert bundle.line_id == "em_test_01"
    # Chain has: video detect + calc + lock = 3 min steps
    assert len(bundle.audit_chain) >= 3
    steps_text = " ".join(s.description for s in bundle.audit_chain)
    assert "YOLOv8" in steps_text or "video" in steps_text.lower()


def test_build_bundle_video_with_smoke_flags():
    line = make_line(
        method="video_estimate",
        scope=1,
        flags=["MAINTENANCE_WIDENED_RANGE", "HEAVY_SMOKE_FLAGGED"],
        evidence_refs=["vid_exhaust_smoke_01"],
    )
    bundle = build_evidence_bundle(line)
    steps_text = " ".join(s.description for s in bundle.audit_chain)
    assert "smoke" in steps_text.lower() or "maintenance" in steps_text.lower()


def test_build_bundle_empty_refs_raises():
    """Rule 3: EmissionLine schema enforces min 1 evidence_ref at validation time."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="too_short|at least 1"):
        EmissionLine(
            id="em_bad",
            scope=2,
            category="Test",
            activity_value=100.0,
            activity_unit="kWh",
            factor_id="grid_india_wa",
            factor_value=0.716,
            factor_unit="kg CO2e/kWh",
            factor_source="CEA",
            factor_url="https://cea.nic.in",
            formula_text="100 x 0.716 = 71.6",
            co2e_kg=71.6,
            low_kg=68.0,
            high_kg=75.2,
            evidence_refs=[],  # Must be blocked by schema
            method="bill",
            flags=[],
        )


def test_build_all_bundles():
    lines = [
        make_line("em_elec_01", method="bill", scope=2, evidence_refs=["bill_e.pdf"]),
        make_line("em_diesel_01", method="bill", scope=1, evidence_refs=["bill_d.pdf"]),
    ]
    bundles = build_all_bundles(lines)
    assert "em_elec_01" in bundles
    assert "em_diesel_01" in bundles
    assert bundles["em_elec_01"].line_id == "em_elec_01"


def test_bundle_to_dict_schema():
    line = make_line(evidence_refs=["invoice_01.pdf"])
    bundle = build_evidence_bundle(line)
    d = bundle.to_dict()

    assert "line_id" in d
    assert "audit_chain" in d
    assert "files" in d
    assert "hashes" in d
    assert "disclaimer" in d

    chain = d["audit_chain"]
    assert isinstance(chain, list)
    assert len(chain) >= 1
    step = chain[0]
    assert "step_number" in step
    assert "description" in step
    assert "timestamp" in step
    assert "actor_or_component" in step


def test_audit_chain_step_numbers_sequential():
    line = make_line(evidence_refs=["bill.pdf"])
    bundle = build_evidence_bundle(line)
    for i, step in enumerate(bundle.audit_chain, start=1):
        assert step.step_number == i


def test_lock_step_always_last():
    """The last audit step should always contain the final locked CO2e value."""
    line = make_line(evidence_refs=["bill.pdf"])
    bundle = build_evidence_bundle(line)
    last = bundle.audit_chain[-1]
    assert "716.0" in last.description or "716" in last.description
    assert "estimate" in last.description.lower()


# --------------------------------------------------------------------------- #
# API endpoint tests
# --------------------------------------------------------------------------- #

def test_evidence_endpoint_404_before_calculate():
    """Before any /api/calculate call the evidence cache is empty."""
    from backend.api.main import app
    client = TestClient(app)
    resp = client.get("/api/evidence/em_nonexistent_line")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_evidence_endpoint_200_after_calculate():
    """After /api/calculate, the evidence endpoint should return a bundle."""
    from backend.api.main import app
    client = TestClient(app)

    calc_payload = {
        "bills": [
            {
                "id": "b_ev_test",
                "source_file": "electric_bill.pdf",
                "bill_type": "electricity",
                "period_start": "2024-03-01",
                "period_end": "2024-03-31",
                "quantity": 5000.0,
                "unit": "kWh",
                "amount_inr": 42000.0,
                "supplier": "MSEDCL",
                "confidence_0_1": 0.95,
                "field_boxes": {},
                "method": "ocr",
            }
        ],
        "gensets": [],
    }
    calc_resp = client.post("/api/calculate", json=calc_payload)
    assert calc_resp.status_code == 200, calc_resp.text

    lines = calc_resp.json()["emission_lines"]
    assert len(lines) == 1
    line_id = lines[0]["id"]

    ev_resp = client.get(f"/api/evidence/{line_id}")
    assert ev_resp.status_code == 200, ev_resp.text

    bundle = ev_resp.json()
    assert bundle["line_id"] == line_id
    assert len(bundle["audit_chain"]) >= 3
    assert len(bundle["files"]) >= 1
    assert bundle["hashes"]
    assert "NOT a third-party" in bundle["disclaimer"]
