"""
backend/rag/postprocess.py — Placeholder substitution and number_map builder.

Replaces placeholders like {{fact_id}} in LLM-generated markdown with verified values
from the locked FACTS registry (e.g. '24,500.00 kg CO2e').
Populates number_map (e.g. "24500.00": "line_1" or "em_line_01") so the UI can link
each rendered number directly to its audit evidence bundle.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple
from backend.rag.facts import FactsRegistry, FactValue


PLACEHOLDER_REGEX = re.compile(r"\{\{([a-zA-Z0-9_\.]+)\}\}")


def postprocess_markdown(
    markdown_text: str,
    facts_registry: FactsRegistry,
) -> Tuple[str, Dict[str, str], List[str]]:
    """
    Substitutes all {{fact_id}} placeholders with engine verified numbers + units.
    Returns:
      (rendered_markdown, number_map, unresolved_placeholders)
    """
    number_map: Dict[str, str] = {}
    unresolved: List[str] = []

    def _replace_placeholder(match: re.Match) -> str:
        fact_id = match.group(1).strip()
        fact = facts_registry.get_fact(fact_id)
        if fact is None:
            unresolved.append(fact_id)
            return f"[UNRESOLVED: {fact_id}]"

        # Formatted display string e.g. "13,210.20 kg CO2e"
        disp = fact.display_str
        raw_num_str = f"{fact.number:.2f}"
        clean_num_str = f"{fact.number:g}"

        # Target line or evidence ref
        target_id = fact.evidence_line_id or fact.id
        number_map[disp] = target_id
        number_map[raw_num_str] = target_id
        number_map[clean_num_str] = target_id
        number_map[f"{{{{{fact_id}}}}}"] = target_id

        return disp

    rendered_text = PLACEHOLDER_REGEX.sub(_replace_placeholder, markdown_text)
    return rendered_text, number_map, unresolved
