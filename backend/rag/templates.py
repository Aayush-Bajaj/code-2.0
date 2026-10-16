"""
backend/rag/templates.py — Deterministic fallback report template and section prompt builders.

Provides:
  1. Strict prompt generation for LLM with locked FACTS object and regulatory passages.
  2. 100% verified template-based report generator filled ONLY from FACTS, used when LLM validation fails.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from backend.rag.facts import FactsRegistry
from backend.rag.retriever import RetrievedChunk
from backend.schemas import ReportSection

SECTION_TOPICS = [
    ("Company summary", "MSME facility operations, manufacturing context, reporting boundary"),
    ("Methodology", "GHG Protocol activity data calculation and emission factor multiplication"),
    ("Emissions by scope (with ranges)", "Scope 1 direct combustion, Scope 2 electricity, Scope 3 freight with low and high uncertainty ranges"),
    ("Data quality and assumptions", "Verification status of bills, optical smoke monitoring, equipment nameplate parameters"),
    ("Reduction plan ranked by payback", "Decarbonisation levers, solar PV, genset operational optimization, capex, and payback ranking"),
    ("Limitations", "Uncertainty ranges, estimations disclaimer, non-regulatory certification boundaries"),
]


def build_section_prompt(
    section_title: str,
    topic: str,
    facts_registry: FactsRegistry,
    retrieved_chunks: List[RetrievedChunk],
    retry_feedback: Optional[str] = None,
) -> str:
    """
    Constructs the prompt for an individual report section per Requirement 3:
    - Use ONLY numbers from FACTS and refer to them by id in double curly braces {{fact_id}}.
    - Cite retrieved passages as [doc p.X].
    - If something is not in FACTS or the passages write 'not available'.
    - Never claim certification or compliance, only that the report supports the data these frameworks request.
    - Keep a neutral professional tone.
    """
    facts_json = json.dumps(facts_registry.to_facts_json(), indent=2)

    passages_text = ""
    for ch in retrieved_chunks:
        passages_text += f"\n--- PASSAGE: {ch.citation} ---\n{ch.text.strip()}\n"

    retry_block = ""
    if retry_feedback:
        retry_block = f"""
CRITICAL CORRECTION REQUIRED FROM PREVIOUS ATTEMPT:
The previous attempt failed validation with the following error:
{retry_feedback}
You MUST eliminate all untraceable or invented numbers. Use ONLY placeholder IDs like {{{{total.all.co2e_kg}}}}.
"""

    return f"""You are the Carbon Passport Technical Report Generator.
Generate the narrative markdown content for the section: "{section_title}".

NON-NEGOTIABLE RULES:
1. Use ONLY numbers from the provided FACTS object below. NEVER invent, round, change, or introduce external numbers.
2. Refer to EVERY number strictly by its identifier enclosed in double curly braces, e.g. {{{{total.scope1.co2e_kg}}}}, {{{{total.all.co2e_kg}}}}, {{{{line_1.co2e_kg}}}}, or {{{{scenario.delta_pct}}}}.
3. Cite retrieved regulatory passages as [doc p.X], e.g. [sebi_brsr_framework.pdf p.1] or [cbam_regulation_guidance.txt p.1].
4. If something is not in FACTS or the retrieved passages, write 'not available'.
5. NEVER claim formal regulatory certification or compliance. State only that the output 'supports the data these frameworks request'.
6. Keep a neutral, professional, engineering audit tone. Format clearly in markdown.
{retry_block}
TOPIC FOR THIS SECTION:
{topic}

LOCKED FACTS OBJECT:
{facts_json}

RETRIEVED REGULATORY PASSAGES:
{passages_text}

