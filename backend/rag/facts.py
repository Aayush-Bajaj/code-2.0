"""
backend/rag/facts.py — Locked Facts Object builder.

Constructs an immutable JSON structure from engine EmissionLines, calculated scope totals,
uncertainty ranges, operational maintenance flags, and optional ScenarioResult.
Assigns a deterministic, unique identifier to EVERY number (e.g. line_1.co2e_kg, total.scope1.low_kg)
and maps IDs back to evidence line IDs so the UI and audit layers have 100% traceability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from backend.schemas import EmissionLine, ScenarioResult


@dataclass(frozen=True)
class FactValue:
    id: str
    number: float
    unit: str
    display_str: str
    evidence_line_id: Optional[str] = None
    description: str = ""


class FactsRegistry:
    """
    Locked facts registry containing all numbers with unique identifiers,
    units, and evidence line linkages.
    """
    def __init__(
        self,
        facility_name: str,
        reporting_period: str,
        emission_lines: List[EmissionLine],
        scenario_result: Optional[ScenarioResult] = None,
    ):
        self.facility_name = facility_name
        self.reporting_period = reporting_period
        self.emission_lines = emission_lines
        self.scenario_result = scenario_result
        self._facts: Dict[str, FactValue] = {}
        self._build_facts()

    def _add_fact(
        self,
        fact_id: str,
        number: float,
        unit: str,
        display_fmt: str = "{:,.2f}",
        evidence_line_id: Optional[str] = None,
        description: str = "",
    ):
        disp = display_fmt.format(number)
        fact = FactValue(
            id=fact_id,
            number=number,
            unit=unit,
            display_str=f"{disp} {unit}".strip(),
            evidence_line_id=evidence_line_id,
            description=description,
        )
        self._facts[fact_id] = fact

    def _build_facts(self):
        # 1. Totals accumulators by Scope
        s1_co2e, s1_low, s1_high = 0.0, 0.0, 0.0
        s2_co2e, s2_low, s2_high = 0.0, 0.0, 0.0
        s3_co2e, s3_low, s3_high = 0.0, 0.0, 0.0
        maint_flags_count = 0

        for idx, line in enumerate(self.emission_lines, start=1):
            s = str(line.scope).lower()
            co2e = float(line.co2e_kg)
            low = float(getattr(line, "low_kg", getattr(line, "co2e_range_low_kg", co2e * 0.95)))
            high = float(getattr(line, "high_kg", getattr(line, "co2e_range_high_kg", co2e * 1.05)))
            act_val = float(getattr(line, "activity_value", getattr(line, "activity_data", 0.0)))

            if "1" in s:
                s1_co2e += co2e
                s1_low += low
                s1_high += high
            elif "2" in s:
                s2_co2e += co2e
                s2_low += low
                s2_high += high
            elif "3" in s:
                s3_co2e += co2e
                s3_low += low
                s3_high += high

            flags = getattr(line, "flags", [])
            has_maint = getattr(line, "maintenance_flag", False) or any("maint" in str(f).lower() for f in flags)
            if has_maint:
                maint_flags_count += 1

            # Individual line facts (both line_N and line.<line.id> aliases)
            aliases = [f"line_{idx}", f"line_{line.id}"]
            for prefix in aliases:
                self._add_fact(
                    f"{prefix}.co2e_kg",
                    co2e,
                    "kg CO2e",
                    evidence_line_id=line.id,
                    description=f"{line.category} emissions",
                )
                self._add_fact(
                    f"{prefix}.low_kg",
                    low,
                    "kg CO2e",
                    evidence_line_id=line.id,
                    description=f"{line.category} lower uncertainty bound",
                )
                self._add_fact(
                    f"{prefix}.high_kg",
                    high,
                    "kg CO2e",
                    evidence_line_id=line.id,
                    description=f"{line.category} upper uncertainty bound",
                )
                self._add_fact(
                    f"{prefix}.activity_data",
                    act_val,
                    line.activity_unit,
                    evidence_line_id=line.id,
                    description=f"Activity volume for {line.category}",
                )


        # 2. Scope totals
        self._add_fact("total.scope1.co2e_kg", s1_co2e, "kg CO2e", description="Total Scope 1 direct emissions")
        self._add_fact("total.scope1.low_kg", s1_low, "kg CO2e", description="Scope 1 lower bound")
        self._add_fact("total.scope1.high_kg", s1_high, "kg CO2e", description="Scope 1 upper bound")

        self._add_fact("total.scope2.co2e_kg", s2_co2e, "kg CO2e", description="Total Scope 2 indirect electricity emissions")
        self._add_fact("total.scope2.low_kg", s2_low, "kg CO2e", description="Scope 2 lower bound")
        self._add_fact("total.scope2.high_kg", s2_high, "kg CO2e", description="Scope 2 upper bound")

        self._add_fact("total.scope3.co2e_kg", s3_co2e, "kg CO2e", description="Total Scope 3 value chain emissions")
        self._add_fact("total.scope3.low_kg", s3_low, "kg CO2e", description="Scope 3 lower bound")
        self._add_fact("total.scope3.high_kg", s3_high, "kg CO2e", description="Scope 3 upper bound")

        total_co2e = s1_co2e + s2_co2e + s3_co2e
        total_low = s1_low + s2_low + s3_low
        total_high = s1_high + s2_high + s3_high
        self._add_fact("total.all.co2e_kg", total_co2e, "kg CO2e", description="Gross enterprise emissions")
        self._add_fact("total.all.low_kg", total_low, "kg CO2e", description="Gross enterprise lower bound")
        self._add_fact("total.all.high_kg", total_high, "kg CO2e", description="Gross enterprise upper bound")

        # 3. Flags
        self._add_fact("flags.maintenance_flags_count", float(maint_flags_count), "flags", display_fmt="{:.0f}")

        # 4. Scenario facts (if present)
        if self.scenario_result:
            sr = self.scenario_result
            self._add_fact("scenario.baseline_co2e_kg", sr.baseline_co2e_kg, "kg CO2e")
            self._add_fact("scenario.new_co2e_kg", sr.new_co2e_kg, "kg CO2e")
            self._add_fact("scenario.delta_pct", sr.delta_pct, "%", display_fmt="{:.1f}")
            self._add_fact("scenario.inr_saved_per_month", sr.inr_saved_per_month, "INR/month")
            self._add_fact("scenario.capex_inr", sr.capex_inr, "INR")
            if sr.payback_months is not None:
                self._add_fact("scenario.payback_months", sr.payback_months, "months", display_fmt="{:.1f}")

            for idx, lever in enumerate(sr.ranked_levers, start=1):
                pfx = f"lever_{idx}"
                if "co2e_reduction_kg" in lever:
                    self._add_fact(f"{pfx}.co2e_reduction_kg", float(lever["co2e_reduction_kg"]), "kg CO2e")
                if "payback_months" in lever and lever["payback_months"] is not None:
                    self._add_fact(f"{pfx}.payback_months", float(lever["payback_months"]), "months", display_fmt="{:.1f}")
                if "capex_inr" in lever and lever["capex_inr"] is not None:
                    self._add_fact(f"{pfx}.capex_inr", float(lever["capex_inr"]), "INR")

    def get_fact(self, fact_id: str) -> Optional[FactValue]:
        return self._facts.get(fact_id)

    def all_facts(self) -> Dict[str, FactValue]:
        return dict(self._facts)

    def to_facts_json(self) -> Dict[str, Any]:
        """
        Export locked JSON structure for LLM prompts and snapshot audit.
        """
        facts_summary = {}
        for fid, fval in self._facts.items():
            facts_summary[fid] = {
                "value": fval.number,
                "unit": fval.unit,
                "display": fval.display_str,
                "evidence_ref": fval.evidence_line_id,
            }
        return {
            "facility_name": self.facility_name,
            "reporting_period": self.reporting_period,
            "facts": facts_summary,
        }

    def get_allowed_numbers(self) -> List[float]:
        """Returns all valid raw numbers present in the locked facts."""
        return [f.number for f in self._facts.values()]


def build_facts_registry(
    facility_name: str,
    reporting_period: str,
    emission_lines: List[EmissionLine],
    scenario_result: Optional[ScenarioResult] = None,
) -> FactsRegistry:
    return FactsRegistry(
        facility_name=facility_name,
        reporting_period=reporting_period,
        emission_lines=emission_lines,
        scenario_result=scenario_result,
    )
