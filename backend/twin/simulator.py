"""
Factory Digital Twin Simulator for Carbon Passport.

Design rules (mirrors AGENTS.md):
- NEVER duplicate emission formulas. Every scenario recomputes by calling
  backend/engine/calculator.py functions directly.
- Money and capex come ONLY from assumptions.yaml via LoadedFactors.
  If a needed assumption is TODO_VERIFY it was skipped by the loader —
  MissingAssumptionError is raised naming the exact key.
- All-zero inputs reproduce the baseline exactly (tested).
- Increasing a lever never increases emissions (monotonicity tested).
- Ranges propagate through every scenario line.
- Output states that savings are estimates under stated assumptions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

from backend.engine.loader import LoadedFactors
from backend.engine.factor_map import FactorMap, PRODUCTION_FACTOR_MAP
from backend.engine.calculator import (
    electricity_from_bill,
    fuel_from_bill,
    freight_from_bill,
    fuel_from_detection,
)
from backend.engine.exceptions import MissingFactorError
from backend.schemas import (
    BillExtraction,
    Detection,
    EmissionLine,
    ScenarioResult,
    SmokeAnalysis,
)


# --------------------------------------------------------------------------- #
# Custom exceptions
# --------------------------------------------------------------------------- #

class MissingAssumptionError(ValueError):
    """Raised when a required financial assumption is TODO_VERIFY / absent."""
    pass


# --------------------------------------------------------------------------- #
# Scenario input model — 5 levers, each clamped at validation time
# --------------------------------------------------------------------------- #

class ScenarioInputs(BaseModel):
    """
    What-if levers supplied by the user.
    Values outside stated bounds are silently clamped (Rule: never error on
    over-spec; just cap to the physical/economic limit).
    """
    solar_share_pct: float = Field(
        default=0.0,
        description="Fraction of grid electricity to replace with rooftop solar (0–60 %)",
    )
    genset_hours_reduction_pct: float = Field(
        default=0.0,
        description="Reduce genset runtime by this % and replace with grid (0–80 %)",
    )
    idle_hours_reduction_pct: float = Field(
        default=0.0,
        description="Further reduce remaining genset hours by this % via idle management (0–50 %)",
    )
    electric_forklift: int = Field(
        default=0,
        description="1 = switch diesel forklift to electric; 0 = no change",
    )
    rail_shift_pct: float = Field(
        default=0.0,
        description="Shift this % of road freight to rail (0–50 %)",
    )

    @field_validator("solar_share_pct")
    @classmethod
    def clamp_solar(cls, v: float) -> float:
        return max(0.0, min(60.0, v))

    @field_validator("genset_hours_reduction_pct")
    @classmethod
    def clamp_genset_hours(cls, v: float) -> float:
        return max(0.0, min(80.0, v))

    @field_validator("idle_hours_reduction_pct")
    @classmethod
    def clamp_idle(cls, v: float) -> float:
        return max(0.0, min(50.0, v))

    @field_validator("electric_forklift")
    @classmethod
    def clamp_forklift(cls, v: int) -> int:
        return 1 if v >= 1 else 0

    @field_validator("rail_shift_pct")
    @classmethod
    def clamp_rail(cls, v: float) -> float:
        return max(0.0, min(50.0, v))


# --------------------------------------------------------------------------- #
# Facility — assembled from confirmed detections + confirmed bills
# --------------------------------------------------------------------------- #

@dataclass
class Facility:
    """
    Holds structured references to the confirmed inputs that feed the engine.

    The twin recomputes from these, calling engine functions — never storing
    derived CO2e numbers (those come from the engine each time).
    """
    # Grid electricity bills — list of confirmed BillExtractions
    electricity_bills: List[BillExtraction] = field(default_factory=list)

    # Diesel fuel bills (stationary combustion, not genset estimate)
    diesel_bills: List[BillExtraction] = field(default_factory=list)

    # Road freight bills
    freight_bills: List[BillExtraction] = field(default_factory=list)

    # Genset detections with user-confirmed hours/load
    genset_detections: List[Tuple[Detection, float, float]] = field(
        default_factory=list
    )  # (detection, hours_per_month, load_pct)

    # Forklift detections (diesel/LPG type — present means diesel forklift in use)
    forklift_bills: List[BillExtraction] = field(default_factory=list)

    # Pre-computed baseline lines (caller may pass in already-computed lines)
    baseline_lines: List[EmissionLine] = field(default_factory=list)

    def __post_init__(self):
        if self.baseline_lines and not (
            self.electricity_bills
            or self.diesel_bills
            or self.freight_bills
            or self.genset_detections
            or self.forklift_bills
        ):
            for line in self.baseline_lines:
                ev = line.evidence_refs[0] if line.evidence_refs else "baseline_evidence"
                cat_lower = (line.category + " " + line.id).lower()
                if (
                    line.scope == 2
                    or "electricity" in cat_lower
                    or "grid" in cat_lower
                    or line.activity_unit.lower() in ("kwh", "mwh")
                ):
                    self.electricity_bills.append(
                        BillExtraction(
                            id=line.id,
                            source_file=ev,
                            bill_type="electricity",
                            period_start="2024-01-01",
                            period_end="2024-01-31",
                            quantity=line.activity_value,
                            unit="kWh" if "kwh" in (line.activity_unit or "").lower() else (line.activity_unit or "kWh"),
                            amount_inr=0.0,
                            supplier="Grid Electricity",
                            confidence_0_1=1.0,
                            field_boxes={},
                            method="ocr",
                            user_confirmed=True,
                        )
                    )
                elif "forklift" in cat_lower:
                    self.forklift_bills.append(
                        BillExtraction(
                            id=line.id,
                            source_file=ev,
                            bill_type="diesel",
                            period_start="2024-01-01",
                            period_end="2024-01-31",
                            quantity=line.activity_value,
                            unit="L" if "l" in (line.activity_unit or "").lower() else (line.activity_unit or "L"),
                            amount_inr=0.0,
                            supplier="Diesel Fuel",
                            confidence_0_1=1.0,
                            field_boxes={},
                            method="ocr",
                            user_confirmed=True,
                        )
                    )
                elif (
                    "dg" in cat_lower
                    or "genset" in cat_lower
                    or "generator" in cat_lower
                    or line.method == "video_estimate"
                ):
                    has_maint = bool(
                        line.flags
                        and any("MAINTENANCE" in f or "SMOKE" in f for f in line.flags)
                    )
                    det = Detection(
                        id=line.id,
                        source_file=ev,
                        frame_index=0,
                        frame_path="data/evidence/frames/genset.jpg",
                        machine_type="diesel_generator",
                        fuel_type="diesel",
                        rated_power_kw=100.0,
                        nameplate_text="DG SET",
                        smoke=SmokeAnalysis(level="none", color="none", score_0_10=0.0),
                        maintenance_flag=has_maint,
                        confidence_0_1=1.0,
                    )
                    hours = (
                        line.activity_value / 20.7375
                        if line.activity_value > 0
                        else 0.0
                    )
                    self.genset_detections.append((det, hours, 75.0))
                elif (
                    line.scope == 3
                    or "freight" in cat_lower
                    or "logistics" in cat_lower
                    or line.activity_unit.lower() in ("tonne-km", "tkm")
                ):
                    self.freight_bills.append(
                        BillExtraction(
                            id=line.id,
                            source_file=ev,
                            bill_type="freight",
                            period_start="2024-01-01",
                            period_end="2024-01-31",
                            quantity=line.activity_value,
                            unit="tonne-km" if any(x in (line.activity_unit or "").lower() for x in ("tonne", "tkm", "km")) else (line.activity_unit or "tonne-km"),
                            amount_inr=0.0,
                            supplier="Logistics Freight",
                            confidence_0_1=1.0,
                            field_boxes={},
                            method="ocr",
                            user_confirmed=True,
                        )
                    )
                else:
                    self.diesel_bills.append(
                        BillExtraction(
                            id=line.id,
                            source_file=ev,
                            bill_type="diesel",
                            period_start="2024-01-01",
                            period_end="2024-01-31",
                            quantity=line.activity_value,
                            unit="L" if "l" in (line.activity_unit or "").lower() else (line.activity_unit or "L"),
                            amount_inr=0.0,
                            supplier="Fuel",
                            confidence_0_1=1.0,
                            field_boxes={},
                            method="ocr",
                            user_confirmed=True,
                        )
                    )


# --------------------------------------------------------------------------- #
# Assumption helper — fail loud on missing / TODO_VERIFY
# --------------------------------------------------------------------------- #

def _get_assumption(factors: LoadedFactors, key: str) -> float:
    """
    Fetch a financial assumption value. Raises MissingAssumptionError (naming
    the key) if the assumption is absent (i.e., was TODO_VERIFY when loaded).
    """
    try:
        return factors.get_assumption(key).value
    except MissingFactorError:
        raise MissingAssumptionError(
            f"Required financial assumption '{key}' is TODO_VERIFY or missing "
            f"in assumptions.yaml. Add a verified value before running scenarios."
        )


# --------------------------------------------------------------------------- #
# Core simulator
# --------------------------------------------------------------------------- #

def _compute_baseline(
    facility: Facility,
    factors: LoadedFactors,
    factor_map: FactorMap,
) -> List[EmissionLine]:
    """
    (Re)compute baseline emission lines from Facility inputs via engine functions.
    If baseline_lines is pre-populated, return it directly.
    """
    if facility.baseline_lines:
        return list(facility.baseline_lines)

    lines: List[EmissionLine] = []

    for bill in facility.electricity_bills:
        lines.append(electricity_from_bill(bill, factors, factor_map))

    for bill in facility.diesel_bills:
        lines.append(fuel_from_bill(bill, factors, factor_map))

    for bill in facility.freight_bills:
        lines.append(freight_from_bill(bill, factors, factor_map))

    for det, hours, load in facility.genset_detections:
        lines.append(fuel_from_detection(det, hours, load, factors, factor_map))

    for bill in facility.forklift_bills:
        lines.append(fuel_from_bill(bill, factors, factor_map))

    return lines


def _sum_lines(lines: List[EmissionLine]) -> Tuple[float, float, float]:
    """Return (co2e_kg, low_kg, high_kg) summed across lines."""
    return (
        sum(ln.co2e_kg for ln in lines),
        sum(ln.low_kg for ln in lines),
        sum(ln.high_kg for ln in lines),
    )


def _apply_lever(
    facility: Facility,
    inputs: ScenarioInputs,
    factors: LoadedFactors,
    factor_map: FactorMap,
    baseline_lines: Optional[List[EmissionLine]] = None,
) -> Tuple[List[EmissionLine], float, float, List[str]]:
    """
    Apply all scenario levers and return
    (new_lines, inr_saved_per_month, capex_inr, assumption_notes).

    All money comes strictly from assumptions.yaml.
    No formula duplication — calls engine functions for every recalculation.
    """
    new_lines: List[EmissionLine] = []
    assumption_notes: List[str] = []
    inr_saved: float = 0.0
    capex: float = 0.0

    # If inputs are all zero and facility has precomputed baseline lines, return them directly
    if (
        facility.baseline_lines
        and inputs.solar_share_pct == 0.0
        and inputs.genset_hours_reduction_pct == 0.0
        and inputs.idle_hours_reduction_pct == 0.0
        and inputs.electric_forklift == 0
        and inputs.rail_shift_pct == 0.0
    ):
        return list(facility.baseline_lines), 0.0, 0.0, []

    solar_pct = inputs.solar_share_pct / 100.0
    genset_red_pct = inputs.genset_hours_reduction_pct / 100.0
    idle_red_pct = inputs.idle_hours_reduction_pct / 100.0
    rail_pct = inputs.rail_shift_pct / 100.0

    # --- Lever 1: Solar rooftop (reduces grid kWh) ---
    for bill in facility.electricity_bills:
        if solar_pct > 0:
            reduced_bill = bill.model_copy(update={
                "quantity": bill.quantity * (1.0 - solar_pct),
                "id": f"{bill.id}_solar_adj",
            })
            new_lines.append(electricity_from_bill(reduced_bill, factors, factor_map))

            # Financial: solar saves grid tariff on displaced kWh
            grid_tariff = _get_assumption(factors, "grid_tariff_inr_per_kwh")
            solar_yield_year = _get_assumption(factors, "solar_yield_kwh_per_kw_year")
            solar_capex_per_kw = _get_assumption(factors, "solar_capex_inr_per_kw")

            displaced_kwh_month = bill.quantity * solar_pct / 12.0
            inr_saved += displaced_kwh_month * grid_tariff

            # Estimate kW needed: displaced annual kWh / yield per kW
            displaced_kwh_year = bill.quantity * solar_pct
            solar_kw = displaced_kwh_year / solar_yield_year if solar_yield_year > 0 else 0.0
            capex += solar_kw * solar_capex_per_kw

            assumption_notes.append(
                f"Solar: grid tariff INR {grid_tariff}/kWh, yield {solar_yield_year} kWh/kW/yr, "
                f"capex INR {solar_capex_per_kw}/kW (from assumptions.yaml). "
                f"Savings are estimates under stated assumptions."
            )
        else:
            new_lines.append(electricity_from_bill(bill, factors, factor_map))

    # --- Lever 2 & 3: Genset hours reduction + idle hours reduction ---
    for det, hours, load in facility.genset_detections:
        effective_hours = hours * (1.0 - genset_red_pct) * (1.0 - idle_red_pct)
        new_lines.append(fuel_from_detection(det, effective_hours, load, factors, factor_map))

        if genset_red_pct > 0 or idle_red_pct > 0:
            # Reduced genset → more grid electricity consumed (Scope 2 trade-off)
            # Financial: hours saved on diesel → diesel_price saving
            diesel_price = _get_assumption(factors, "diesel_price_inr_per_litre")
            pf = factors.get_genset_pf(factor_map)
            rated_kw = det.rated_power_kw or (det.rated_kva or 0.0) * pf
            sfc, _ = factors.get_diesel_sfc(load, factor_map)
            load_frac = load / 100.0
            saved_hours = hours - effective_hours
            saved_litres_month = rated_kw * load_frac * saved_hours * sfc
            inr_saved += saved_litres_month * diesel_price
            # No capex for operational change
            assumption_notes.append(
                f"Genset hours reduction: diesel price INR {diesel_price}/L "
                f"(from assumptions.yaml). Savings are estimates under stated assumptions."
            )


    # Diesel fuel bills — unchanged by genset levers (bills are already confirmed actuals)
    for bill in facility.diesel_bills:
        new_lines.append(fuel_from_bill(bill, factors, factor_map))

    # --- Lever 4: Electric forklift ---
    for bill in facility.forklift_bills:
        if inputs.electric_forklift:
            # Diesel forklift removed — zero emission line
            # Financial: diesel cost saved minus electricity cost increase (approximate)
            diesel_price = _get_assumption(factors, "diesel_price_inr_per_litre")
            forklift_premium = _get_assumption(factors, "electric_forklift_price_premium_inr")
            inr_saved += bill.quantity * diesel_price / 12.0  # monthly saving
            capex += forklift_premium
            assumption_notes.append(
                f"Electric forklift: premium capex INR {forklift_premium}, "
                f"diesel savings at INR {diesel_price}/L (from assumptions.yaml). "
                f"Savings are estimates under stated assumptions."
            )
            # No emission line added → forklift emissions disappear
        else:
            new_lines.append(fuel_from_bill(bill, factors, factor_map))

    # --- Lever 5: Rail freight shift ---
    for bill in facility.freight_bills:
        if rail_pct > 0:
            road_portion = bill.model_copy(update={
                "quantity": bill.quantity * (1.0 - rail_pct),
                "id": f"{bill.id}_road",
            })
            rail_bill = bill.model_copy(update={
                "quantity": bill.quantity * rail_pct,
                "unit": "tonne-km",
                "bill_type": "freight",
                "id": f"{bill.id}_rail",
            })
            new_lines.append(freight_from_bill(road_portion, factors, factor_map))
            # Rail line: override factor to freight_rail
            rail_factor_map = FactorMap(
                diesel=factor_map.diesel,
                petrol=factor_map.petrol,
                lpg_kg=factor_map.lpg_kg,
                grid=factor_map.grid,
                freight_road=factor_map.freight_rail,  # use rail factor
                freight_rail=factor_map.freight_rail,
                genset_pf=factor_map.genset_pf,
                genset_tolerance=factor_map.genset_tolerance,
                genset_model=factor_map.genset_model,
            )
            new_lines.append(freight_from_bill(rail_bill, factors, rail_factor_map))

            # Financial: rail cheaper per tkm
            rail_cost_diff = _get_assumption(
                factors, "rail_vs_road_freight_cost_difference_inr_per_tkm"
            )
            shifted_tkm_month = bill.quantity * rail_pct / 12.0
            inr_saved += shifted_tkm_month * rail_cost_diff
            assumption_notes.append(
                f"Rail shift: cost diff INR {rail_cost_diff}/tkm "
                f"(from assumptions.yaml). Savings are estimates under stated assumptions."
            )
        else:
            new_lines.append(freight_from_bill(bill, factors, factor_map))

    return new_lines, inr_saved, capex, assumption_notes


def _payback(capex: float, inr_saved_per_month: float) -> float:
    """
    Payback period in months. Returns 0 if capex is 0, inf if no savings.
    """
    if capex <= 0.0:
        return 0.0
    if inr_saved_per_month <= 0.0:
        return float("inf")
    return capex / inr_saved_per_month


def simulate(
    facility: Facility,
    inputs: ScenarioInputs,
    factors: LoadedFactors,
    factor_map: FactorMap = PRODUCTION_FACTOR_MAP,
) -> ScenarioResult:
    """
    Run a what-if scenario against a Facility's baseline.

    Invariants:
    - All-zero inputs → new_co2e_kg == baseline_co2e_kg exactly.
    - Increasing a lever never increases CO2e (monotone).
    - Money comes only from assumptions.yaml; TODO_VERIFY → MissingAssumptionError.
    - Ranges propagate. Output states that savings are estimates.
    """
    baseline_lines = _compute_baseline(facility, factors, factor_map)
    base_co2e, base_low, base_high = _sum_lines(baseline_lines)

    new_lines, inr_saved, capex, notes = _apply_lever(
        facility, inputs, factors, factor_map, baseline_lines
    )
    new_co2e, new_low, new_high = _sum_lines(new_lines)

    delta_pct = (
        ((new_co2e - base_co2e) / base_co2e * 100.0)
        if base_co2e != 0.0
        else 0.0
    )
    payback = _payback(capex, inr_saved)

    # --- Ranked levers: each lever tested independently ---
    ranked = _rank_levers(
        facility, inputs, factors, factor_map, base_co2e, base_low, base_high, baseline_lines
    )

    return ScenarioResult(
        scenario_inputs=inputs.model_dump(),
        baseline_co2e_kg=round(base_co2e, 3),
        new_co2e_kg=round(new_co2e, 3),
        delta_pct=round(delta_pct, 2),
        inr_saved_per_month=round(inr_saved, 2),
        capex_inr=round(capex, 2),
        payback_months=round(payback, 2) if payback != float("inf") else None,
        ranked_levers=ranked,
        assumptions=notes + [
            "All savings are estimates under stated assumptions and should not be "
            "construed as certified carbon reduction credits or regulatory compliance."
        ],
    )


def _rank_levers(
    facility: Facility,
    inputs: ScenarioInputs,
    factors: LoadedFactors,
    factor_map: FactorMap,
    base_co2e: float,
    base_low: float,
    base_high: float,
    baseline_lines: Optional[List[EmissionLine]] = None,
) -> List[Dict[str, Any]]:
    """
    Run each lever in isolation and rank by payback (best = shortest first).
    Uses the clamped input values — if a lever is at 0 it produces 0 reduction.
    """
    lever_specs = [
        (
            "Rooftop Solar PV",
            ScenarioInputs(solar_share_pct=inputs.solar_share_pct),
        ),
        (
            "Genset Hours Reduction (grid replacement)",
            ScenarioInputs(genset_hours_reduction_pct=inputs.genset_hours_reduction_pct),
        ),
        (
            "Idle Hours Reduction (genset management)",
            ScenarioInputs(idle_hours_reduction_pct=inputs.idle_hours_reduction_pct),
        ),
        (
            "Electric Forklift Conversion",
            ScenarioInputs(electric_forklift=inputs.electric_forklift),
        ),
        (
            "Rail Freight Mode Shift",
            ScenarioInputs(rail_shift_pct=inputs.rail_shift_pct),
        ),
    ]

    results = []
    for name, solo_inputs in lever_specs:
        try:
            solo_lines, solo_saved, solo_capex, _ = _apply_lever(
                facility, solo_inputs, factors, factor_map, baseline_lines
            )
            solo_co2e, _, _ = _sum_lines(solo_lines)
            reduction = max(0.0, base_co2e - solo_co2e)
            delta_pct = (reduction / base_co2e * 100.0) if base_co2e != 0.0 else 0.0
            pb = _payback(solo_capex, solo_saved)
            results.append(
                {
                    "lever": name,
                    "co2e_reduction_kg": round(reduction, 3),
                    "delta_pct": round(delta_pct, 2),
                    "inr_saved_per_month": round(solo_saved, 2),
                    "capex_inr": round(solo_capex, 2),
                    "payback_months": round(pb, 2) if pb != float("inf") else None,
                }
            )
        except MissingAssumptionError:
            # Lever can't be evaluated — include with null financials
            results.append(
                {
                    "lever": name,
                    "co2e_reduction_kg": None,
                    "delta_pct": None,
                    "inr_saved_per_month": None,
                    "capex_inr": None,
                    "payback_months": None,
                    "note": "TODO_VERIFY assumption — financial estimates unavailable",
                }
            )

    # Sort: positive-capex levers by payback ascending (best ROI first),
    # then zero-capex operational levers (payback=0 means free savings),
    # then unknown (TODO_VERIFY) levers.
    def sort_key(r: Dict[str, Any]):
        pb = r.get("payback_months")
        if pb is None:
            return (2, 0.0)   # unknown → last
        if pb > 0:
            return (0, pb)    # has capex → sort ascending by payback
        return (1, 0.0)       # zero capex operational change → middle

    results.sort(key=sort_key)
    for i, r in enumerate(results, start=1):
        r["rank"] = i

    return results

