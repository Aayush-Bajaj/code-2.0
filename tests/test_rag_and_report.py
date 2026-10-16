"""
Tests for Phase 5 & 7 (backend/rag and Report generation pipeline)

Covers:
1. Mocked LLM returning a wrong number must be caught by the validator.
2. Placeholder replacement (double curly braces replaced with exact engine numbers + units and number_map populated).
3. Fallback template generation fills only from FACTS and passes validation.
4. ReportLab PDF generation renders valid PDF with CO<sub>2</sub> tags and disclaimer footer.
5. RAG retrieval returns passages with proper citations [doc p.X].
6. FastAPI endpoints POST /report and GET /report/{id}/pdf work end-to-end.
"""
from __future__ import annotations

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.schemas import (
    EmissionLine,
    ScenarioResult,
    Report,
)

from backend.rag.facts import build_facts_registry
from backend.rag.postprocess import postprocess_markdown
from backend.rag.validator import validate_report_numbers
from backend.rag.retriever import retrieve_relevant_chunks, RetrievedChunk
from backend.rag.templates import generate_fallback_template_sections
from backend.rag.generator import generate_report, _generate_fallback_report
from backend.rag.pdf import build_report_pdf, _sanitize_co2_subscripts
from backend.api.main import app


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def sample_emission_lines() -> list[EmissionLine]:
    return [
        EmissionLine(
            id="em_line_scope1_01",
            scope=1,
            category="Stationary Combustion",
            activity_value=400.0,
            activity_unit="L",
            factor_id="diesel_mineral_l",
            factor_value=2.68,
            factor_unit="kg CO2e/L",
            factor_source="IPCC 2006",
            factor_url="https://www.ipcc-nggip.iges.or.jp",
            co2e_kg=1072.0,
            low_kg=1018.4,
            high_kg=1125.6,
            formula_text="400.0 L x 2.68 kg CO2e/L = 1072.0 kg",
            evidence_refs=["det_dg_001", "bill_diesel_001"],
            method="video_estimate",
            flags=["MAINTENANCE_WIDENED_RANGE"],
        ),
        EmissionLine(
            id="em_line_scope2_01",
            scope=2,
            category="Purchased Electricity",
            activity_value=15000.0,
            activity_unit="kWh",
            factor_id="grid_india_wa",
            factor_value=0.82,
            factor_unit="kg CO2e/kWh",
            factor_source="CEA v19",
            factor_url="https://cea.nic.in",
            co2e_kg=12300.0,
            low_kg=11685.0,
            high_kg=12915.0,
            formula_text="15000.0 kWh x 0.82 kg CO2e/kWh = 12300.0 kg",
            evidence_refs=["bill_elec_001"],
            method="bill",
            flags=[],
        ),
    ]



@pytest.fixture
def sample_scenario_result() -> ScenarioResult:
    return ScenarioResult(
        scenario_inputs={"solar_share_pct": 30.0},
        baseline_co2e_kg=13372.0,
        new_co2e_kg=9682.0,
        delta_pct=-27.6,
        inr_saved_per_month=36000.0,
        capex_inr=1350000.0,
        payback_months=37.5,
        ranked_levers=[
            {
                "rank": 1,
                "lever": "Rooftop Solar PV (30 kWp)",
                "co2e_reduction_kg": 3690.0,
                "payback_months": 37.5,
                "capex_inr": 1350000.0,
            }
        ],
        assumptions=["Grid tariff INR 8.0/kWh from assumptions.yaml"],
    )


# --------------------------------------------------------------------------- #
# 1. Mocked LLM returning a wrong number must be caught by the validator
# --------------------------------------------------------------------------- #

