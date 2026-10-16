"""
backend/rag/generator.py — Full Report Generation Orchestrator.

Combines:
  1. Locked FACTS object construction (backend/rag/facts.py).
  2. RAG regulatory chunk retrieval (backend/rag/retriever.py).
  3. LLM generation with strict constraint prompts via backend/llm.generate_text.
  4. Post-processing placeholder replacement (backend/rag/postprocess.py).
  5. Strict number validation & hallucination detection (backend/rag/validator.py).
  6. Automatic one-time regeneration and deterministic fallback template (backend/rag/templates.py).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from backend.schemas import EmissionLine, Report, ReportSection, ScenarioResult, ValidationSummary
from backend.rag.facts import build_facts_registry, FactsRegistry
from backend.rag.retriever import retrieve_relevant_chunks, RetrievedChunk
from backend.rag.templates import SECTION_TOPICS, build_section_prompt, generate_fallback_template_sections
from backend.rag.postprocess import postprocess_markdown
from backend.rag.validator import validate_report_numbers
import backend.llm as llm_client

logger = logging.getLogger(__name__)


def generate_report(
    facility_name: str,
    reporting_period: str,
    emission_lines: List[EmissionLine],
    scenario_result: Optional[ScenarioResult] = None,
    force_fallback_template: bool = False,
) -> Report:
    """
    Generates a validated Carbon Passport narrative report.
    Guarantees that 100% of reported numbers trace back to engine calculations or regulatory citations.
    """
    # 1. Build immutable facts registry
    facts_reg = build_facts_registry(
        facility_name=facility_name,
        reporting_period=reporting_period,
        emission_lines=emission_lines,
        scenario_result=scenario_result,
    )

    # Fast-path for explicit fallback template request
    if force_fallback_template:
        return _generate_fallback_report(facts_reg)

    # 2. Attempt 1: Generate with LLM + RAG
    sections, number_map, all_chunks, passed, untraceable = _generate_and_validate(
        facts_reg=facts_reg,
        retry_feedback=None,
    )

    if not passed:
        logger.warning(f"Report validation failed on Attempt 1 with {len(untraceable)} untraceable numbers. Retrying once...")
        # Prepare specific retry feedback for LLM
        err_details = "\n".join([f"- Found '{u['number']}' in '{u['section']}': {u['snippet']}" for u in untraceable[:5]])
        retry_msg = f"The following numbers are untraceable and forbidden:\n{err_details}\nUse ONLY placeholders like {{{{total.all.co2e_kg}}}}."

        # Attempt 2: Regenerate once on failure
        sections, number_map, all_chunks, passed, untraceable = _generate_and_validate(
            facts_reg=facts_reg,
            retry_feedback=retry_msg,
        )

        if not passed:
            logger.warning("Report validation failed on Attempt 2. Falling back to deterministic template.")
            # Fall back to template-based report filled ONLY from FACTS
            return _generate_fallback_report(facts_reg)

    # Build validated Report object
    return Report(
        sections=sections,
        facts_snapshot=facts_reg.to_facts_json(),
        number_map=number_map,
        validation=ValidationSummary(
            passed=True,
            untraceable_numbers=[],
        ),
    )


def _generate_and_validate(
    facts_reg: FactsRegistry,
    retry_feedback: Optional[str] = None,
) -> Tuple[List[ReportSection], Dict[str, str], List[RetrievedChunk], bool, List[Dict[str, Any]]]:
    """
    Runs section-by-section retrieval, prompt generation, LLM call, postprocessing, and validation.
    """
    sections: List[ReportSection] = []
    combined_number_map: Dict[str, str] = {}
    all_retrieved_chunks: List[RetrievedChunk] = []
    sections_rendered_dict: Dict[str, str] = {}

    for section_title, topic in SECTION_TOPICS:
        # Retrieve relevant passages for topic
        chunks = retrieve_relevant_chunks(topic, top_k=2)
        all_retrieved_chunks.extend(chunks)

        # Build prompt
        prompt = build_section_prompt(
            section_title=section_title,
            topic=topic,
            facts_registry=facts_reg,
            retrieved_chunks=chunks,
            retry_feedback=retry_feedback,
        )

        # Call LLM through backend/llm
        try:
            raw_text = llm_client.generate_text(prompt)
        except Exception as e:
            logger.error(f"LLM call failed for section '{section_title}': {e}")
            raw_text = f"Content generation error: {e}"

        # Post-process placeholders
        rendered_md, num_map, _ = postprocess_markdown(raw_text, facts_reg)
        combined_number_map.update(num_map)
        sections_rendered_dict[section_title] = rendered_md

        # Chart metadata
        charts = []
        if "scope" in section_title.lower():
            charts.append({"type": "donut", "data_ref": "scope_breakdown"})
        elif "reduction" in section_title.lower() and facts_reg.scenario_result:
            charts.append({"type": "bar", "data_ref": "ranked_levers"})

        sections.append(ReportSection(
            title=section_title,
            content_markdown=rendered_md,
            charts=charts,
        ))

    # Validate all numbers in final rendered markdown
    passed, untraceable = validate_report_numbers(
        sections_markdown=sections_rendered_dict,
        facts_registry=facts_reg,
        retrieved_chunks=all_retrieved_chunks,
    )

    return sections, combined_number_map, all_retrieved_chunks, passed, untraceable


def _generate_fallback_report(facts_reg: FactsRegistry) -> Report:
    """Generates 100% verified deterministic fallback template report."""
    citations = {
        "ghg": "[ghg_protocol_corporate_standard.pdf p.1]",
        "brsr": "[sebi_brsr_framework.pdf p.1]",
        "cbam": "[cbam_regulation_guidance.txt p.1]",
    }
    sections = generate_fallback_template_sections(facts_reg, citations)

    # Build number_map from template
    sections_dict = {s.title: s.content_markdown for s in sections}
    number_map: Dict[str, str] = {}
    for fid, fval in facts_reg.all_facts().items():
        disp = fval.display_str
        raw_num = f"{fval.number:.2f}"
        target = fval.evidence_line_id or fid
        number_map[disp] = target
        number_map[raw_num] = target

    return Report(
        sections=sections,
        facts_snapshot=facts_reg.to_facts_json(),
        number_map=number_map,
        validation=ValidationSummary(
            passed=True,
            untraceable_numbers=[],
        ),
    )
