"""
Unit and integration tests for the emission calculation engine (backend/engine).

Unit tests use tests/fixtures/factors_test.csv via TEST_FACTOR_MAP.
Round numbers make expected values hand-verifiable from plain arithmetic.

Integration test uses the real data/factors/factors.csv (Cummins C140D5P).
"""

from pathlib import Path
import pytest

from backend.schemas import Detection, BillExtraction, SmokeAnalysis
from backend.engine import (
    load_factors,
    electricity_from_bill,
    fuel_from_bill,
    freight_from_bill,
    fuel_from_detection,
    reconcile,
    totals,
    MissingFactorError,
    UnitError,
    NeedsUserInput,
)
from backend.engine.factor_map import TEST_FACTOR_MAP, PRODUCTION_FACTOR_MAP

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FACTORS_TEST_CSV = FIXTURES_DIR / "factors_test.csv"
ASSUMPTIONS_TEST_YAML = FIXTURES_DIR / "assumptions_test.yaml"

BASE_DIR = Path(__file__).parent.parent
REAL_FACTORS_CSV = BASE_DIR / "data" / "factors" / "factors.csv"
REAL_ASSUMPTIONS_YAML = BASE_DIR / "data" / "factors" / "assumptions.yaml"


@pytest.fixture
def test_factors():
    """Load test factor registry with simple round numbers."""
    return load_factors(FACTORS_TEST_CSV, ASSUMPTIONS_TEST_YAML)


@pytest.fixture
def real_factors():
    """Load real production factors (Cummins C140D5P, CEA grid, DEFRA diesel)."""
    return load_factors(REAL_FACTORS_CSV, REAL_ASSUMPTIONS_YAML)


def make_dummy_detection(
    id="det_01",
    source_file="media/gen.mp4",
    frame_index=1,
    frame_path="data/evidence/frames/gen_1.jpg",
    machine_type="diesel_generator",
    rated_power_kw=100.0,
    rated_kva=None,
    smoke_score=1.0,
    smoke_color="none",
    smoke_level="none",
    maintenance_flag=False,
    confidence_0_1=0.90,
) -> Detection:
    return Detection(
        id=id,
        source_file=source_file,
        frame_index=frame_index,
        frame_path=frame_path,
        machine_type=machine_type,
        rated_power_kw=rated_power_kw,
        rated_kva=rated_kva,
        smoke=SmokeAnalysis(level=smoke_level, color=smoke_color, score_0_10=smoke_score),
        maintenance_flag=maintenance_flag,
        confidence_0_1=confidence_0_1,
    )


# --------------------------------------------------------------------------- #
#  1. Factor loading & verification rules
# --------------------------------------------------------------------------- #

def test_load_factors_success(test_factors):
    assert test_factors.get_factor("diesel_mineral_l").value == 3.0
    assert test_factors.get_factor("grid_india_wa").value == 0.8
    assert test_factors.get_factor("freight_hgv_avg_tkm").value == 0.1
    assert test_factors.get_assumption("diesel_price_inr_per_litre").value == 90.0


def test_todo_verify_in_factors_raises(tmp_path):
    bad_csv = tmp_path / "bad_factors.csv"
    bad_csv.write_text(
        "factor_id,name,value,unit,source_name,source_url,year,notes\n"
        "diesel_mineral_l,Test Factor,TODO_VERIFY,kg CO2e,Source,http://url,2024,Note\n"
    )
    with pytest.raises(MissingFactorError) as exc_info:
        load_factors(bad_csv, ASSUMPTIONS_TEST_YAML)
    assert "TODO_VERIFY" in str(exc_info.value) or "unverified" in str(exc_info.value)


def test_non_numeric_in_factors_raises(tmp_path):
    bad_csv = tmp_path / "bad_factors.csv"
    bad_csv.write_text(
        "factor_id,name,value,unit,source_name,source_url,year,notes\n"
        "diesel_mineral_l,Test Factor,not_a_number,kg CO2e,Source,http://url,2024,Note\n"
    )
    with pytest.raises(MissingFactorError) as exc_info:
        load_factors(bad_csv, ASSUMPTIONS_TEST_YAML)
    assert "non-numeric" in str(exc_info.value)


