"""
Unit and integration tests for backend/ocr.
All tests run without EasyOCR or live Gemini (mocked).
Covers:
1. Indian number format parsing
2. Date format parsing (dd/mm/yyyy, dd-mm-yyyy, ISO)
3. Unit normalisation (MWh→kWh, ltr→L, tkm→tonne-km)
4. OCR character confusion fixes (O→0, l→1, S→5)
5. Fallback trigger (missing fields / low confidence)
6. user_confirmed is always False
7. Sanity check flags (negative, absurdly large)
8. Supplier extraction
9. Bill type detection
10. Full pipeline with mocked OCR
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.ocr.parser import (
    ParseResult,
    _parse_date,
    _parse_indian_number,
    _fix_ocr_numeric,
    _normalise_unit,
    _sanity_check,
    parse_ocr_results,
    _detect_bill_type,
)
from backend.ocr.pipeline import (
    extract_bill,
    _should_trigger_fallback,
    _merge_fallback,
)


# ─────────────────────────────────────────────────────────────────────────── #
#  1. Indian number formats
# ─────────────────────────────────────────────────────────────────────────── #

@pytest.mark.parametrize("raw, expected", [
    ("1,23,456.78", 123456.78),
    ("13,343.80",   13343.80),
    ("662.83",       662.83),
    ("1,00,000",   100000.0),
    ("  84.5 ",      84.5),
    ("0",             0.0),
])
def test_indian_number_format(raw, expected):
    result = _parse_indian_number(raw)
    assert result is not None
    assert abs(result - expected) < 0.01


# ─────────────────────────────────────────────────────────────────────────── #
#  2. Date formats
# ─────────────────────────────────────────────────────────────────────────── #

@pytest.mark.parametrize("raw, expected_iso", [
    ("01/01/2024", "2024-01-01"),
    ("28/02/2024", "2024-02-28"),
    ("09-01-2024", "2024-01-09"),
    ("03.04.2024", "2024-04-03"),
    ("2024-05-22", "2024-05-22"),
    ("2024/07/15", "2024-07-15"),
])
def test_date_formats(raw, expected_iso):
    assert _parse_date(raw) == expected_iso


def test_invalid_date_returns_none():
    assert _parse_date("not-a-date") is None
    assert _parse_date("") is None


# ─────────────────────────────────────────────────────────────────────────── #
#  3. Unit normalisation
# ─────────────────────────────────────────────────────────────────────────── #

@pytest.mark.parametrize("raw_unit, qty_in, expected_unit, expected_qty", [
    ("MWh",      5.0,    "kWh",      5000.0),
    ("mwh",      1.5,    "kWh",      1500.0),
    ("kwh",      100.0,  "kWh",      100.0),
    ("kWh",      200.0,  "kWh",      200.0),
    ("units",    300.0,  "kWh",      300.0),
    ("litres",   662.83, "L",        662.83),
    ("ltr",      200.0,  "L",        200.0),
    ("Ltrs",     50.0,   "L",        50.0),
    ("L",        100.0,  "L",        100.0),
    ("tkm",      5633.4, "tonne-km", 5633.4),
    ("t-km",     100.0,  "tonne-km", 100.0),
    ("tonne-km", 800.0,  "tonne-km", 800.0),
    ("kg",       9000.0, "kg",       9000.0),
    ("kgs",      1234.0, "kg",       1234.0),
])
def test_unit_normalisation(raw_unit, qty_in, expected_unit, expected_qty):
    unit, qty = _normalise_unit(raw_unit, qty_in)
    assert unit == expected_unit
    assert abs(qty - expected_qty) < 0.01


# ─────────────────────────────────────────────────────────────────────────── #
#  4. OCR char confusion fixes
# ─────────────────────────────────────────────────────────────────────────── #

@pytest.mark.parametrize("raw, expected", [
    ("l3,343.8O",  "13,343.80"),
    ("S62.83",     "562.83"),
    ("1O9,lS2.28", "109,152.28"),
])
def test_ocr_numeric_fix(raw, expected):
    assert _fix_ocr_numeric(raw) == expected


# ─────────────────────────────────────────────────────────────────────────── #
#  5. Bill type detection
# ─────────────────────────────────────────────────────────────────────────── #

def test_detect_electricity():
    text = "Maharashtra State Electricity Distribution  Units consumed: 13343 kWh"
    bt, conf = _detect_bill_type(text)
    assert bt == "electricity"

def test_detect_diesel():
    text = "Indian Oil Corporation diesel fuel litres 662.83 HSD"
    bt, conf = _detect_bill_type(text)
    assert bt == "diesel"

def test_detect_freight():
    text = "VRL Logistics freight tkm consignment cargo dispatch"
    bt, conf = _detect_bill_type(text)
    assert bt == "freight"


# ─────────────────────────────────────────────────────────────────────────── #
#  6. Sanity checks
# ─────────────────────────────────────────────────────────────────────────── #

def test_sanity_negative():
    flag = _sanity_check("electricity", -10.0, "kWh")
    assert flag is not None and "Negative" in flag

def test_sanity_absurdly_large_electricity():
    flag = _sanity_check("electricity", 2_000_000, "kWh")
    assert flag is not None

def test_sanity_valid_passes():
    assert _sanity_check("electricity", 5000, "kWh") is None
    assert _sanity_check("diesel", 500, "L") is None
    assert _sanity_check("freight", 5000, "tonne-km") is None


# ─────────────────────────────────────────────────────────────────────────── #
#  7. Parse from OCR results
# ─────────────────────────────────────────────────────────────────────────── #

def _make_ocr(text, conf=0.90, x=0, y=0, w=100, h=20):
    """Helper to create a single OCR result tuple."""
    return (text, [[x, y], [x+w, y], [x+w, y+h], [x, y+h]], conf)


def test_parse_electricity_bill():
    ocr = [
        _make_ocr("Maharashtra State Electricity Distribution Co. Ltd.", 0.92),
        _make_ocr("Bill Period: 01/01/2024 to 28/01/2024", 0.89),
        _make_ocr("Units consumed 13,343.80 kWh", 0.91),
        _make_ocr("Total Amount Rs. 1,09,152.28", 0.88),
    ]
    result = parse_ocr_results(ocr)
    assert result.bill_type == "electricity"
    assert result.period_start == "2024-01-01"
    assert result.period_end == "2024-01-28"
    assert result.quantity is not None and abs(result.quantity - 13343.80) < 1
    assert result.unit == "kWh"
    assert result.amount_inr is not None and abs(result.amount_inr - 109152.28) < 1


def test_parse_diesel_bill():
    ocr = [
        _make_ocr("Indian Oil Corporation Fuel Point Pune", 0.92),
        _make_ocr("Date: 09/01/2024", 0.85),
        _make_ocr("Quantity: 662.83 Litres", 0.88),
        _make_ocr("Total: Rs. 60,529.64", 0.87),
    ]
    result = parse_ocr_results(ocr)
    assert result.bill_type == "diesel"
    assert result.quantity is not None and abs(result.quantity - 662.83) < 0.1
    assert result.unit == "L"
    assert result.amount_inr is not None and abs(result.amount_inr - 60529.64) < 1


def test_parse_freight_bill():
    ocr = [
        _make_ocr("VRL Logistics Freight Invoice", 0.90),
        _make_ocr("Date: 15/07/2024", 0.85),
        _make_ocr("5,633.40 tkm transported", 0.88),
        _make_ocr("Net Payable: 29,068.34", 0.89),
    ]
    result = parse_ocr_results(ocr)
    assert result.bill_type == "freight"
    assert result.quantity is not None and abs(result.quantity - 5633.40) < 1
    assert result.unit == "tonne-km"


# ─────────────────────────────────────────────────────────────────────────── #
#  8. Fallback trigger
# ─────────────────────────────────────────────────────────────────────────── #

def test_fallback_triggers_on_missing_fields():
    p = ParseResult()
    p.bill_type = "electricity"
    # quantity, amount, supplier all missing
    assert _should_trigger_fallback(p) is True


def test_fallback_not_triggered_when_complete():
    p = ParseResult()
    p.bill_type = "electricity"
    p.period_start = "2024-01-01"
    p.period_end = "2024-01-31"
    p.quantity = 5000.0
    p.unit = "kWh"
    p.amount_inr = 45000.0
    p.supplier = "BESCOM"
    p.overall_confidence = 0.85
    p.per_field_conf = {k: 0.85 for k in ["bill_type","period_start","period_end","quantity","unit","amount_inr","supplier"]}
    assert _should_trigger_fallback(p) is False


def test_merge_fallback_fills_missing():
    p = ParseResult()
    p.bill_type = None
    p.period_start = None
    fb = {
        "bill_type": "diesel",
        "period_start": "2024-06-20",
        "period_end": "2024-06-20",
        "quantity": 884.85,
        "unit": "L",
        "amount_inr": 83087.42,
        "supplier": "BPCL Chakan",
        "confidence_0_1": 0.80,
    }
    merged = _merge_fallback(p, fb)
    assert merged.bill_type == "diesel"
    assert merged.period_start == "2024-06-20"
    assert merged.quantity == 884.85


# ─────────────────────────────────────────────────────────────────────────── #
#  9. user_confirmed is ALWAYS False
# ─────────────────────────────────────────────────────────────────────────── #

def test_user_confirmed_always_false(tmp_path, monkeypatch):
    # Create a dummy bill image
    img = Image.new("RGB", (200, 100), color=(240, 240, 240))
    img_path = tmp_path / "dummy_bill.png"
    img.save(str(img_path))

    # Mock EasyOCR to return realistic electricity tokens
    mock_results = [
        ("MSEDCL Electric Bill", [[0,0],[200,0],[200,20],[0,20]], 0.92),
        ("01/01/2024 to 28/01/2024", [[0,20],[200,20],[200,40],[0,40]], 0.88),
        ("Units 5000 kWh", [[0,40],[200,40],[200,60],[0,60]], 0.90),
        ("Total Rs. 45000.00", [[0,60],[200,60],[200,80],[0,80]], 0.87),
        ("MSEDCL Mumbai", [[0,80],[200,80],[200,100],[0,100]], 0.85),
    ]

    monkeypatch.setattr("backend.ocr.reader.run_ocr", lambda img: mock_results)

    extraction = extract_bill(str(img_path))
    assert extraction.user_confirmed is False, "BUG: user_confirmed must never be auto-set to True"


# ─────────────────────────────────────────────────────────────────────────── #
#  10. Empty OCR → fallback triggered (mocked Gemini)
# ─────────────────────────────────────────────────────────────────────────── #

def test_empty_ocr_triggers_gemini_fallback(tmp_path, monkeypatch):
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    img_path = tmp_path / "blank_bill.png"
    img.save(str(img_path))

    # EasyOCR returns nothing
    monkeypatch.setattr("backend.ocr.reader.run_ocr", lambda img: [])

    fb_response = {
        "bill_type": "electricity",
        "period_start": "2024-03-01",
        "period_end": "2024-03-28",
        "quantity": 7326.5,
        "unit": "kWh",
        "amount_inr": 71579.90,
        "supplier": "BESCOM",
        "confidence_0_1": 0.80,
    }
    monkeypatch.setattr("backend.ocr.pipeline.gemini_fallback_extract", lambda *a, **kw: fb_response)

    extraction = extract_bill(str(img_path))
    assert extraction.method == "gemini_fallback"
    assert extraction.bill_type == "electricity"
    assert extraction.user_confirmed is False
    assert abs(extraction.quantity - 7326.5) < 0.1
