"""
Regex + keyword-proximity parser for Indian utility and freight bills.

Handles:
- Indian number formats  : 1,23,456.00  /  1,23,456  /  1234.56
- Date formats           : dd/mm/yyyy  dd-mm-yyyy  dd.mm.yyyy  yyyy-mm-dd
- OCR char confusions    : O↔0, l↔1, S↔5, I↔1  (only inside numeric fields)
- Bill type detection    : electricity / diesel / freight via keyword proximity
- Unit normalisation     : MWh→kWh, litre/ltr/ltrs→L, tkm/t-km→tonne-km
- Sanity checks          : negative values, >10M kWh, >1M L
- field_boxes            : bounding rectangle of the OCR token used
"""

from __future__ import annotations

import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Type alias
# --------------------------------------------------------------------------- #
OCRResult = Tuple[str, List[List[int]], float]
FieldBoxes = Dict[str, Any]
ParsedFields = Dict[str, Any]


# =========================================================================== #
#  Helpers – number / date cleaning
# =========================================================================== #

_OCR_NUMERIC_FIXES = str.maketrans({
    "O": "0", "o": "0",
    "l": "1", "I": "1",
    "S": "5", "s": "5",
    "B": "8", "b": "6",
    "G": "6", "g": "9",
    "Z": "2", "z": "2",
})


def _fix_ocr_numeric(text: str) -> str:
    """Apply OCR character substitutions only inside what looks like a number."""
    return re.sub(
        r"[\dOolISsBbGgZz,\.]+",
        lambda m: m.group().translate(_OCR_NUMERIC_FIXES),
        text,
    )


def _parse_indian_number(s: str) -> Optional[float]:
    """Parse Indian formatted number like 1,23,456.78 or 1,234.5."""
    s = s.strip()
    s = _fix_ocr_numeric(s)
    # Remove all commas (Indian grouping), then parse
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(s: str) -> Optional[str]:
    """
    Try common Indian date formats, return ISO YYYY-MM-DD.
    Accepts: dd/mm/yyyy  dd-mm-yyyy  dd.mm.yyyy  yyyy-mm-dd  mm/yyyy  mm-yyyy
    """
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Try partial: mm/yyyy
    m = re.match(r"(\d{1,2})[/\-](\d{4})", s)
    if m:
        try:
            return datetime(int(m.group(2)), int(m.group(1)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


# =========================================================================== #
#  Keyword sets
# =========================================================================== #

_ELEC_KW = {
    "kwh", "kwh.", "units", "unit", "electricity", "electrical", "power",
    "mwh", "consumption", "energy", "electric", "bijli", "bijlee",
    "msedcl", "bescom", "tata power", "torrent", "dhbvn", "wesco", "discom",
}
_DIESEL_KW = {
    "diesel", "hsd", "hs diesel", "fuel", "litres", "litre", "ltr", "ltrs",
    "petroleum", "iocl", "bpcl", "hpcl", "shell", "nayara",
    "fuelling", "fuel point", "petrol",
}
_FREIGHT_KW = {
    "freight", "logistics", "transport", "cargo", "tkm", "tonne-km",
    "tonne km", "consignment", "delivery", "dispatch",
    "vrl", "tci", "gati", "bluedart", "blue dart", "dhl", "safechem",
}


def _detect_bill_type(full_text: str) -> Tuple[Optional[str], float]:
    lower = full_text.lower()
    scores = {"electricity": 0, "diesel": 0, "freight": 0}
    for kw in _ELEC_KW:
        if kw in lower:
            scores["electricity"] += 1
    for kw in _DIESEL_KW:
        if kw in lower:
            scores["diesel"] += 1
    for kw in _FREIGHT_KW:
        if kw in lower:
            scores["freight"] += 1
    best = max(scores, key=lambda k: scores[k])
    total = sum(scores.values()) or 1
    conf = scores[best] / total
    if scores[best] == 0:
        return None, 0.0
    return best, min(1.0, conf)


# =========================================================================== #
#  Unit normalisation
# =========================================================================== #

_UNIT_MAP: Dict[str, str] = {
    # Electricity
    "mwh": "kWh",  # 1 MWh = 1000 kWh (caller must multiply quantity)
    "kwh": "kWh",
    "units": "kWh",
    "unit": "kWh",
    # Diesel
    "litres": "L",
    "litre": "L",
    "ltr": "L",
    "ltrs": "L",
    "l": "L",
    # Freight
    "tkm": "tonne-km",
    "t-km": "tonne-km",
    "tonne-km": "tonne-km",
    "tonne km": "tonne-km",
    "ton-km": "tonne-km",
    "tonkm": "tonne-km",
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
}


def _normalise_unit(raw: str, quantity: float) -> Tuple[str, float]:
    """Return (normalised_unit, adjusted_quantity)."""
    key = raw.strip().lower()
    mapped = _UNIT_MAP.get(key, raw.strip())
    if key == "mwh":
        quantity = quantity * 1000  # convert to kWh
    return mapped, quantity


# =========================================================================== #
#  Sanity checks
# =========================================================================== #

_SANITY: Dict[str, Tuple[float, float]] = {
    "electricity": (0.1, 1_000_000),   # kWh
    "diesel":      (0.1, 100_000),     # L
    "freight":     (0.1, 10_000_000),  # tonne-km or kg
}


def _sanity_check(bill_type: str, quantity: float, unit: str) -> Optional[str]:
    lo, hi = _SANITY.get(bill_type, (0.1, 1e12))
    if quantity < 0:
        return f"Negative quantity {quantity} for {bill_type}"
    if quantity < lo:
        return f"Suspiciously low quantity {quantity} {unit} for {bill_type}"
    if quantity > hi:
        return f"Suspiciously large quantity {quantity} {unit} for {bill_type}"
    return None


# =========================================================================== #
#  Bounding box helpers
# =========================================================================== #

def _box_rect(quad: List[List[int]]) -> List[int]:
    """Return [xmin, ymin, xmax, ymax] from a 4-point quad."""
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return [min(xs), min(ys), max(xs), max(ys)]


# =========================================================================== #
#  Field extraction regexes
# =========================================================================== #

# Date – dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy, yyyy-mm-dd
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})\b"
)

