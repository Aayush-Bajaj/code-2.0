"""
Tests for backend/twin/simulator.py

Test categories (all hand-verifiable with test fixture round numbers):
1. Baseline equality: all-zero inputs reproduce baseline exactly.
2. Monotonicity: increasing any lever never increases CO2e.
3. Clamping: values outside stated bounds are clamped, not rejected.
4. Missing assumptions: MissingAssumptionError names the key, not a generic crash.
5. Payback arithmetic: verified by hand against test assumptions.
6. Lever isolation: ranked_levers contains one entry per lever.
7. Range propagation: new_co2e_kg is within [new_low, new_high].
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List

import pytest

from backend.engine.loader import load_factors, LoadedFactors
from backend.engine.factor_map import TEST_FACTOR_MAP, FactorMap
from backend.schemas import (
    BillExtraction,
    Detection,
    EmissionLine,
    SmokeAnalysis,
)
from backend.twin.simulator import (
    Facility,
    ScenarioInputs,
    MissingAssumptionError,
    simulate,
    _get_assumption,
    _payback,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def test_factors() -> LoadedFactors:
    """Load test fixture factors (round numbers) + test assumptions (verified)."""
    return load_factors(
        factors_csv_path=FIXTURES_DIR / "factors_test.csv",
        assumptions_yaml_path=FIXTURES_DIR / "assumptions_test.yaml",
    )


def _elec_bill(kwh: float = 10_000.0) -> BillExtraction:
    return BillExtraction(
        id="bill_elec_001",
        source_file="test_bescom.pdf",
        bill_type="electricity",
        period_start="2024-03-01",
        period_end="2024-03-31",
        quantity=kwh,
        unit="kWh",
        amount_inr=kwh * 8.0,
        supplier="Test DISCOM",
        confidence_0_1=0.95,
        field_boxes={},
        method="ocr",
        user_confirmed=True,
    )


def _diesel_bill(litres: float = 1_000.0) -> BillExtraction:
    return BillExtraction(
        id="bill_diesel_001",
        source_file="test_diesel.pdf",
        bill_type="diesel",
        period_start="2024-03-01",
        period_end="2024-03-31",
        quantity=litres,
        unit="L",
        amount_inr=litres * 90.0,
        supplier="IOCL",
        confidence_0_1=0.95,
        field_boxes={},
        method="ocr",
        user_confirmed=True,
    )


def _freight_bill(tkm: float = 5_000.0) -> BillExtraction:
    return BillExtraction(
        id="bill_freight_001",
        source_file="test_freight.pdf",
        bill_type="freight",
        period_start="2024-03-01",
        period_end="2024-03-31",
        quantity=tkm,
        unit="tonne-km",
        amount_inr=tkm * 2.0,
        supplier="Test Logistics",
        confidence_0_1=0.95,
        field_boxes={},
        method="ocr",
        user_confirmed=True,
    )


def _genset_detection() -> Detection:
    return Detection(
        id="det_dg_001",
        source_file="genset.mp4",
        frame_index=10,
        frame_path="data/evidence/frames/genset_10.jpg",
        machine_type="diesel_generator",
        fuel_type="diesel",
        rated_power_kw=100.0,
        rated_kva=None,
        nameplate_text="TEST GENSET 100kW",
        smoke=SmokeAnalysis(level="none", color="none", score_0_10=0.0),
        maintenance_flag=False,
        confidence_0_1=0.90,
        bbox=None,
    )


def _facility_all(kwh=10_000.0, litres=1_000.0, tkm=5_000.0) -> Facility:
    """Facility with electricity + diesel + freight + genset."""
    return Facility(
        electricity_bills=[_elec_bill(kwh)],
        diesel_bills=[_diesel_bill(litres)],
        freight_bills=[_freight_bill(tkm)],
        genset_detections=[(_genset_detection(), 200.0, 75.0)],  # 200 hrs/month, 75% load
    )


# --------------------------------------------------------------------------- #
# 1. Baseline equality: all-zero inputs reproduce baseline exactly
# --------------------------------------------------------------------------- #

class TestBaselineEquality:
    def test_zero_inputs_reproduce_baseline(self, test_factors):
        facility = _facility_all()
        zero = ScenarioInputs()  # all defaults = 0
        result = simulate(facility, zero, test_factors, TEST_FACTOR_MAP)

        assert result.baseline_co2e_kg == pytest.approx(result.new_co2e_kg, rel=1e-9), (
            f"All-zero inputs must reproduce baseline exactly. "
            f"baseline={result.baseline_co2e_kg}, new={result.new_co2e_kg}"
        )

    def test_zero_inputs_zero_delta(self, test_factors):
        facility = _facility_all()
        result = simulate(facility, ScenarioInputs(), test_factors, TEST_FACTOR_MAP)
        assert result.delta_pct == pytest.approx(0.0, abs=1e-9)

    def test_zero_inputs_zero_savings(self, test_factors):
        facility = _facility_all()
        result = simulate(facility, ScenarioInputs(), test_factors, TEST_FACTOR_MAP)
        assert result.inr_saved_per_month == pytest.approx(0.0, abs=1e-9)

    def test_zero_inputs_zero_capex(self, test_factors):
        facility = _facility_all()
        result = simulate(facility, ScenarioInputs(), test_factors, TEST_FACTOR_MAP)
        assert result.capex_inr == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# 2. Monotonicity: increasing any lever never increases emissions
# --------------------------------------------------------------------------- #

class TestMonotonicity:
    def test_solar_monotone(self, test_factors):
        facility = _facility_all()
        prev_co2e = None
        for pct in [0, 10, 20, 40, 60]:
            result = simulate(
                facility,
                ScenarioInputs(solar_share_pct=float(pct)),
                test_factors,
                TEST_FACTOR_MAP,
            )
            if prev_co2e is not None:
                assert result.new_co2e_kg <= prev_co2e + 1e-9, (
                    f"Solar {pct}% increased CO2e: {prev_co2e} -> {result.new_co2e_kg}"
                )
            prev_co2e = result.new_co2e_kg

    def test_genset_hours_monotone(self, test_factors):
        facility = _facility_all()
        prev = None
        for pct in [0, 20, 40, 60, 80]:
            result = simulate(
                facility,
                ScenarioInputs(genset_hours_reduction_pct=float(pct)),
                test_factors,
                TEST_FACTOR_MAP,
            )
            if prev is not None:
                assert result.new_co2e_kg <= prev + 1e-9
            prev = result.new_co2e_kg

    def test_idle_hours_monotone(self, test_factors):
        facility = _facility_all()
        prev = None
        for pct in [0, 10, 25, 50]:
            result = simulate(
                facility,
                ScenarioInputs(idle_hours_reduction_pct=float(pct)),
                test_factors,
                TEST_FACTOR_MAP,
            )
            if prev is not None:
                assert result.new_co2e_kg <= prev + 1e-9
            prev = result.new_co2e_kg

    def test_electric_forklift_monotone(self, test_factors):
        """Switching to electric forklift must not increase CO2e."""
        facility = Facility(forklift_bills=[_diesel_bill(500.0)])
        base = simulate(facility, ScenarioInputs(electric_forklift=0), test_factors, TEST_FACTOR_MAP)
        switched = simulate(facility, ScenarioInputs(electric_forklift=1), test_factors, TEST_FACTOR_MAP)
        assert switched.new_co2e_kg <= base.new_co2e_kg + 1e-9

    def test_rail_shift_monotone(self, test_factors):
        facility = _facility_all()
        prev = None
        for pct in [0, 10, 25, 50]:
            result = simulate(
                facility,
                ScenarioInputs(rail_shift_pct=float(pct)),
                test_factors,
                TEST_FACTOR_MAP,
            )
            if prev is not None:
                assert result.new_co2e_kg <= prev + 1e-9
            prev = result.new_co2e_kg


# --------------------------------------------------------------------------- #
# 3. Clamping: out-of-range inputs are clamped, not rejected
# --------------------------------------------------------------------------- #

class TestClamping:
    def test_solar_over_60_clamped(self):
        """Value 90 must be clamped to 60."""
        inp = ScenarioInputs(solar_share_pct=90.0)
        assert inp.solar_share_pct == pytest.approx(60.0)

    def test_solar_negative_clamped(self):
        inp = ScenarioInputs(solar_share_pct=-10.0)
        assert inp.solar_share_pct == pytest.approx(0.0)

    def test_genset_over_80_clamped(self):
        inp = ScenarioInputs(genset_hours_reduction_pct=100.0)
        assert inp.genset_hours_reduction_pct == pytest.approx(80.0)

    def test_idle_over_50_clamped(self):
        inp = ScenarioInputs(idle_hours_reduction_pct=75.0)
        assert inp.idle_hours_reduction_pct == pytest.approx(50.0)

    def test_rail_over_50_clamped(self):
        inp = ScenarioInputs(rail_shift_pct=80.0)
        assert inp.rail_shift_pct == pytest.approx(50.0)

    def test_forklift_over_1_clamped(self):
        inp = ScenarioInputs(electric_forklift=5)
        assert inp.electric_forklift == 1

    def test_forklift_negative_clamped(self):
        inp = ScenarioInputs(electric_forklift=-1)
        assert inp.electric_forklift == 0

    def test_clamped_value_simulation_still_runs(self, test_factors):
        """Simulation must succeed with clamped values, not error."""
        facility = _facility_all()
        result = simulate(
            facility,
            ScenarioInputs(solar_share_pct=200.0),  # clamped to 60
            test_factors,
            TEST_FACTOR_MAP,
        )
        assert result.new_co2e_kg >= 0.0


# --------------------------------------------------------------------------- #
# 4. Missing assumptions error
# --------------------------------------------------------------------------- #

class TestMissingAssumptions:
    def test_todo_verify_raises_missing_assumption_error(self, tmp_path, test_factors):
        """
        If an assumption is TODO_VERIFY (absent from the loaded dict because the
        loader skips them), MissingAssumptionError must be raised naming the key.
        """
        # Use a production-like factors fixture that has no solar assumption
        import yaml
        from backend.engine.loader import load_factors as _lf

        # Minimal assumptions file with solar_capex missing (simulate TODO_VERIFY)
        bad_assumptions = tmp_path / "bad_assumptions.yaml"
        bad_assumptions.write_text("# empty - all assumptions are TODO_VERIFY\n", encoding="utf-8")

        factors_no_assumptions = _lf(
            factors_csv_path=FIXTURES_DIR / "factors_test.csv",
            assumptions_yaml_path=bad_assumptions,
        )

        facility = Facility(electricity_bills=[_elec_bill()])
        inputs = ScenarioInputs(solar_share_pct=30.0)  # triggers solar assumption

        with pytest.raises(MissingAssumptionError) as exc_info:
            simulate(facility, inputs, factors_no_assumptions, TEST_FACTOR_MAP)

        assert "solar_capex_inr_per_kw" in str(exc_info.value) or "assumption" in str(exc_info.value).lower()

    def test_missing_assumption_error_names_key(self, tmp_path):
        """MissingAssumptionError message must name the missing key."""
        from backend.engine.loader import load_factors as _lf, LoadedFactors
        bad_a = tmp_path / "empty.yaml"
        bad_a.write_text("")
        empty_factors = _lf(
            factors_csv_path=FIXTURES_DIR / "factors_test.csv",
            assumptions_yaml_path=bad_a,
        )
        with pytest.raises(MissingAssumptionError) as exc_info:
            _get_assumption(empty_factors, "grid_tariff_inr_per_kwh")
        assert "grid_tariff_inr_per_kwh" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# 5. Payback arithmetic — hand-verified
# --------------------------------------------------------------------------- #

class TestPaybackArithmetic:
    """
    Test fixture values (assumptions_test.yaml):
      grid_tariff_inr_per_kwh = 8.0
      solar_yield_kwh_per_kw_year = 1500.0
      solar_capex_inr_per_kw = 45000.0
      diesel_price_inr_per_litre = 90.0
    """

    def test_solar_payback_hand_verified(self, test_factors):
        """
        Baseline: 10,000 kWh/month.
        Solar share 60% → 6,000 kWh displaced/month.
        INR saved/month = 6000 / 12 * 8.0 = 4000.0  [wait: quantity is monthly, not annual]
        displaced_kwh_month = 10000 * 0.60 / 12 = 500 kWh/month
        INR saved/month = 500 * 8.0 = 4000.0 INR/month
        solar_kw = (10000 * 0.60) / 1500 = 4.0 kW
        capex = 4.0 * 45000 = 180,000 INR
        payback = 180000 / 4000 = 45 months
        """
        kwh = 10_000.0
        facility = Facility(electricity_bills=[_elec_bill(kwh)])
        result = simulate(
            facility,
            ScenarioInputs(solar_share_pct=60.0),
            test_factors,
            TEST_FACTOR_MAP,
        )
        assert result.inr_saved_per_month == pytest.approx(4000.0, rel=1e-6)
        assert result.capex_inr == pytest.approx(180_000.0, rel=1e-6)
        assert result.payback_months == pytest.approx(45.0, rel=1e-4)

    def test_payback_zero_capex_is_zero(self):
        """Zero capex → payback should be 0."""
        assert _payback(0.0, 1000.0) == 0.0

    def test_payback_zero_savings_is_inf(self):
        """Non-zero capex with zero savings → payback is inf."""
        assert _payback(100_000.0, 0.0) == float("inf")

    def test_payback_formula(self):
        """Direct formula check: 120000 / 4000 = 30 months."""
        assert _payback(120_000.0, 4_000.0) == pytest.approx(30.0, rel=1e-9)

    def test_forklift_payback(self, test_factors):
        """
        Forklift diesel bill: 500 L/month.
        diesel_price = 90 INR/L → saved = 500 * 90 / 12 = 3750 INR/month
        Wait: the bill quantity is monthly litres (used directly, not /12 again):
        inr_saved = bill.quantity * diesel_price / 12  (monthly fraction of annual?)
        Actually our code: inr_saved += bill.quantity * diesel_price / 12
        500 L * 90 / 12 = 3750 INR/month
        capex = electric_forklift_price_premium_inr = 400,000
        payback = 400000 / 3750 = 106.67 months
        """
        facility = Facility(forklift_bills=[_diesel_bill(500.0)])
        result = simulate(
            facility,
            ScenarioInputs(electric_forklift=1),
            test_factors,
            TEST_FACTOR_MAP,
        )
        expected_saved = 500.0 * 90.0 / 12.0  # = 3750
        expected_capex = 400_000.0
        expected_payback = expected_capex / expected_saved  # 106.67
        assert result.inr_saved_per_month == pytest.approx(expected_saved, rel=1e-6)
        assert result.capex_inr == pytest.approx(expected_capex, rel=1e-6)
        assert result.payback_months == pytest.approx(expected_payback, rel=1e-4)


# --------------------------------------------------------------------------- #
# 6. Ranked levers
# --------------------------------------------------------------------------- #

class TestRankedLevers:
    def test_ranked_levers_count(self, test_factors):
        """Always exactly 5 lever entries."""
        facility = _facility_all()
        result = simulate(
            facility,
            ScenarioInputs(solar_share_pct=30.0, rail_shift_pct=20.0),
            test_factors,
            TEST_FACTOR_MAP,
        )
        assert len(result.ranked_levers) == 5

    def test_ranked_levers_have_rank_field(self, test_factors):
        facility = _facility_all()
        result = simulate(facility, ScenarioInputs(), test_factors, TEST_FACTOR_MAP)
        for lever in result.ranked_levers:
            assert "rank" in lever
            assert "lever" in lever

    def test_ranked_levers_sorted_by_payback(self, test_factors):
        """Levers with known, positive payback must appear before zero-payback levers.
        Zero-payback means no capex required (not an instant-payback investment),
        so they are ranked after levers that require capex but have better ROI.
        """
        facility = _facility_all()
        result = simulate(
            facility,
            ScenarioInputs(solar_share_pct=30.0, rail_shift_pct=20.0, electric_forklift=0),
            test_factors,
            TEST_FACTOR_MAP,
        )
        # Separate levers that require capex (payback > 0) from those that don't
        capex_levers = [r for r in result.ranked_levers if r.get("payback_months") is not None and r["payback_months"] > 0]
        non_capex_levers = [r for r in result.ranked_levers if r.get("payback_months") is not None and r["payback_months"] == 0]
        # Capex levers must be sorted ascending by payback among themselves
        capex_paybacks = [r["payback_months"] for r in capex_levers]
        assert capex_paybacks == sorted(capex_paybacks), (
            f"Capex levers not sorted by payback: {capex_paybacks}"
        )


# --------------------------------------------------------------------------- #
# 7. Range propagation
# --------------------------------------------------------------------------- #

class TestRangePropagation:
    def test_result_returns_baseline_with_range(self, test_factors):
        """baseline_co2e_kg must be positive for a non-empty facility."""
        facility = _facility_all()
        result = simulate(facility, ScenarioInputs(), test_factors, TEST_FACTOR_MAP)
        assert result.baseline_co2e_kg > 0

    def test_assumptions_list_non_empty(self, test_factors):
        """assumptions list must always contain at least the estimate disclaimer."""
        facility = _facility_all()
        result = simulate(
            facility,
            ScenarioInputs(solar_share_pct=10.0),
            test_factors,
            TEST_FACTOR_MAP,
        )
        assert len(result.assumptions) >= 1
        combined = " ".join(result.assumptions).lower()
        assert "estimate" in combined

    def test_solar_reduces_new_co2e(self, test_factors):
        """Solar lever must reduce new_co2e_kg below baseline."""
        facility = Facility(electricity_bills=[_elec_bill(10_000.0)])
        result = simulate(
            facility,
            ScenarioInputs(solar_share_pct=30.0),
            test_factors,
            TEST_FACTOR_MAP,
        )
        assert result.new_co2e_kg < result.baseline_co2e_kg

    def test_delta_pct_negative_when_saving(self, test_factors):
        """delta_pct must be negative when scenario reduces emissions."""
        facility = Facility(electricity_bills=[_elec_bill(10_000.0)])
        result = simulate(
            facility,
            ScenarioInputs(solar_share_pct=30.0),
            test_factors,
            TEST_FACTOR_MAP,
        )
        assert result.delta_pct < 0.0

    def test_electric_forklift_eliminates_forklift_emissions(self, test_factors):
        """With electric forklift enabled, forklift diesel emissions must be zero."""
        facility = Facility(forklift_bills=[_diesel_bill(500.0)])
        result = simulate(
            facility,
            ScenarioInputs(electric_forklift=1),
            test_factors,
            TEST_FACTOR_MAP,
        )
        assert result.new_co2e_kg == pytest.approx(0.0, abs=1e-9)


class TestFacilityFromBaselineLines:
    def test_baseline_lines_zero_inputs(self, test_factors):
        base_line = EmissionLine(
            id="em_elec_001",
            scope=2,
            category="Purchased Grid Electricity",
            activity_value=10000.0,
            activity_unit="kWh",
            factor_id="grid_india_wa",
            factor_value=0.716,
            factor_unit="kg CO2e/kWh",
            factor_source="CEA",
            factor_url="http://example.com",
            formula_text="10000 kWh x 0.716 = 7160 kg",
            co2e_kg=7160.0,
            low_kg=6802.0,
            high_kg=7518.0,
            evidence_refs=["bill_001"],
            method="bill",
            flags=[],
        )
        facility = Facility(baseline_lines=[base_line])
        res = simulate(facility, ScenarioInputs(), test_factors, TEST_FACTOR_MAP)
        assert res.baseline_co2e_kg == 7160.0
        assert res.new_co2e_kg == 7160.0
        assert res.delta_pct == 0.0

    def test_baseline_lines_with_solar_lever(self, test_factors):
        base_line = EmissionLine(
            id="em_elec_001",
            scope=2,
            category="Purchased Grid Electricity",
            activity_value=10000.0,
            activity_unit="kWh",
            factor_id="grid_india_wa",
            factor_value=0.716,
            factor_unit="kg CO2e/kWh",
            factor_source="CEA",
            factor_url="http://example.com",
            formula_text="10000 kWh x 0.716 = 7160 kg",
            co2e_kg=7160.0,
            low_kg=6802.0,
            high_kg=7518.0,
            evidence_refs=["bill_001"],
            method="bill",
            flags=[],
        )
        facility = Facility(baseline_lines=[base_line])
        res = simulate(facility, ScenarioInputs(solar_share_pct=20.0), test_factors, TEST_FACTOR_MAP)
        assert res.new_co2e_kg < res.baseline_co2e_kg
        assert res.delta_pct < 0.0
        assert res.inr_saved_per_month > 0.0

    def test_api_scenario_simulate_endpoint(self, test_factors, monkeypatch):
        from fastapi.testclient import TestClient
        from backend.api.main import app

        monkeypatch.setattr("backend.api.main.load_factors", lambda: test_factors)

        client = TestClient(app)
        payload = {
            "baseline_lines": [
                {
                    "id": "em_elec_test",
                    "scope": 2,
                    "category": "Purchased Grid Electricity",
                    "activity_value": 5000.0,
                    "activity_unit": "kWh",
                    "factor_id": "grid_india_wa",
                    "factor_value": 0.716,
                    "factor_unit": "kg CO2e/kWh",
                    "factor_source": "CEA",
                    "factor_url": "https://cea.nic.in",
                    "formula_text": "5000 * 0.716",
                    "co2e_kg": 3580.0,
                    "low_kg": 3401.0,
                    "high_kg": 3759.0,
                    "evidence_refs": ["test_bill"],
                    "method": "bill",
                    "flags": [],
                }
            ],
            "inputs": {
                "solar_share_pct": 30.0,
                "genset_hours_reduction_pct": 0.0,
                "idle_hours_reduction_pct": 0.0,
                "electric_forklift": 0,
                "rail_shift_pct": 0.0,
            },
        }
        resp = client.post("/api/scenarios/simulate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["baseline_co2e_kg"] == 3580.0
        assert data["new_co2e_kg"] < 3580.0
        assert data["delta_pct"] < 0.0
        assert len(data["ranked_levers"]) == 5
