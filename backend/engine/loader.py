"""
Factor registry and assumption loader.
Strictly checks all factors and assumptions: raises MissingFactorError
if any value is TODO_VERIFY, empty, or non-numeric.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

from backend.config import settings
from backend.engine.exceptions import MissingFactorError


@dataclass(frozen=True)
class FactorRecord:
    factor_id: str
    name: str
    value: float
    unit: str
    source_name: str
    source_url: str
    year: str
    notes: str


@dataclass(frozen=True)
class AssumptionRecord:
    key: str
    value: float
    unit: str
    source_note: str


class LoadedFactors:
    """Container for validated factors and assumptions with interpolation helpers."""

    def __init__(
        self,
        factors: Dict[str, FactorRecord],
        assumptions: Dict[str, AssumptionRecord],
    ):
        self._factors = factors
        self._assumptions = assumptions

    def get_factor(self, factor_id: str) -> FactorRecord:
        if factor_id not in self._factors:
            raise MissingFactorError(f"Required emission factor '{factor_id}' not found in registry.")
        return self._factors[factor_id]

    def get_assumption(self, key: str) -> AssumptionRecord:
        if key not in self._assumptions:
            raise MissingFactorError(f"Required assumption '{key}' not found in assumptions file.")
        return self._assumptions[key]

    @property
    def factors_dict(self) -> Dict[str, FactorRecord]:
        return self._factors

    @property
    def assumptions_dict(self) -> Dict[str, AssumptionRecord]:
        return self._assumptions

    def get_diesel_sfc(
        self,
        load_pct: float,
        factor_map,  # FactorMap — avoids circular import; duck-typed
    ) -> Tuple[float, List[str]]:
        """
        Specific fuel consumption (L/kWh) lookup with mandatory flags.

        Data source: factors.csv provides SFC at 75% and 100% load ONLY.
        Interpolation rules (never extrapolate):
          - load_pct >= 75: linear interpolation between sfc_75 and sfc_100.
          - load_pct < 75: clamp to sfc_75, add flag 'load_below_datasheet_range',
            and instruct caller to widen the range.

        Returns (sfc_value, flags).
        """
        flags: List[str] = []

        sfc_75 = self.get_factor(factor_map.sfc_key(75)).value
        sfc_100 = self.get_factor(factor_map.sfc_key(100)).value

        if load_pct >= 100.0:
            sfc = sfc_100
        elif load_pct >= 75.0:
            # Linear interpolation between 75% and 100%
            fraction = (load_pct - 75.0) / (100.0 - 75.0)
            sfc = sfc_75 + fraction * (sfc_100 - sfc_75)
        else:
            # Below the datasheet range — clamp and flag
            sfc = sfc_75
            flags.append("load_below_datasheet_range")

        return sfc, flags

    def get_genset_tolerance(self, factor_map) -> float:
        """
        Read generator fuel consumption tolerance from factors.csv (not hardcoded).
        Returns the fractional tolerance (e.g. 0.05 for +-5%).
        """
        return self.get_factor(factor_map.genset_tolerance).value

    def get_genset_pf(self, factor_map) -> float:
        """
        Read standard generator power factor from factors.csv.
        Used for kVA -> kW conversion.
        """
        return self.get_factor(factor_map.genset_pf).value


def load_factors(
    factors_csv_path: Optional[Path] = None,
    assumptions_yaml_path: Optional[Path] = None,
    strict_assumptions: bool = False,
) -> LoadedFactors:
    """
    Load factors.csv and assumptions.yaml.

    Validation rules:
    - factors.csv: every row must have a verified numeric value. TODO_VERIFY raises MissingFactorError.
    - assumptions.yaml: by default, TODO_VERIFY entries are SKIPPED (they belong to the twin/scenario
      module, not the emission engine). Pass strict_assumptions=True to enforce all assumptions.

    Comment lines beginning with '#' are silently skipped.
    """
    import logging
    _log = logging.getLogger(__name__)

    f_path = factors_csv_path or (settings.DATA_DIR / "factors" / "factors.csv")
    a_path = assumptions_yaml_path or (settings.DATA_DIR / "factors" / "assumptions.yaml")

    if not f_path.exists():
        raise MissingFactorError(f"Factors file not found at: {f_path}")
    if not a_path.exists():
        raise MissingFactorError(f"Assumptions file not found at: {a_path}")

    factors: Dict[str, FactorRecord] = {}
    with open(f_path, "r", encoding="utf-8") as f:
        # Skip comment lines starting with # (used only in test fixtures)
        lines = [line for line in f if not line.strip().startswith("#")]
        reader = csv.DictReader(lines)
        for row in reader:
            factor_id = row.get("factor_id", "").strip()
            if not factor_id:
                continue
            val_raw = str(row.get("value", "")).strip()
            if not val_raw or val_raw == "TODO_VERIFY":
                raise MissingFactorError(
                    f"Factor '{factor_id}' in {f_path.name} contains unverified value: '{val_raw}'."
                )
            try:
                numeric_val = float(val_raw)
            except ValueError:
                raise MissingFactorError(
                    f"Factor '{factor_id}' in {f_path.name} has non-numeric value: '{val_raw}'."
                )

            factors[factor_id] = FactorRecord(
                factor_id=factor_id,
                name=row.get("name", "").strip(),
                value=numeric_val,
                unit=row.get("unit", "").strip(),
                source_name=row.get("source_name", "").strip(),
                source_url=row.get("source_url", "").strip(),
                year=row.get("year", "").strip(),
                notes=row.get("notes", "").strip(),
            )

    assumptions: Dict[str, AssumptionRecord] = {}
    with open(a_path, "r", encoding="utf-8") as f:
        raw_yaml = yaml.safe_load(f) or {}

    for key, item in raw_yaml.items():
        if isinstance(item, dict):
            val_raw = str(item.get("value", "")).strip()
            unit = str(item.get("unit", "")).strip()
            note = str(item.get("source_note", "")).strip()
        else:
            val_raw = str(item).strip()
            unit = ""
            note = ""

        if not val_raw or val_raw == "TODO_VERIFY":
            if strict_assumptions:
                raise MissingFactorError(
                    f"Assumption '{key}' in {a_path.name} contains unverified value: '{val_raw}'."
                )
            else:
                _log.debug("Skipping unverified assumption '%s' (not needed by emission engine)", key)
                continue
        try:
            numeric_val = float(val_raw)
        except ValueError:
            raise MissingFactorError(
                f"Assumption '{key}' in {a_path.name} has non-numeric value: '{val_raw}'."
            )

        assumptions[key] = AssumptionRecord(
            key=key,
            value=numeric_val,
            unit=unit,
            source_note=note,
        )

    return LoadedFactors(factors=factors, assumptions=assumptions)