# Indian currency: optional Rs/INR prefix, then number
_AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr\.?|₹|total\s*[:\-]?\s*)?\s*"
    r"([\d,]+(?:\.\d{1,2})?)"
    r"(?:\s*(?:/\-|/-|only))?",
    re.IGNORECASE,
)

# Quantity patterns: e.g. "13,343.80 kWh" or "662.83 L"
_QTY_UNIT_RE = re.compile(
    r"([\d,]+(?:\.\d{1,3})?)\s*"
    r"(kwh|mwh|units?|litres?|ltrs?|ltr|l\b|tkm|t\-km|tonne[\-\s]km|ton[\-\s]km|tonkm|kg|kgs)",
    re.IGNORECASE,
)

# Billing period keywords
_PERIOD_KEYWORDS = re.compile(
    r"(?:bill(?:ing)?\s*period|period|from|to|date|due\s*date|billing\s*date)",
    re.IGNORECASE,
)

# Supplier / company name indicators
_SUPPLIER_KEYWORDS = re.compile(
    r"(?:from|bill\s+from|supplier|company|utility|issued\s+by|service\s+provider)\s*[:\-]?\s*(.+)",
    re.IGNORECASE,
)


# =========================================================================== #
#  Main parser
# =========================================================================== #

class ParseResult:
    def __init__(self):
        self.bill_type: Optional[str] = None
        self.bill_type_conf: float = 0.0
        self.period_start: Optional[str] = None
        self.period_end: Optional[str] = None
        self.quantity: Optional[float] = None
        self.unit: Optional[str] = None
        self.amount_inr: Optional[float] = None
        self.supplier: Optional[str] = None
        self.overall_confidence: float = 0.0
        self.flags: List[str] = []
        self.field_boxes: FieldBoxes = {}
        self.per_field_conf: Dict[str, float] = {}


