"""
LLM (Gemini) fallback for bill extraction.
Called when OCR confidence is below threshold or required fields are missing.
Always marks method='gemini_fallback'. Never auto-confirms.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Dict, Optional

from PIL import Image

from backend import llm

logger = logging.getLogger(__name__)

_FALLBACK_PROMPT = """\
You are a bill parsing assistant. Extract data from this Indian utility or freight invoice image.
Return ONLY valid JSON — no prose, no markdown, no code fences.

Required JSON schema:
{
  "bill_type": "<electricity|diesel|freight>",
  "supplier": "<company name string>",
  "period_start": "<YYYY-MM-DD>",
  "period_end": "<YYYY-MM-DD>",
  "quantity": <float>,
  "unit": "<kWh|L|tonne-km|kg>",
  "amount_inr": <float>,
  "confidence_0_1": <float 0-1>
}

Rules:
- bill_type MUST be one of: electricity, diesel, freight
- unit MUST be one of: kWh, L, tonne-km, kg
- All dates in YYYY-MM-DD format
- quantity and amount_inr must be numeric (no commas, no currency symbols)
- If a field truly cannot be determined, use null
- Do NOT invent numbers; if unreadable, use null
- confidence_0_1 reflects your certainty (0=no idea, 1=certain)
"""


def gemini_fallback_extract(
    image_path: str,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Call Gemini with the bill image and a strict JSON-only prompt.
    Returns a dict with extracted fields. On any failure returns an empty dict.
    existing: fields already parsed by OCR (may be partially filled).
    """
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        result = llm.generate_json(prompt=_FALLBACK_PROMPT, images=[image_bytes])
        logger.info(f"Gemini fallback returned: {result}")
        return result
    except Exception as exc:
        logger.warning(f"Gemini fallback failed for {image_path}: {exc}")
        return {}
