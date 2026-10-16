"""
Uncertainty quantification module for Carbon Passport.

Every EmissionLine returns low_kg and high_kg.
Named constants define all standard uncertainties and widening factors.
Every widening trigger is documented and recorded in the flags list.
"""

from __future__ import annotations
from typing import List, Optional, Tuple

# --------------------------------------------------------------------------- #
#  Named Constants & Documented Justifications
# --------------------------------------------------------------------------- #

# Standard utility meter tolerance and calibration uncertainty (+-5%)
BILL_BASE_UNCERTAINTY = 0.05

# Confidence threshold below which OCR extraction uncertainty is widened
BILL_CONFIDENCE_THRESHOLD = 0.70

# Additional uncertainty (+-5%) added when OCR confidence is below threshold
BILL_LOW_CONF_WIDENING = 0.05

# Human estimation uncertainty on generator operational load (+-15 percentage points)
# Accounts for fluctuating machine cycles during MSME operating hours
DETECTION_LOAD_POINTS = 15.0

# Optical smoke score threshold (0-10) triggering maintenance flag and uncertainty widening
SMOKE_SCORE_WIDENING_THRESHOLD = 6.0

# Additional uncertainty widening (+-10%) for high smoke or dark/blue exhaust
# Smoke indicates incomplete combustion or lube oil burning, widening fuel consumption variance
DETECTION_SMOKE_WIDENING = 0.10

# Machine detection visual confidence threshold
DETECTION_CONFIDENCE_THRESHOLD = 0.60

# Additional uncertainty widening (+-10%) when visual recognition confidence is low
DETECTION_LOW_CONF_WIDENING = 0.10

# Additional widening (+-15%) when load is below the datasheet range (< 75%)
DETECTION_BELOW_RANGE_WIDENING = 0.15


def compute_bill_uncertainty(
    co2e_kg: float,
    ocr_confidence: Optional[float] = None,
) -> Tuple[float, float, List[str]]:
    """
    Compute low_kg and high_kg for bill-based emission lines.
    Base range is +-5%. If OCR confidence is below threshold, widens by a further 5%.
    """
    flags: List[str] = []
    spread = BILL_BASE_UNCERTAINTY

    if ocr_confidence is not None and ocr_confidence < BILL_CONFIDENCE_THRESHOLD:
        spread += BILL_LOW_CONF_WIDENING
        flags.append("ocr_low_confidence_widened")

    low_kg = max(0.0, co2e_kg * (1.0 - spread))
    high_kg = co2e_kg * (1.0 + spread)
    return low_kg, high_kg, flags


def compute_detection_uncertainty(
    kw: float,
    hours: float,
    load_pct: float,
    sfc_func,
    ef_value: float,
    sfc_tolerance: float,        # From gen_fuel_tolerance_pct in factors.csv
    sfc_extra_flags: List[str],  # Flags from get_diesel_sfc (e.g. load_below_datasheet_range)
    smoke_score: float = 0.0,
    smoke_color: str = "none",
    detection_confidence: float = 1.0,
) -> Tuple[float, float, List[str]]:
    """
    Compute low_kg and high_kg for machine detection lines.

    - Load bounds: +-15 percentage points (clamped to [75, 100] because we only
      have datasheet SFC at those points).
    - Fuel use tolerance: read from gen_fuel_tolerance_pct in factors.csv.
    - If load was below datasheet range (flag in sfc_extra_flags), widen further.
    - Widens for heavy smoke or low detection confidence.
    """
    flags: List[str] = list(sfc_extra_flags)

    # 1. Load bounds (+-15 points, clamped so SFC lookup stays within 75-100%)
    load_low = max(75.0, load_pct - DETECTION_LOAD_POINTS)
    load_high = min(100.0, load_pct + DETECTION_LOAD_POINTS)

    # 2. SFC at bounds + fuel tolerance from factors.csv
    sfc_at_low_load, _ = sfc_func(load_low)
    sfc_at_high_load, _ = sfc_func(load_high)

    # Low bound uses lowest SFC (less fuel at higher load efficiency)
    # but the tolerance adds uncertainty on top
    sfc_low = min(sfc_at_low_load, sfc_at_high_load) * (1.0 - sfc_tolerance)
    sfc_high = max(sfc_at_low_load, sfc_at_high_load) * (1.0 + sfc_tolerance)

    # 3. Base litres and CO2e bounds
    litres_low = kw * (load_low / 100.0) * hours * sfc_low
    litres_high = kw * (load_high / 100.0) * hours * sfc_high

    low_kg = max(0.0, litres_low * ef_value)
    high_kg = max(0.0, litres_high * ef_value)

    # 4. Below datasheet range: widen further
    if "load_below_datasheet_range" in sfc_extra_flags:
        low_kg = max(0.0, low_kg * (1.0 - DETECTION_BELOW_RANGE_WIDENING))
        high_kg = high_kg * (1.0 + DETECTION_BELOW_RANGE_WIDENING)

    # 5. Smoke widening: smoke score >= 6.0 or dark/blue exhaust
    color_normalized = (smoke_color or "").strip().lower()
    has_heavy_smoke = (
        smoke_score >= SMOKE_SCORE_WIDENING_THRESHOLD
        or color_normalized in ("black", "blue", "dark")
    )
    if has_heavy_smoke:
        low_kg = max(0.0, low_kg * (1.0 - DETECTION_SMOKE_WIDENING))
        high_kg = high_kg * (1.0 + DETECTION_SMOKE_WIDENING)
        flags.append("smoke_inefficiency_widened")

    # 6. Low visual detection confidence widening
    if detection_confidence < DETECTION_CONFIDENCE_THRESHOLD:
        low_kg = max(0.0, low_kg * (1.0 - DETECTION_LOW_CONF_WIDENING))
        high_kg = high_kg * (1.0 + DETECTION_LOW_CONF_WIDENING)
        flags.append("detection_low_confidence_widened")

    return low_kg, high_kg, flags
