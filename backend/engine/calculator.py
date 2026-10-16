"""
Deterministic emission calculation engine for Carbon Passport.

Rules:
- NO LLM calls. Pure Python deterministic arithmetic.
- All numbers originate strictly from loaded factors (data/factors/factors.csv).
- All factor_id lookups go through factor_map.py — no IDs hardcoded here.
- Every EmissionLine contains at least one evidence_ref.
- Round only at display time, never in calculation.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from backend.schemas import Detection, BillExtraction, EmissionLine
from backend.engine.exceptions import NeedsUserInput, UnitError
from backend.engine.loader import LoadedFactors
from backend.engine.factor_map import FactorMap, PRODUCTION_FACTOR_MAP
from backend.engine.units import (
    normalise_electricity_unit,
    normalise_fuel_unit,
    normalise_freight_unit,
)
from backend.engine.uncertainty import (
    compute_bill_uncertainty,
    compute_detection_uncertainty,
)


def electricity_from_bill(
    bill: BillExtraction,
    factors: LoadedFactors,
    factor_map: FactorMap = PRODUCTION_FACTOR_MAP,
) -> EmissionLine:
    """
    Compute Scope 2 grid electricity emissions from a confirmed bill.
    Formula: kWh * India grid emission factor.
    Note: Grid factor is CO2 only (CEA methodology), recorded in category.
    """
    kwh, act_unit = normalise_electricity_unit(bill.quantity, bill.unit)
    ef = factors.get_factor(factor_map.grid)

    co2e = kwh * ef.value
    low_kg, high_kg, flags = compute_bill_uncertainty(co2e, bill.confidence_0_1)

    formula_text = f"{kwh} kWh x {ef.value} kg CO2e/kWh = {co2e} kg"

    evidence: List[str] = [bill.source_file]
    if bill.field_boxes:
        evidence.append(f"field_boxes:{list(bill.field_boxes.keys())}")

    return EmissionLine(
        id=f"em_elec_{uuid.uuid4().hex[:8]}",
        scope=2,
        category="Purchased Electricity (Grid) [CO2 only]",
        activity_value=kwh,
        activity_unit=act_unit,
        factor_id=ef.factor_id,
        factor_value=ef.value,
        factor_unit=ef.unit,
        factor_source=ef.source_name,
        factor_url=ef.source_url,
        formula_text=formula_text,
        co2e_kg=co2e,
        low_kg=low_kg,
        high_kg=high_kg,
        evidence_refs=evidence,
        method="bill",
        flags=flags,
    )


def fuel_from_bill(
    bill: BillExtraction,
    factors: LoadedFactors,
    factor_map: FactorMap = PRODUCTION_FACTOR_MAP,
) -> EmissionLine:
    """
    Compute Scope 1 stationary combustion emissions from a diesel bill.
    Formula: Litres * diesel emission factor.
    """
    litres, act_unit = normalise_fuel_unit(bill.quantity, bill.unit)
    ef = factors.get_factor(factor_map.diesel)

    co2e = litres * ef.value
    low_kg, high_kg, flags = compute_bill_uncertainty(co2e, bill.confidence_0_1)

    formula_text = f"{litres} L x {ef.value} kg CO2e/L = {co2e} kg"

    evidence: List[str] = [bill.source_file]
    if bill.field_boxes:
        evidence.append(f"field_boxes:{list(bill.field_boxes.keys())}")

    return EmissionLine(
        id=f"em_diesel_{uuid.uuid4().hex[:8]}",
        scope=1,
        category="Stationary Combustion (Diesel)",
        activity_value=litres,
        activity_unit=act_unit,
        factor_id=ef.factor_id,
        factor_value=ef.value,
        factor_unit=ef.unit,
        factor_source=ef.source_name,
        factor_url=ef.source_url,
        formula_text=formula_text,
        co2e_kg=co2e,
        low_kg=low_kg,
        high_kg=high_kg,
        evidence_refs=evidence,
        method="bill",
        flags=flags,
    )


def freight_from_bill(
    bill: BillExtraction,
    factors: LoadedFactors,
    factor_map: FactorMap = PRODUCTION_FACTOR_MAP,
) -> EmissionLine:
    """
    Compute Scope 3 freight transport emissions from a freight bill.
    Formula: tonne-km * freight factor.
    """
    tkm, act_unit = normalise_freight_unit(bill.quantity, bill.unit)
    ef = factors.get_factor(factor_map.freight_road)

    co2e = tkm * ef.value
    low_kg, high_kg, flags = compute_bill_uncertainty(co2e, bill.confidence_0_1)

    formula_text = f"{tkm} tonne-km x {ef.value} kg CO2e/tonne-km = {co2e} kg"

    evidence: List[str] = [bill.source_file]
    if bill.field_boxes:
        evidence.append(f"field_boxes:{list(bill.field_boxes.keys())}")

    return EmissionLine(
        id=f"em_freight_{uuid.uuid4().hex[:8]}",
        scope=3,
        category="Upstream Transportation & Freight",
        activity_value=tkm,
        activity_unit=act_unit,
        factor_id=ef.factor_id,
        factor_value=ef.value,
        factor_unit=ef.unit,
        factor_source=ef.source_name,
        factor_url=ef.source_url,
        formula_text=formula_text,
        co2e_kg=co2e,
        low_kg=low_kg,
        high_kg=high_kg,
        evidence_refs=evidence,
        method="bill",
        flags=flags,
    )


def fuel_from_detection(
    detection: Detection,
    hours_per_month: Optional[float],
    load_pct: Optional[float],
    factors: LoadedFactors,
    factor_map: FactorMap = PRODUCTION_FACTOR_MAP,
) -> EmissionLine:
    """
    Compute Scope 1 diesel generator emissions from visual machine detection.

    Formula:
      rated_kw * load_fraction * hours * SFC(load_pct) * diesel_factor

    Invariants:
    - hours_per_month and load_pct are mandatory USER INPUTS (never guessed from video).
    - If only kVA is known, kW = kVA * PF (read from factors.csv, not hardcoded).
    - SFC data only exists at 75% and 100% load. Below 75%, clamps to 75% SFC
      and adds flag 'load_below_datasheet_range'.
    """
    missing: List[str] = []
    if hours_per_month is None:
        missing.append("hours_per_month")
    if load_pct is None:
        missing.append("load_pct")
    if missing:
        raise NeedsUserInput(missing)

    if hours_per_month < 0:
        raise ValueError("hours_per_month cannot be negative.")
    if not (0.0 <= load_pct <= 100.0):
        raise ValueError("load_pct must be between 0 and 100.")

    # Read power factor from factors.csv — never hardcoded
    pf = factors.get_genset_pf(factor_map)

    # Determine rated kW
    power_explanation = ""
    if detection.rated_power_kw is not None and detection.rated_power_kw > 0:
        rated_kw = float(detection.rated_power_kw)
        kw_text = f"{rated_kw} kW"
    elif detection.rated_kva is not None and detection.rated_kva > 0:
        rated_kw = float(detection.rated_kva) * pf
        kw_text = f"{rated_kw} kW (converted from {detection.rated_kva} kVA x {pf} power factor)"
        power_explanation = f" [kVA * {pf} PF applied]"
    else:
        raise ValueError("Detection must specify either rated_power_kw or rated_kva.")

    # SFC lookup (only 75%/100% datasheet points; flags if below range)
    sfc, sfc_flags = factors.get_diesel_sfc(load_pct, factor_map)
    load_fraction = load_pct / 100.0
    estimated_litres = rated_kw * load_fraction * hours_per_month * sfc

    ef = factors.get_factor(factor_map.diesel)
    co2e = estimated_litres * ef.value

    # Read tolerance from factors.csv
    sfc_tolerance = factors.get_genset_tolerance(factor_map)

    smoke_score = detection.smoke.score_0_10 if detection.smoke else 0.0
    smoke_color = detection.smoke.color if detection.smoke else "none"
    confidence = detection.confidence_0_1 if detection.confidence_0_1 is not None else 1.0

    # Closure so uncertainty module can call sfc lookup for boundary evaluation
    def sfc_at(pct: float):
        return factors.get_diesel_sfc(pct, factor_map)

    low_kg, high_kg, unc_flags = compute_detection_uncertainty(
        kw=rated_kw,
        hours=hours_per_month,
        load_pct=load_pct,
        sfc_func=sfc_at,
        ef_value=ef.value,
        sfc_tolerance=sfc_tolerance,
        sfc_extra_flags=sfc_flags,
        smoke_score=smoke_score,
        smoke_color=smoke_color,
        detection_confidence=confidence,
    )

    all_flags = list(unc_flags)
    if detection.maintenance_flag:
        all_flags.append("maintenance_flag_active")

    formula_text = (
        f"{kw_text} x {load_pct}% load x {hours_per_month} hrs x {sfc:.4f} L/kWh x "
        f"{ef.value} kg CO2e/L = {co2e} kg{power_explanation}"
    )

    evidence: List[str] = [
        detection.source_file,
        detection.frame_path,
        f"user_input:hours={hours_per_month},load_pct={load_pct}",
    ]

    return EmissionLine(
        id=f"em_det_dg_{uuid.uuid4().hex[:8]}",
        scope=1,
        category="Stationary Combustion (Diesel Genset Estimate)",
        activity_value=estimated_litres,
        activity_unit="L",
        factor_id=ef.factor_id,
        factor_value=ef.value,
        factor_unit=ef.unit,
        factor_source=ef.source_name,
        factor_url=ef.source_url,
        formula_text=formula_text,
        co2e_kg=co2e,
        low_kg=low_kg,
        high_kg=high_kg,
        evidence_refs=evidence,
        method="video_estimate",
        flags=all_flags,
    )


def reconcile(video_line: EmissionLine, bill_line: EmissionLine) -> EmissionLine:
    """
    Reconcile a video-estimated generator footprint against an audited fuel bill.

    Rules:
    - Compute percent difference between video estimate and bill.
    - If diff > 25%, add flag 'video_bill_mismatch'.
    - The bill figure remains the primary source of truth (co2e_kg = bill_line.co2e_kg).
    - The video estimate is displayed as a cross-check in formula_text.
    - Resulting method is 'reconciled'.
    """
    if bill_line.co2e_kg == 0.0:
        pct_diff = 0.0 if video_line.co2e_kg == 0.0 else 100.0
    else:
        pct_diff = abs(video_line.co2e_kg - bill_line.co2e_kg) / bill_line.co2e_kg * 100.0

    flags = list(bill_line.flags)
    if pct_diff > 25.0:
        flags.append("video_bill_mismatch")

    # Combine unique evidence refs from both
    seen = set()
    combined_evidence: List[str] = []
    for ref in bill_line.evidence_refs + video_line.evidence_refs:
        if ref not in seen:
            seen.add(ref)
            combined_evidence.append(ref)

    formula_text = (
        f"Reconciled: Primary Bill {bill_line.co2e_kg} kg CO2e "
        f"[Cross-check Video Estimate: {video_line.co2e_kg} kg CO2e, delta: {pct_diff:.1f}%]"
    )

    return EmissionLine(
        id=f"em_reconciled_{uuid.uuid4().hex[:8]}",
        scope=bill_line.scope,
        category=bill_line.category,
        activity_value=bill_line.activity_value,
        activity_unit=bill_line.activity_unit,
        factor_id=bill_line.factor_id,
        factor_value=bill_line.factor_value,
        factor_unit=bill_line.factor_unit,
        factor_source=bill_line.factor_source,
        factor_url=bill_line.factor_url,
        formula_text=formula_text,
        co2e_kg=bill_line.co2e_kg,
        low_kg=bill_line.low_kg,
        high_kg=bill_line.high_kg,
        evidence_refs=combined_evidence,
        method="reconciled",
        flags=flags,
    )


def totals(lines: List[EmissionLine]) -> Dict[str, Any]:
    """
    Sum emissions by scope (1, 2, 3) with low/high ranges, plus grand total with range.
    Invariant: grand_total == sum of scope totals.
    """
    by_scope: Dict[int, Dict[str, float]] = {
        1: {"co2e_kg": 0.0, "low_kg": 0.0, "high_kg": 0.0},
        2: {"co2e_kg": 0.0, "low_kg": 0.0, "high_kg": 0.0},
        3: {"co2e_kg": 0.0, "low_kg": 0.0, "high_kg": 0.0},
    }

    grand_co2e = 0.0
    grand_low = 0.0
    grand_high = 0.0

    for line in lines:
        scope = line.scope
        if scope in by_scope:
            by_scope[scope]["co2e_kg"] += line.co2e_kg
            by_scope[scope]["low_kg"] += line.low_kg
            by_scope[scope]["high_kg"] += line.high_kg

        grand_co2e += line.co2e_kg
        grand_low += line.low_kg
        grand_high += line.high_kg

    return {
        "scope_1": by_scope[1],
        "scope_2": by_scope[2],
        "scope_3": by_scope[3],
        "grand_total": {
            "co2e_kg": grand_co2e,
            "low_kg": grand_low,
            "high_kg": grand_high,
        },
    }