class TestValidatorHallucinationGuardrail:
    def test_untraceable_number_caught_by_validator(self, sample_emission_lines):
        facts = build_facts_registry("Test MSME", "2024-Q1", sample_emission_lines)
        chunks = [
            RetrievedChunk(
                text="CBAM transitional rules apply from 1 October 2023.",
                doc="cbam_regulation_guidance.txt",
                page=1,
                url="file:///cbam#page=1",
                citation="[cbam_regulation_guidance.txt p.1]",
            )
        ]

        # LLM text introduces a fabricated number "99999.9" and fake percentage "84.7%"
        hallucinated_sections = {
            "Methodology": "The facility reduced carbon by 84.7% achieving an absolute total of 99999.9 kg.",
        }

        passed, untraceable = validate_report_numbers(hallucinated_sections, facts, chunks)
        assert passed is False, "Validator must fail when text contains fabricated numbers!"
        assert len(untraceable) >= 1

        untraceable_vals = [u["raw_str"] if "raw_str" in u else u["number"] for u in untraceable]
        assert any("99999.9" in str(v) for v in untraceable_vals)

    def test_traceable_numbers_pass_validator(self, sample_emission_lines):
        facts = build_facts_registry("Test MSME", "2024-Q1", sample_emission_lines)
        chunks = [
            RetrievedChunk(
                text="Under Principle 6 of SEBI BRSR framework.",
                doc="sebi_brsr_framework.pdf",
                page=1,
                url="file:///brsr#page=1",
                citation="[sebi_brsr_framework.pdf p.1]",
            )
        ]

        # Valid text using numbers directly from facts and citations
        valid_sections = {
            "Emissions by scope": (
                "Total Scope 1 emissions were 1,072.00 kg CO2e and Scope 2 emissions were 12,300.00 kg CO2e "
                "supporting reporting under SEBI BRSR Principle 6 [sebi_brsr_framework.pdf p.1]."
            ),
        }

        passed, untraceable = validate_report_numbers(valid_sections, facts, chunks)
        assert passed is True, f"Legitimate facts numbers should pass validation: {untraceable}"
        assert len(untraceable) == 0


# --------------------------------------------------------------------------- #
# 2. Placeholder replacement
# --------------------------------------------------------------------------- #

class TestPlaceholderReplacement:
    def test_placeholders_substituted_with_exact_values(self, sample_emission_lines):
        facts = build_facts_registry("Test MSME", "2024-Q1", sample_emission_lines)
        raw_md = (
            "Total emissions are {{total.all.co2e_kg}} with Scope 1 at {{total.scope1.co2e_kg}} "
            "and Scope 2 at {{total.scope2.co2e_kg}}."
        )

        rendered, number_map, unresolved = postprocess_markdown(raw_md, facts)

        # Placeholders should be gone
        assert "{{" not in rendered
        assert "}}" not in rendered
        assert len(unresolved) == 0

        # Exact values should appear
        assert "13,372.00 kg CO2e" in rendered
        assert "1,072.00 kg CO2e" in rendered
        assert "12,300.00 kg CO2e" in rendered

        # Number map must contain mappings
        assert len(number_map) > 0
        assert "13,372.00 kg CO2e" in number_map or "13372.00" in number_map

    def test_unresolved_placeholder_flagged(self, sample_emission_lines):
        facts = build_facts_registry("Test MSME", "2024-Q1", sample_emission_lines)
        raw_md = "Here is an unknown {{non_existent_fact_id}} in text."

        rendered, number_map, unresolved = postprocess_markdown(raw_md, facts)
        assert "non_existent_fact_id" in unresolved
        assert "[UNRESOLVED: non_existent_fact_id]" in rendered


# --------------------------------------------------------------------------- #
# 3. Fallback template
# --------------------------------------------------------------------------- #

