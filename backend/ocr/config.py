"""
OCR pipeline configuration thresholds.
All values driven from here — never hardcoded in business logic.
"""

from __future__ import annotations

# Minimum per-field OCR confidence below which a field is considered missing
# and the LLM fallback is triggered.
FIELD_CONFIDENCE_THRESHOLD: float = 0.55

# If the *overall* extraction confidence is below this, trigger fallback too.
OVERALL_CONFIDENCE_THRESHOLD: float = 0.50

# Required fields that must all be present for a successful extraction
REQUIRED_FIELDS = {"bill_type", "period_start", "period_end", "quantity", "unit", "amount_inr", "supplier"}