def test_real_factors_load_cleanly(real_factors):
    """Confirm real factors.csv now loads without MissingFactorError."""
    ef = real_factors.get_factor("diesel_mineral_l")
    assert ef.value > 0.0
    assert ef.value == 2.68  # DEFRA 2024

    ef_grid = real_factors.get_factor("grid_india_wa")
    assert ef_grid.value == 0.716  # CEA v22

    ef_freight = real_factors.get_factor("freight_hgv_avg_tkm")
    assert ef_freight.value > 0.0


# --------------------------------------------------------------------------- #
#  2. Electricity bill calculation & unit normalisation
# --------------------------------------------------------------------------- #

def test_electricity_from_bill(test_factors):
    # Hand calculation: 1000 kWh * 0.8 kg CO2e/kWh = 800.0 kg CO2e
    bill = BillExtraction(
        id="bill_elec_01",
        source_file="bills/march_elec.png",
        bill_type="electricity",
        period_start="2024-03-01",
        period_end="2024-03-31",
        quantity=1000.0,
        unit="kWh",
        amount_inr=8000.0,
        supplier="BESCOM",
        confidence_0_1=0.95,
        field_boxes={"units": [10, 10, 20, 20]},
        method="ocr",
        user_confirmed=True,
    )
    line = electricity_from_bill(bill, test_factors, TEST_FACTOR_MAP)
    assert line.scope == 2
    assert line.co2e_kg == 800.0
    assert line.activity_value == 1000.0
    assert line.activity_unit == "kWh"
    assert "1000.0 kWh x 0.8 kg CO2e/kWh = 800.0 kg" in line.formula_text
    assert "[CO2 only]" in line.category
    assert "bills/march_elec.png" in line.evidence_refs
    # Standard uncertainty: 800 +- 5% = [760.0, 840.0]
    assert line.low_kg == 760.0
    assert line.high_kg == 840.0


def test_electricity_mwh_conversion(test_factors):
    # 2.5 MWh = 2500 kWh * 0.8 = 2000.0 kg CO2e
    bill = BillExtraction(
        id="bill_elec_mwh",
        source_file="bills/mwh_bill.png",
        bill_type="electricity",
        period_start="2024-03-01",
        period_end="2024-03-31",
        quantity=2.5,
        unit="MWh",
        amount_inr=20000.0,
        supplier="Tata Power",
        confidence_0_1=0.90,
        method="ocr",
        user_confirmed=True,
    )
    line = electricity_from_bill(bill, test_factors, TEST_FACTOR_MAP)
    assert line.activity_value == 2500.0
    assert line.activity_unit == "kWh"
    assert line.co2e_kg == 2000.0


# --------------------------------------------------------------------------- #
#  3. Diesel fuel bill calculation & gallon rejection
# --------------------------------------------------------------------------- #

def test_fuel_from_bill(test_factors):
    # Hand calculation: 500 L * 3.0 kg CO2e/L = 1500.0 kg CO2e
    bill = BillExtraction(
        id="bill_diesel_01",
        source_file="bills/fuel_slip.png",
        bill_type="diesel",
        period_start="2024-04-10",
        period_end="2024-04-10",
        quantity=500.0,
        unit="L",
        amount_inr=45000.0,
        supplier="IOCL",
        confidence_0_1=0.92,
        method="ocr",
        user_confirmed=True,
    )
    line = fuel_from_bill(bill, test_factors, TEST_FACTOR_MAP)
    assert line.scope == 1
    assert line.co2e_kg == 1500.0
    assert line.activity_value == 500.0
    assert line.activity_unit == "L"
    assert "500.0 L x 3.0 kg CO2e/L = 1500.0 kg" in line.formula_text
    assert line.low_kg == 1425.0   # 1500 * 0.95
    assert line.high_kg == 1575.0  # 1500 * 1.05


def test_fuel_gallons_rejected(test_factors):
    bill = BillExtraction(
        id="bill_diesel_gal",
        source_file="bills/fuel_gal.png",
        bill_type="diesel",
        period_start="2024-04-10",
        period_end="2024-04-10",
        quantity=100.0,
        unit="gallons",
        amount_inr=4000.0,
        supplier="Unknown",
        confidence_0_1=0.90,
        method="ocr",
        user_confirmed=True,
    )
    with pytest.raises(UnitError) as exc_info:
        fuel_from_bill(bill, test_factors, TEST_FACTOR_MAP)
    assert "Gallons are rejected" in str(exc_info.value)