def parse_ocr_results(ocr_results: List[OCRResult]) -> ParseResult:
    """
    Parse a flat list of (text, quad_box, confidence) OCR tokens into structured bill fields.
    """
    result = ParseResult()
    if not ocr_results:
        result.flags.append("no_ocr_output")
        return result

    full_text = " ".join(t for t, _, _ in ocr_results)
    full_text_lower = full_text.lower()

    # ------------------------------------------------------------------ #
    #  1. Bill type
    # ------------------------------------------------------------------ #
    bill_type, bt_conf = _detect_bill_type(full_text)
    result.bill_type = bill_type
    result.bill_type_conf = bt_conf
    result.per_field_conf["bill_type"] = bt_conf

    # ------------------------------------------------------------------ #
    #  2. Dates (look for two distinct dates for period_start / period_end)
    # ------------------------------------------------------------------ #
    dates_found: List[Tuple[str, float, List[int]]] = []
    for text, quad, conf in ocr_results:
        for m in _DATE_RE.finditer(text):
            iso = _parse_date(m.group(1))
            if iso:
                dates_found.append((iso, conf, _box_rect(quad)))

    # Deduplicate
    seen_dates = []
    for iso, conf, box in dates_found:
        if iso not in [d[0] for d in seen_dates]:
            seen_dates.append((iso, conf, box))

    if seen_dates:
        seen_dates.sort(key=lambda x: x[0])  # chronological
        result.period_start = seen_dates[0][0]
        result.field_boxes["period_start"] = seen_dates[0][2]
        result.per_field_conf["period_start"] = seen_dates[0][1]
        if len(seen_dates) > 1:
            result.period_end = seen_dates[-1][0]
            result.field_boxes["period_end"] = seen_dates[-1][2]
            result.per_field_conf["period_end"] = seen_dates[-1][1]
        else:
            # Single-date bills (diesel / freight invoices) – same start & end
            result.period_end = result.period_start
            result.field_boxes["period_end"] = result.field_boxes["period_start"]
            result.per_field_conf["period_end"] = result.per_field_conf["period_start"]

    # ------------------------------------------------------------------ #
    #  3. Quantity & Unit
    # ------------------------------------------------------------------ #
    qty_candidates: List[Tuple[float, str, float, List[int]]] = []
    for text, quad, conf in ocr_results:
        cleaned = _fix_ocr_numeric(text)
        for m in _QTY_UNIT_RE.finditer(cleaned):
            qty_str = m.group(1)
            unit_raw = m.group(2)
            qty = _parse_indian_number(qty_str)
            if qty is not None and qty > 0:
                norm_unit, adj_qty = _normalise_unit(unit_raw, qty)
                qty_candidates.append((adj_qty, norm_unit, conf, _box_rect(quad)))

    # Sort candidates by confidence, pick the one consistent with bill_type
    if qty_candidates:
        # Prefer candidate that matches bill type unit
        def _unit_score(cand):
            _, unit, conf, _ = cand
            if bill_type == "electricity" and unit == "kWh":
                return conf + 1
            if bill_type == "diesel" and unit == "L":
                return conf + 1
            if bill_type == "freight" and unit in ("tonne-km", "kg"):
                return conf + 1
            return conf

        qty_candidates.sort(key=_unit_score, reverse=True)
        q, u, qconf, qbox = qty_candidates[0]
        result.quantity = q
        result.unit = u
        result.field_boxes["quantity"] = qbox
        result.field_boxes["unit"] = qbox
        result.per_field_conf["quantity"] = qconf
        result.per_field_conf["unit"] = qconf

    # ------------------------------------------------------------------ #
    #  4. Amount in INR
    # ------------------------------------------------------------------ #
    # Strategy: collect all numbers, look near "total", "amount", "rs", "inr", "₹"
    amount_kw_tokens = []
    for text, quad, conf in ocr_results:
        lo = text.lower()
        if any(k in lo for k in ("total", "amount", "rs", "inr", "₹", "payable", "net")):
            amount_kw_tokens.append((text, quad, conf))

    # Also scan full document lines
    amount_candidates: List[Tuple[float, float, List[int]]] = []
    search_list = amount_kw_tokens if amount_kw_tokens else ocr_results
    for text, quad, conf in search_list:
        cleaned = _fix_ocr_numeric(text)
        for m in _AMOUNT_RE.finditer(cleaned):
            num_str = m.group(1)
            if not num_str:
                continue
            val = _parse_indian_number(num_str)
            if val is not None and val > 100:  # amounts are > 100 INR
                amount_candidates.append((val, conf, _box_rect(quad)))

    if amount_candidates:
        # Largest amount is usually the total (avoid rate_per_unit)
        amount_candidates.sort(key=lambda x: x[0], reverse=True)
        amt, aconf, abox = amount_candidates[0]
        result.amount_inr = amt
        result.field_boxes["amount_inr"] = abox
        result.per_field_conf["amount_inr"] = aconf

    # ------------------------------------------------------------------ #
    #  5. Supplier name
    # ------------------------------------------------------------------ #
    supplier = _extract_supplier(ocr_results, full_text)
    if supplier:
        result.supplier = supplier[0]
        result.field_boxes["supplier"] = supplier[1]
        result.per_field_conf["supplier"] = supplier[2]

    # ------------------------------------------------------------------ #
    #  6. Sanity checks
    # ------------------------------------------------------------------ #
    if result.quantity is not None and result.unit is not None and result.bill_type:
        warn = _sanity_check(result.bill_type, result.quantity, result.unit)
        if warn:
            result.flags.append(f"sanity_fail:{warn}")

    # ------------------------------------------------------------------ #
    #  7. Overall confidence
    # ------------------------------------------------------------------ #
    confs = list(result.per_field_conf.values())
    result.overall_confidence = round(sum(confs) / len(confs), 3) if confs else 0.0

    return result


def _extract_supplier(
    ocr_results: List[OCRResult],
    full_text: str,
) -> Optional[Tuple[str, List[int], float]]:
    """
    Try to extract the supplier / company name.
    Heuristic: first long capitalised token block, or text near supplier keywords.
    """
    # Look for explicit keyword patterns
    for text, quad, conf in ocr_results:
        m = _SUPPLIER_KEYWORDS.match(text)
        if m:
            name = m.group(1).strip()
            if len(name) > 5:
                return name, _box_rect(quad), conf

    # Heuristic: first text block that is at least 10 chars and contains a capital letter
    # and does NOT look like a date or pure number
    for text, quad, conf in ocr_results:
        t = text.strip()
        if (
            len(t) >= 8
            and re.search(r"[A-Z][a-zA-Z\s\.\-&]+", t)
            and not _DATE_RE.search(t)
            and not re.fullmatch(r"[\d,\.\s]+", t)
            and conf > 0.5
        ):
            return t, _box_rect(quad), conf

    return None
