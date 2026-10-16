"""
Unit normalisation and validation rules for the emission engine.
Rejects unapproved units (such as gallons) with a clear UnitError.
"""

from __future__ import annotations
from typing import Tuple
from backend.engine.exceptions import UnitError


def normalise_electricity_unit(value: float, unit: str) -> Tuple[float, str]:
    """
    Normalise electricity consumption to kWh.
    Converts MWh to kWh (1 MWh = 1000 kWh).
    Accepts: 'kwh', 'units', 'mwh'.
    """
    cleaned = (unit or "").strip().lower()
    if cleaned in ("kwh", "units", "unit"):
        return float(value), "kWh"
    if cleaned == "mwh":
        return float(value) * 1000.0, "kWh"
    raise UnitError(f"Unsupported electricity unit '{unit}'. Expected 'kWh', 'units', or 'MWh'.")


def normalise_fuel_unit(value: float, unit: str) -> Tuple[float, str]:
    """
    Normalise fuel volume to litres (L).
    Rejects gallons with an explicit UnitError.
    Accepts: 'l', 'ltr', 'ltrs', 'litre', 'litres', 'liter', 'liters'.
    """
    cleaned = (unit or "").strip().lower()
    if cleaned in ("gallon", "gallons", "gal"):
        raise UnitError("Gallons are rejected. All fuel figures must be specified in litres (L).")
    if cleaned in ("l", "ltr", "ltrs", "litre", "litres", "liter", "liters", "l diesel", "litres diesel", "liter diesel", "ltr diesel"):
        return float(value), "L"
    raise UnitError(f"Unsupported fuel unit '{unit}'. Expected litres ('L', 'litres').")


def normalise_freight_unit(value: float, unit: str) -> Tuple[float, str]:
    """
    Normalise freight activity to tonne-km.
    Accepts: 'tonne-km', 'tonne km', 'tkm', 't-km', 'tonne_km'.
    """
    cleaned = (unit or "").strip().lower()
    if cleaned in ("tonne-km", "tonne km", "tkm", "t-km", "tonne_km"):
        return float(value), "tonne-km"
    raise UnitError(f"Unsupported freight unit '{unit}'. Expected 'tonne-km' (tkm).")