# --------------------------------------------------------------------------- #
#  4. Freight bill calculation
# --------------------------------------------------------------------------- #

def test_freight_from_bill(test_factors):
    # Hand calculation: 2000 tonne-km * 0.1 kg CO2e/tonne-km = 200.0 kg CO2e
    bill = BillExtraction(
        id="bill_freight_01",
        source_file="bills/freight_lr.png",
        bill_type="freight",
        period_start="2024-05-01",
        period_end="2024-05-01",
        quantity=2000.0,
        unit="tonne-km",
        amount_inr=6000.0,
        supplier="VRL",
        confidence_0_1=0.88,
        method="ocr",
        user_confirmed=True,
    )
    line = freight_from_bill(bill, test_factors, TEST_FACTOR_MAP)
    assert line.scope == 3
    assert line.co2e_kg == 200.0
    assert line.activity_value == 2000.0
    assert line.activity_unit == "tonne-km"
    assert "2000.0 tonne-km x 0.1 kg CO2e/tonne-km = 200.0 kg" in line.formula_text


# --------------------------------------------------------------------------- #
#  5. Machine detection estimate: kW, kVA, SFC interpolation, flags
# --------------------------------------------------------------------------- #

def test_fuel_from_detection_kw_at_100pct(test_factors):
    # Hand calculation at 100% load:
    # 100 kW, 100% load, 10 hrs.
    # SFC(100%) = 0.24 L/kWh (from test fixture gen_TEST_sfc_100)
    # Litres = 100 * 1.0 * 10 * 0.24 = 240.0 L
    # CO2e = 240.0 * 3.0 = 720.0 kg CO2e
    det = make_dummy_detection(rated_power_kw=100.0, confidence_0_1=0.90)
    line = fuel_from_detection(det, hours_per_month=10.0, load_pct=100.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)
    assert line.scope == 1
    assert abs(line.activity_value - 240.0) < 1e-6
    assert abs(line.co2e_kg - 720.0) < 1e-6
    assert "100.0 kW x 100.0% load x 10.0 hrs x 0.2400 L/kWh x 3.0 kg CO2e/L = 720.0 kg" in line.formula_text
    assert "data/evidence/frames/gen_1.jpg" in line.evidence_refs
    assert "user_input:hours=10.0,load_pct=100.0" in line.evidence_refs
    # No below-range flag at 100%
    assert "load_below_datasheet_range" not in line.flags


def test_fuel_from_detection_kw_at_75pct(test_factors):
    # At exactly 75% load:
    # SFC = gen_TEST_sfc_75 = 0.28 L/kWh
    # 100 kW * 0.75 * 10 hrs * 0.28 = 210.0 L
    # CO2e = 210.0 * 3.0 = 630.0 kg CO2e
    det = make_dummy_detection(rated_power_kw=100.0, confidence_0_1=0.90)
    line = fuel_from_detection(det, hours_per_month=10.0, load_pct=75.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)
    assert abs(line.co2e_kg - 630.0) < 1e-6
    assert "load_below_datasheet_range" not in line.flags


def test_fuel_from_detection_below_75pct_clamps_and_flags(test_factors):
    # At 50% load — below 75% datasheet range.
    # SFC MUST clamp to sfc_75 = 0.28, and flag 'load_below_datasheet_range' must appear.
    # 100 kW * 0.50 * 10 hrs * 0.28 = 140.0 L
    # CO2e = 140.0 * 3.0 = 420.0 kg CO2e
    det = make_dummy_detection(rated_power_kw=100.0, confidence_0_1=0.90)
    line = fuel_from_detection(det, hours_per_month=10.0, load_pct=50.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)
    assert abs(line.co2e_kg - 420.0) < 1e-6
    assert "load_below_datasheet_range" in line.flags


