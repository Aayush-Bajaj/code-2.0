"""
backend/rag/validator.py — Strict numerical audit and hallucination guardrail.

Extracts every numeric token in the post-processed report markdown.
Verifies each number against:
  1. Engine values in the locked FACTS registry.
  2. Numbers explicitly present in cited regulatory passages (page numbers, dates, regulation IDs).
  3. Structural constants (Scope 1/2/3, section indices 1-6).

If any number cannot be mathematically traced, the validation fails and returns untraceable_numbers,
triggering an automated regeneration attempt or deterministic fallback template.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple
from backend.rag.facts import FactsRegistry
from backend.rag.retriever import RetrievedChunk

# Matches integers, decimals, numbers with commas (e.g. 99999.9, 1,072.00, 84.7, 100)
NUMBER_PATTERN = re.compile(r"(?<![a-zA-Z_])(\d+(?:,\d{3})*(?:\.\d+)?|\d*\.\d+)(?:\b|%|kg|t|kWh|L)?")


# Standard structural / scope constants that are not emission numbers
STRUCTURAL_NUMBERS: Set[float] = {
    0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0,  # Single-digit indices / Scopes / Ringelmann
    2023.0, 2024.0, 2025.0, 2026.0, 2030.0,  # Standard regulation & reporting years
    956.0,  # EU 2023/956 regulation number
}


def _extract_numbers_from_text(text: str) -> List[Tuple[float, str, str]]:
    """
    Extracts all numeric tokens from text along with surrounding context snippet.
    Returns: list of (numeric_value, raw_str, context_snippet)
    """
    results: List[Tuple[float, str, str]] = []
    lines = text.splitlines()

    for line in lines:
        for match in NUMBER_PATTERN.finditer(line):
            raw_str = match.group(1).replace(",", "").strip()
            if not raw_str:
                continue
            try:
                val = float(raw_str)
            except ValueError:
                continue

            # Context snippet around match
            start = max(0, match.start() - 25)
            end = min(len(line), match.end() + 25)
            snippet = line[start:end].strip()

            results.append((val, raw_str, snippet))

    return results


def _extract_numbers_from_chunks(chunks: List[RetrievedChunk]) -> Set[float]:
    """Extracts all numbers appearing in retrieved regulatory document passages."""
    allowed: Set[float] = set()
    for chunk in chunks:
        # Include page number
        allowed.add(float(chunk.page))
        # Include all numbers in passage text
        for val, _, _ in _extract_numbers_from_text(chunk.text):
            allowed.add(val)
    return allowed


def validate_report_numbers(
    sections_markdown: Dict[str, str],
    facts_registry: FactsRegistry,
    retrieved_chunks: List[RetrievedChunk],
    tolerance: float = 0.05,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validates that every single number in the rendered report is traceable.
    Returns:
      (passed: bool, untraceable_numbers: List[Dict[str, Any]])
    """
    untraceable: List[Dict[str, Any]] = []

    # 1. Collect all allowed numbers from FACTS
    facts_numbers = facts_registry.get_allowed_numbers()

    # 2. Collect allowed numbers from regulatory passages
    passage_numbers = _extract_numbers_from_chunks(retrieved_chunks)

    # Combined allowed set
    for section_title, content in sections_markdown.items():
        extracted = _extract_numbers_from_text(content)
        for val, raw_str, snippet in extracted:
            # Check 1: Structural number?
            if val in STRUCTURAL_NUMBERS:
                continue

            # Check 2: Regulatory passage number?
            if any(abs(val - p_num) < 1e-4 for p_num in passage_numbers):
                continue

            # Check 3: Facts registry number?
            matched_fact = False
            for f_val in facts_numbers:
                if abs(val - f_val) < tolerance or (f_val != 0 and abs(val - f_val) / abs(f_val) < 0.01):
                    matched_fact = True
                    break

            if matched_fact:
                continue

            # If none matched, this number is untraceable!
            untraceable.append({
                "number": raw_str,
                "value": val,
                "section": section_title,
                "snippet": snippet,
                "reason": "Number does not trace back to engine calculations or cited regulatory documents",
            })

    passed = len(untraceable) == 0
    return passed, untraceable
