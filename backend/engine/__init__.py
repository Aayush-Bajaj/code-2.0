"""
Emission Engine Package — Carbon Passport.
Pure Python deterministic calculation engine with zero LLM dependence.
"""

from backend.engine.factor_map import FactorMap, PRODUCTION_FACTOR_MAP, TEST_FACTOR_MAP
from backend.engine.exceptions import (
    EngineError,
    MissingFactorError,
    UnitError,
    NeedsUserInput,
)
from backend.engine.loader import (
    load_factors,
    LoadedFactors,
    FactorRecord,
    AssumptionRecord,
)
from backend.engine.units import (
    normalise_electricity_unit,
    normalise_fuel_unit,
    normalise_freight_unit,
)
from backend.engine.uncertainty import (
    BILL_BASE_UNCERTAINTY,
    BILL_CONFIDENCE_THRESHOLD,
    BILL_LOW_CONF_WIDENING,
    DETECTION_LOAD_POINTS,
    SMOKE_SCORE_WIDENING_THRESHOLD,
    DETECTION_SMOKE_WIDENING,
    DETECTION_CONFIDENCE_THRESHOLD,
    DETECTION_LOW_CONF_WIDENING,
    DETECTION_BELOW_RANGE_WIDENING,
)
from backend.engine.calculator import (
    electricity_from_bill,
    fuel_from_bill,
    freight_from_bill,
    fuel_from_detection,
    reconcile,
    totals,
)

__all__ = [
    "FactorMap",
    "PRODUCTION_FACTOR_MAP",
    "TEST_FACTOR_MAP",
    "EngineError",
    "MissingFactorError",
    "UnitError",
    "NeedsUserInput",
    "load_factors",
    "LoadedFactors",
    "FactorRecord",
    "AssumptionRecord",
    "normalise_electricity_unit",
    "normalise_fuel_unit",
    "normalise_freight_unit",
    "BILL_BASE_UNCERTAINTY",
    "BILL_CONFIDENCE_THRESHOLD",
    "BILL_LOW_CONF_WIDENING",
    "DETECTION_LOAD_POINTS",
    "SMOKE_SCORE_WIDENING_THRESHOLD",
    "DETECTION_SMOKE_WIDENING",
    "DETECTION_CONFIDENCE_THRESHOLD",
    "DETECTION_LOW_CONF_WIDENING",
    "DETECTION_BELOW_RANGE_WIDENING",
    "electricity_from_bill",
    "fuel_from_bill",
    "freight_from_bill",
    "fuel_from_detection",
    "reconcile",
    "totals",
]