def test_fuel_from_detection_sfc_interpolation_at_87pct(test_factors):
    # At 87.5% load (halfway between 75% SFC=0.28 and 100% SFC=0.24):
    # SFC = 0.28 + 0.5 * (0.24 - 0.28) = 0.28 - 0.02 = 0.26 L/kWh
    # 100 kW * 0.875 * 10 hrs * 0.26 = 227.5 L
    # CO2e = 227.5 * 3.0 = 682.5 kg CO2e
    det = make_dummy_detection(rated_power_kw=100.0, confidence_0_1=0.90)
    line = fuel_from_detection(det, hours_per_month=10.0, load_pct=87.5, factors=test_factors, factor_map=TEST_FACTOR_MAP)
    assert abs(line.activity_value - 227.5) < 1e-4
    assert abs(line.co2e_kg - 682.5) < 1e-4
    assert "load_below_datasheet_range" not in line.flags


def test_fuel_from_detection_kva_conversion(test_factors):
    # When rated_power_kw is None and rated_kva=125.0:
    # PF = 0.8 (from factors.csv gen_fuel_tolerance_pct -> genset_power_factor)
    # kW = 125.0 * 0.8 = 100.0 kW
    # At 100% load: 100 * 1.0 * 10 * 0.24 = 240.0 L; * 3.0 = 720.0 kg CO2e
    det = make_dummy_detection(rated_power_kw=None, rated_kva=125.0, confidence_0_1=0.85)
    line = fuel_from_detection(det, hours_per_month=10.0, load_pct=100.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)
    assert abs(line.co2e_kg - 720.0) < 1e-6
    assert "100.0 kW (converted from 125.0 kVA x 0.8 power factor)" in line.formula_text


def test_fuel_from_detection_missing_hours_raises(test_factors):
    det = make_dummy_detection(rated_power_kw=100.0)
    with pytest.raises(NeedsUserInput) as exc_info:
        fuel_from_detection(det, hours_per_month=None, load_pct=75.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)
    assert "hours_per_month" in exc_info.value.missing_fields


def test_fuel_from_detection_zero_hours(test_factors):
    det = make_dummy_detection(rated_power_kw=100.0)
    line = fuel_from_detection(det, hours_per_month=0.0, load_pct=100.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)
    assert line.co2e_kg == 0.0
    assert line.activity_value == 0.0


# --------------------------------------------------------------------------- #
#  6. Uncertainty widening: smoke, low confidence, low OCR
# --------------------------------------------------------------------------- #

def test_uncertainty_widened_for_heavy_smoke(test_factors):
    det_clean = make_dummy_detection(rated_power_kw=100.0, smoke_score=1.0, smoke_color="none", smoke_level="none", confidence_0_1=0.90)
    det_smoky = make_dummy_detection(rated_power_kw=100.0, smoke_score=8.0, smoke_color="black", smoke_level="heavy", maintenance_flag=True, confidence_0_1=0.90)
    line_clean = fuel_from_detection(det_clean, hours_per_month=10.0, load_pct=100.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)
    line_smoky = fuel_from_detection(det_smoky, hours_per_month=10.0, load_pct=100.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)

    # Invariant: co2e baseline must NEVER change due to smoke
    assert line_clean.co2e_kg == line_smoky.co2e_kg

    # Smoky range must be wider
    assert line_smoky.high_kg > line_clean.high_kg
    assert line_smoky.low_kg < line_clean.low_kg
    assert "smoke_inefficiency_widened" in line_smoky.flags


def test_uncertainty_widened_for_low_ocr_confidence(test_factors):
    bill_good = BillExtraction(
        id="bill_good", source_file="b.png", bill_type="electricity",
        period_start="2024-01-01", period_end="2024-01-31",
        quantity=1000.0, unit="kWh", amount_inr=8000.0, supplier="BESCOM",
        confidence_0_1=0.95, method="ocr", user_confirmed=True,
    )
    bill_bad = BillExtraction(
        id="bill_bad", source_file="b.png", bill_type="electricity",
        period_start="2024-01-01", period_end="2024-01-31",
        quantity=1000.0, unit="kWh", amount_inr=8000.0, supplier="BESCOM",
        confidence_0_1=0.50, method="ocr", user_confirmed=True,
    )
    line_good = electricity_from_bill(bill_good, test_factors, TEST_FACTOR_MAP)
    line_bad = electricity_from_bill(bill_bad, test_factors, TEST_FACTOR_MAP)

    assert line_good.co2e_kg == line_bad.co2e_kg == 800.0
    assert abs(line_good.low_kg - 760.0) < 1e-6 and abs(line_good.high_kg - 840.0) < 1e-6
    assert abs(line_bad.low_kg - 720.0) < 1e-6 and abs(line_bad.high_kg - 880.0) < 1e-6
    assert "ocr_low_confidence_widened" in line_bad.flags