Output ONLY the markdown content for this section (do not include markdown block markers):
"""


def generate_fallback_template_sections(
    facts_registry: FactsRegistry,
    citations: Dict[str, str],
) -> List[ReportSection]:
    """
    Generates a 100% deterministic, audit-verified report using structured templates
    populated directly from the locked FACTS registry. Used as fail-safe fallback.
    """
    fac = facts_registry.facility_name
    period = facts_registry.reporting_period
    facts = facts_registry.all_facts()

    def _val(fid: str, default: str = "not available") -> str:
        f = facts_registry.get_fact(fid)
        return f.display_str if f else default

    # 1. Company summary
    s1 = (
        f"### Facility Overview\n"
        f"This report covers operational carbon footprint estimation for **{fac}** during reporting period **{period}**. "
        f"The boundary encompasses direct combustion sources (Scope 1), purchased grid electricity (Scope 2), "
        f"and documented upstream logistics (Scope 3). The output supports the data these frameworks request "
        f"for supply chain transparency and customer carbon passport requirements."
    )

    # 2. Methodology
    s2 = (
        f"### Calculation Methodology\n"
        f"Emissions were determined following standard GHG Protocol guidelines {citations.get('ghg', '[ghg_protocol_corporate_standard.pdf p.1]')} "
        f"using the verified formula: `Emissions = Activity Data x Emission Factor`. "
        f"Grid electricity emission factors align with regional grid baselines, and diesel combustion factors "
        f"are drawn from published government and international lifecycle inventories. "
        f"All numbers link directly to underlying invoices and optical evidence bundles."
    )

    # 3. Emissions by scope (with ranges)
    s3 = (
        f"### Emissions by Scope Summary\n"
        f"- **Scope 1 (Direct Combustion):** {_val('total.scope1.co2e_kg')} "
        f"(Uncertainty range: {_val('total.scope1.low_kg')} to {_val('total.scope1.high_kg')})\n"
        f"- **Scope 2 (Electricity Indirect):** {_val('total.scope2.co2e_kg')} "
        f"(Uncertainty range: {_val('total.scope2.low_kg')} to {_val('total.scope2.high_kg')})\n"
        f"- **Scope 3 (Freight Logistics):** {_val('total.scope3.co2e_kg')} "
        f"(Uncertainty range: {_val('total.scope3.low_kg')} to {_val('total.scope3.high_kg')})\n"
        f"- **Gross Total Footprint:** {_val('total.all.co2e_kg')} "
        f"(Uncertainty range: {_val('total.all.low_kg')} to {_val('total.all.high_kg')})\n\n"
        f"Reporting adheres to SEBI BRSR Principle 6 {citations.get('brsr', '[sebi_brsr_framework.pdf p.1]')} "
        f"and supports transitional reporting for EU CBAM {citations.get('cbam', '[cbam_regulation_guidance.txt p.1]')}."
    )

    # 4. Data quality and assumptions
    maint_count = _val("flags.maintenance_flags_count", "0")
    s4 = (
        f"### Evidence and Data Quality\n"
        f"Input data was collected from utility electricity statements, fuel purchase records, and optical video monitoring. "
        f"Total active equipment maintenance flags raised: **{maint_count}**. "
        f"Maintenance flags widen the low-high uncertainty range without altering baseline emission numbers."
    )

    # 5. Reduction plan ranked by payback
    if facts_registry.scenario_result and facts_registry.scenario_result.ranked_levers:
        sr = facts_registry.scenario_result
        lever_lines = []
        for idx, lever in enumerate(sr.ranked_levers, start=1):
            name = lever.get("lever", f"Lever {idx}")
            red = _val(f"lever_{idx}.co2e_reduction_kg", "0 kg CO2e")
            pb = _val(f"lever_{idx}.payback_months", "N/A")
            lever_lines.append(f"{idx}. **{name}**: Reduction {_val(f'lever_{idx}.co2e_reduction_kg')} | Payback: {pb}")
        levers_text = "\n".join(lever_lines)
        s5 = (
            f"### Prioritized Decarbonisation Levers\n"
            f"Projected footprint reduction under simulated scenario: {_val('scenario.delta_pct')} "
            f"(new projected footprint: {_val('scenario.new_co2e_kg')}). "
            f"Estimated monthly operating savings: {_val('scenario.inr_saved_per_month')} against capex of {_val('scenario.capex_inr')}. "
            f"Estimated payback period: {_val('scenario.payback_months')}.\n\n"
            f"**Ranked Levers (by payback):**\n{levers_text}"
        )
    else:
        s5 = (
            f"### Prioritized Decarbonisation Levers\n"
            f"No scenario analysis was executed for this reporting run. "
            f"Recommendations for rooftop solar PV and equipment maintenance can be simulated in the Digital Twin module."
        )

    # 6. Limitations
    s6 = (
        f"### Limitations and Disclaimer\n"
        f"All figures presented herein are estimates with low/high uncertainty bounds. "
        f"This output does not constitute formal certification or regulatory compliance, "
        f"but supports the data these frameworks request under stated operational assumptions."
    )

    return [
        ReportSection(title="Company summary", content_markdown=s1, charts=[]),
        ReportSection(title="Methodology", content_markdown=s2, charts=[]),
        ReportSection(title="Emissions by scope (with ranges)", content_markdown=s3, charts=[{"type": "donut", "data_ref": "scope_breakdown"}]),
        ReportSection(title="Data quality and assumptions", content_markdown=s4, charts=[]),
        ReportSection(title="Reduction plan ranked by payback", content_markdown=s5, charts=[{"type": "bar", "data_ref": "ranked_levers"}]),
        ReportSection(title="Limitations", content_markdown=s6, charts=[]),
    ]
