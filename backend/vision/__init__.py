"""
Vision Protocol Package.
Provides video/image inspection, frame extraction, optical smoke evaluation,
and detection merging compliant with SPEC.md and AGENTS.md.
"""

from backend.vision.pipeline import (
    process_media,
    merge_detections,
    check_maintenance_flag,
    SMOKE_MAINTENANCE_SCORE_THRESHOLD,
    SMOKE_MAINTENANCE_TRIGGER_COLORS,
    MAINTENANCE_REASON,
)
from backend.vision.frames import process_media_frames, calculate_sharpness
from backend.vision.prompts import INSPECTION_SYSTEM_PROMPT, REPAIR_PROMPT
from backend.vision.smoke import (
    analyze_smoke_optical,
    evaluate_maintenance,
    smoke_result_to_schema,
    OpticalSmokeResult,
)

__all__ = [
    "process_media",
    "merge_detections",
    "check_maintenance_flag",
    "process_media_frames",
    "calculate_sharpness",
    "INSPECTION_SYSTEM_PROMPT",
    "REPAIR_PROMPT",
    "SMOKE_MAINTENANCE_SCORE_THRESHOLD",
    "SMOKE_MAINTENANCE_TRIGGER_COLORS",
    "MAINTENANCE_REASON",
    "analyze_smoke_optical",
    "evaluate_maintenance",
    "smoke_result_to_schema",
    "OpticalSmokeResult",
]