# --------------------------------------------------------------------------- #
#  7. Reconcile under and over 25 percent mismatch
# --------------------------------------------------------------------------- #

def _make_diesel_bill(quantity_litres: float, test_factors, test_factor_map) -> "EmissionLine":
    bill = BillExtraction(
        id="b_rec", source_file="b.png", bill_type="diesel",
        period_start="2024-01-01", period_end="2024-01-31",
        quantity=quantity_litres, unit="L", amount_inr=30000.0, supplier="IOCL",
        confidence_0_1=0.9, method="ocr", user_confirmed=True,
    )
    return fuel_from_bill(bill, test_factors, test_factor_map)


def test_reconcile_under_25_pct(test_factors):
    # Bill co2e: 333.333 L * 3.0 = 1000.0 kg
    bill_line = _make_diesel_bill(333.333333, test_factors, TEST_FACTOR_MAP)

    det = make_dummy_detection(rated_power_kw=100.0)
    # Target video estimate ~1100 kg -> 1100/3.0 = 366.667 L
    # At 100% load SFC=0.24: 100 * 1.0 * hrs * 0.24 = 366.667 -> hrs = 15.278
    video_line = fuel_from_detection(det, hours_per_month=15.278, load_pct=100.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)

    rec = reconcile(video_line, bill_line)
    assert rec.method == "reconciled"
    assert rec.co2e_kg == bill_line.co2e_kg
    assert "video_bill_mismatch" not in rec.flags


def test_reconcile_over_25_pct_triggers_flag(test_factors):
    # Bill co2e: 333.333 L * 3.0 = 1000.0 kg
    bill_line = _make_diesel_bill(333.333333, test_factors, TEST_FACTOR_MAP)

    det = make_dummy_detection(rated_power_kw=100.0)
    # Target video estimate ~1400 kg -> 1400/3.0 = 466.667 L
    # hrs = 466.667 / (100 * 1.0 * 0.24) = 466.667 / 24 = 19.444
    video_line = fuel_from_detection(det, hours_per_month=19.444, load_pct=100.0, factors=test_factors, factor_map=TEST_FACTOR_MAP)

    rec = reconcile(video_line, bill_line)
    assert rec.method == "reconciled"
    assert rec.co2e_kg == bill_line.co2e_kg
    assert "video_bill_mismatch" in rec.flags


# --------------------------------------------------------------------------- #
#  8. Totals aggregation & range sum invariants
# --------------------------------------------------------------------------- #

def test_totals_equal_sum_of_lines(test_factors):
    b1 = BillExtraction(id="b1", source_file="b1.png", bill_type="diesel", period_start="2024-01-01", period_end="2024-01-31", quantity=100.0, unit="L", amount_inr=9000.0, supplier="IOCL", confidence_0_1=0.9, method="ocr", user_confirmed=True)
    b2 = BillExtraction(id="b2", source_file="b2.png", bill_type="electricity", period_start="2024-01-01", period_end="2024-01-31", quantity=1000.0, unit="kWh", amount_inr=8000.0, supplier="BESCOM", confidence_0_1=0.9, method="ocr", user_confirmed=True)
    b3 = BillExtraction(id="b3", source_file="b3.png", bill_type="freight", period_start="2024-01-01", period_end="2024-01-31", quantity=500.0, unit="tonne-km", amount_inr=1500.0, supplier="VRL", confidence_0_1=0.9, method="ocr", user_confirmed=True)

    line1 = fuel_from_bill(b1, test_factors, TEST_FACTOR_MAP)        # 100 * 3.0 = 300 kg Scope 1
    line2 = electricity_from_bill(b2, test_factors, TEST_FACTOR_MAP) # 1000 * 0.8 = 800 kg Scope 2
    line3 = freight_from_bill(b3, test_factors, TEST_FACTOR_MAP)     # 500 * 0.1 = 50 kg Scope 3

    res = totals([line1, line2, line3])

    assert res["scope_1"]["co2e_kg"] == 300.0
    assert res["scope_2"]["co2e_kg"] == 800.0
    assert res["scope_3"]["co2e_kg"] == 50.0

    expected_grand = 300.0 + 800.0 + 50.0
    assert res["grand_total"]["co2e_kg"] == expected_grand
    assert abs(res["grand_total"]["low_kg"] - (line1.low_kg + line2.low_kg + line3.low_kg)) < 1e-6
    assert abs(res["grand_total"]["high_kg"] - (line1.high_kg + line2.high_kg + line3.high_kg)) < 1e-6