class TestFallbackTemplate:
    def test_fallback_template_produces_valid_report(self, sample_emission_lines, sample_scenario_result):
        facts = build_facts_registry("Apex Machining", "2024-Q1", sample_emission_lines, sample_scenario_result)
        report = _generate_fallback_report(facts)

        assert isinstance(report, Report)
        assert len(report.sections) == 6

        # Check section titles
        titles = [s.title for s in report.sections]
        assert "Company summary" in titles
        assert "Methodology" in titles
        assert "Emissions by scope (with ranges)" in titles
        assert "Data quality and assumptions" in titles
        assert "Reduction plan ranked by payback" in titles
        assert "Limitations" in titles

        # Check validation passes
        assert report.validation.passed is True
        assert len(report.validation.untraceable_numbers) == 0

        # Disclaimer must be present
        limitations = next(s for s in report.sections if s.title == "Limitations")
        assert "estimates with low/high uncertainty bounds" in limitations.content_markdown
        assert "does not constitute formal certification" in limitations.content_markdown


# --------------------------------------------------------------------------- #
# 4. PDF renders with ReportLab
# --------------------------------------------------------------------------- #

class TestPDFRendering:
    def test_sanitize_co2_subscripts(self):
        # Raw Unicode subscript '₂' must be replaced with <sub>2</sub>
        input_text = "Gross emissions: 1200 tCO₂e and 500 kg CO2e."
        sanitized = _sanitize_co2_subscripts(input_text)
        assert "CO₂" not in sanitized
        assert "tCO<sub>2</sub>e" in sanitized
        assert "CO<sub>2</sub>e" in sanitized

    def test_pdf_generation_creates_valid_file(self, tmp_path, sample_emission_lines, sample_scenario_result):
        import pypdf
        facts = build_facts_registry("Test Factory", "2024-Q1", sample_emission_lines, sample_scenario_result)
        report = _generate_fallback_report(facts)

        pdf_path = tmp_path / "test_report.pdf"
        res_path = build_report_pdf(report, pdf_path)

        assert res_path.exists()
        pdf_bytes = res_path.read_bytes()
        assert len(pdf_bytes) > 2000
        assert pdf_bytes.startswith(b"%PDF")

        # Verify footer string exists in generated PDF pages using pypdf
        reader = pypdf.PdfReader(str(res_path))
        assert len(reader.pages) >= 1
        page1_text = reader.pages[0].extract_text()
        assert "Estimates, not a third-party audit" in page1_text or "Estimates" in page1_text



# --------------------------------------------------------------------------- #
# 5. RAG Retrieval
# --------------------------------------------------------------------------- #

class TestRAGRetriever:
    def test_retrieve_relevant_chunks_returns_citations(self):
        chunks = retrieve_relevant_chunks("Scope 1 stationary combustion diesel", top_k=2)
        assert len(chunks) > 0
        for ch in chunks:
            assert isinstance(ch, RetrievedChunk)
            assert ch.citation.startswith("[") and ch.citation.endswith("]")
            assert "p." in ch.citation
            assert len(ch.text) > 20


# --------------------------------------------------------------------------- #
# 6. API Endpoints POST /report and GET /report/{id}/pdf
# --------------------------------------------------------------------------- #

class TestReportAPIEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_post_report_and_get_pdf(self, client, sample_emission_lines, sample_scenario_result):
        payload = {
            "facility_name": "API Test Machining Facility",
            "reporting_period": "2024-Q1",
            "emission_lines": [l.model_dump() for l in sample_emission_lines],
            "scenario_result": sample_scenario_result.model_dump(),
            "force_fallback_template": True,
        }

        # 1. POST /report
        post_resp = client.post("/report", json=payload)
        assert post_resp.status_code == 200, post_resp.text
        data = post_resp.json()

        assert "sections" in data
        assert len(data["sections"]) == 6
        assert data["validation"]["passed"] is True
        assert "report_id" in data["facts_snapshot"]

        report_id = data["facts_snapshot"]["report_id"]

        # 2. GET /report/{id}/pdf
        pdf_resp = client.get(f"/report/{report_id}/pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert len(pdf_resp.content) > 1000
        assert pdf_resp.content.startswith(b"%PDF")
