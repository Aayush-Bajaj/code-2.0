"""
Factor ID mapping for the Carbon Passport emission engine.

This module provides a single indirection layer between logical keys
(used throughout calculator.py) and physical factor_ids stored in factors.csv.

Rules:
- Never hardcode a factor value here; only factor_ids are stored.
- Every calculator call must go through this map so changing a data source
  only requires updating one file.
- Test suites inject TEST_FACTOR_MAP to point to test fixture factor IDs,
  keeping round numbers in the fixture and real values in production.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FactorMap:
    """
    Mapping from logical engine keys to physical factor_ids in factors.csv.

    Genset SFC keys are per-model (e.g. gen_C140D5P_sfc_75).
    Use make_sfc_key() to build them dynamically.
    """
    # Fuel combustion
    diesel: str = "diesel_mineral_l"
    petrol: str = "petrol_mineral_l"
    lpg_kg: str = "lpg_kg"

    # Electricity
    grid: str = "grid_india_wa"

    # Freight
    freight_road: str = "freight_hgv_avg_tkm"
    freight_rail: str = "freight_rail_tkm"

    # Generator meta-parameters (read from factors.csv as numbers, not hardcoded)
    genset_pf: str = "genset_power_factor"
    genset_tolerance: str = "gen_fuel_tolerance_pct"

    # Generator model used for SFC lookups — override per detection if nameplate is read
    genset_model: str = "C140D5P"

    def sfc_key(self, pct: int) -> str:
        """Return the factor_id for genset SFC at `pct`% load for the configured model."""
        return f"gen_{self.genset_model}_sfc_{pct}"


# --------------------------------------------------------------------------- #
#  Production map — points to real verified factor_ids in factors.csv
# --------------------------------------------------------------------------- #

PRODUCTION_FACTOR_MAP = FactorMap()


# --------------------------------------------------------------------------- #
#  Test map — points to factor_ids in tests/fixtures/factors_test.csv
#  Values are round numbers for hand-verifiable arithmetic; never used in prod.
# --------------------------------------------------------------------------- #

TEST_FACTOR_MAP = FactorMap(
    diesel="diesel_mineral_l",
    petrol="petrol_mineral_l",
    lpg_kg="lpg_kg",
    grid="grid_india_wa",
    freight_road="freight_hgv_avg_tkm",
    freight_rail="freight_rail_tkm",
    genset_pf="genset_power_factor",
    genset_tolerance="gen_fuel_tolerance_pct",
    genset_model="TEST",  # resolves to gen_TEST_sfc_75, gen_TEST_sfc_100
)