# --------------------------------------------------------------------------- #
#  9. INTEGRATION — Cummins C140D5P against REAL factors.csv
# --------------------------------------------------------------------------- #

def test_integration_real_cummins_c140d5p(real_factors):
    """
    Demo scenario: Cummins C140D5P diesel genset.
    Nameplate: 140 kVA / 112 kW prime rated.
    User input: 80 hours/month at 87.5% load.

    Hand arithmetic (using verified real factors):

    Step 1 — Rated kW
      kW = 112.0 kW (rated_power_kw supplied; no kVA conversion needed)

    Step 2 — SFC at 87.5% load (between 75% and 100% datasheet points)
      sfc_75  = 0.2765 L/kWh   (gen_C140D5P_sfc_75 in factors.csv)
      sfc_100 = 0.2614 L/kWh   (gen_C140D5P_sfc_100 in factors.csv)
      fraction = (87.5 - 75.0) / (100.0 - 75.0) = 12.5 / 25.0 = 0.5
      SFC(87.5%) = 0.2765 + 0.5 * (0.2614 - 0.2765)
                 = 0.2765 + 0.5 * (-0.0151)
                 = 0.2765 - 0.00755
                 = 0.26895 L/kWh

    Step 3 — Estimated litres
      Litres = 112.0 kW * (87.5/100) * 80 hrs * 0.26895 L/kWh
             = 112.0 * 0.875 * 80 * 0.26895
             = 98.0 * 80 * 0.26895
             = 7840.0 * 0.26895
             = 2108.568 L

    Step 4 — CO2e
      diesel factor = 2.68 kg CO2e/L   (diesel_mineral_l in factors.csv)
      CO2e = 2108.568 L * 2.68 kg/L = 5650.96 kg  (rounded to 2dp for assertion tolerance)
    """
    # These are the USER INPUTS that would be typed into the form
    HOURS_PER_MONTH = 80.0
    LOAD_PCT = 87.5
    RATED_KW = 112.0

    det = Detection(
        id="det_c140d5p_demo",
        source_file="media/cummins_c140d5p.mp4",
        frame_index=42,
        frame_path="data/evidence/frames/cummins_c140d5p_42.jpg",
        machine_type="diesel_generator",
        rated_power_kw=RATED_KW,
        nameplate_text="CUMMINS C140D5P 140kVA/112kW PRIME",
        smoke=SmokeAnalysis(level="none", color="none", score_0_10=0.0),
        maintenance_flag=False,
        confidence_0_1=0.93,
    )

    line = fuel_from_detection(
        det,
        hours_per_month=HOURS_PER_MONTH,
        load_pct=LOAD_PCT,
        factors=real_factors,
        factor_map=PRODUCTION_FACTOR_MAP,
    )

    # --- Hand arithmetic (reproduced above in docstring) ---
    expected_sfc = 0.2765 + 0.5 * (0.2614 - 0.2765)       # = 0.26895
    expected_litres = RATED_KW * (LOAD_PCT / 100.0) * HOURS_PER_MONTH * expected_sfc
    expected_co2e = expected_litres * 2.68                   # diesel_mineral_l

    # Assert to within floating-point rounding (< 0.01 kg tolerance)
    assert abs(line.co2e_kg - expected_co2e) < 0.01, (
        f"Expected {expected_co2e:.4f} kg, got {line.co2e_kg:.4f} kg"
    )
    assert abs(line.activity_value - expected_litres) < 0.001
    assert line.scope == 1
    assert line.method == "video_estimate"
    assert line.factor_id == "diesel_mineral_l"
    assert "load_below_datasheet_range" not in line.flags
    assert "user_input:hours=80.0,load_pct=87.5" in line.evidence_refs
    assert "data/evidence/frames/cummins_c140d5p_42.jpg" in line.evidence_refs

    # Uncertainty bounds: must bracket the central estimate
    assert line.low_kg < line.co2e_kg < line.high_kg
