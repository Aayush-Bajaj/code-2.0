import pytest
from backend.schemas import (
    Detection,
    BillExtraction,
    EmissionLine,
    ScenarioResult,
    Report,
    ReportSection,
    EvidenceBundle,
    AuditStep,
    SmokeAnalysis,
    BoundingBox,
    ValidationSummary,
)
from backend.config import settings
from backend import llm


def test_detection_schema():
    det = Detection(
        id="det_001",
        source_file="test_video.mp4",
        frame_index=10,
        frame_path="data/evidence/frames/f_10.jpg",
        machine_type="diesel_generator",
        fuel_type="diesel",
        rated_power_kw=100.0,
        rated_kva=125.0,
        nameplate_text="Generator 100kW",
        smoke=SmokeAnalysis(level="light", color="grey", score_0_10=3.5),
        maintenance_flag=False,
        confidence_0_1=0.92,
        bbox=BoundingBox(x_min=10, y_min=20, x_max=200, y_max=300),
    )
    assert det.id == "det_001"
    assert det.smoke.score_0_10 == 3.5
    assert not det.maintenance_flag


def test_bill_extraction_schema():
    bill = BillExtraction(
        id="bill_001",
        source_file="electricity_bill.pdf",
        bill_type="electricity",
        period_start="2024-01-01",
        period_end="2024-01-31",
        quantity=5000.0,
        unit="kWh",
        amount_inr=42500.0,
        supplier="BESCOM",
        confidence_0_1=0.98,
        field_boxes={"units": [10, 20, 30, 40]},
        method="ocr",
        user_confirmed=True,
    )
    assert bill.quantity == 5000.0
    assert bill.method == "ocr"


def test_emission_line_schema():
    line = EmissionLine(
        id="line_001",
        scope=2,
        category="Purchased Electricity",
        activity_value=5000.0,
        activity_unit="kWh",
        factor_id="EF_IN_GRID",
        factor_value=0.716,
        factor_unit="kgCO2e/kWh",
        factor_source="CEA v19",
        factor_url="https://cea.nic.in",
        formula_text="5000.0 * 0.716",
        co2e_kg=3580.0,
        low_kg=3401.0,
        high_kg=3759.0,
        evidence_refs=["data/bills/electricity_bill.pdf"],
        method="bill",
        flags=[],
    )
    assert line.co2e_kg == 3580.0
    assert len(line.evidence_refs) >= 1


def test_scenario_result_schema():
    res = ScenarioResult(
        scenario_inputs={"solar_kw": 25.0},
        baseline_co2e_kg=3580.0,
        new_co2e_kg=2500.0,
        delta_pct=-30.17,
        inr_saved_per_month=8500.0,
        capex_inr=1100000.0,
        payback_months=129.4,
        ranked_levers=[{"lever": "Rooftop Solar", "saving": 1080.0}],
        assumptions=["Standard sun hours"],
    )
    assert res.baseline_co2e_kg == 3580.0
    assert res.delta_pct < 0


def test_report_schema():
    rep = Report(
        sections=[ReportSection(title="Summary", content_markdown="Baseline report", charts=[])],
        facts_snapshot={"kwh": 5000.0},
        number_map={"3580.0": "line_001"},
        validation=ValidationSummary(passed=True, untraceable_numbers=[]),
    )
    assert rep.validation.passed
    assert "3580.0" in rep.number_map


def test_evidence_bundle_schema():
    bundle = EvidenceBundle(
        line_id="line_001",
        audit_chain=[
            AuditStep(
                step_number=1,
                description="Parsed bill invoice",
                timestamp="2024-03-20T10:00:00Z",
                actor_or_component="backend/ocr/parser.py",
            )
        ],
        files=["data/bills/electricity_bill.pdf"],
        hashes={"data/bills/electricity_bill.pdf": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    )
    assert bundle.line_id == "line_001"
    assert len(bundle.audit_chain) == 1


def test_mock_llm_generation(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_LLM", True)
    text = llm.generate_text("Test prompt")
    assert isinstance(text, str)
    assert len(text) > 0

    data = llm.generate_json("Test prompt for json")
    assert isinstance(data, dict)
    assert "status" in data or "supplier" in data
