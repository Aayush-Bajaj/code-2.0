"""
Vision inspection pipeline implementation.
Complies with AGENTS.md, SPEC.md, and Vision Protocol.
"""

import os
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import ValidationError, BaseModel, Field

from backend.config import settings
from backend import llm
from backend.schemas import Detection, SmokeAnalysis, BoundingBox, MachineType, SmokeLevel, SmokeColor
from backend.vision.prompts import INSPECTION_SYSTEM_PROMPT, REPAIR_PROMPT
from backend.vision.frames import process_media_frames

logger = logging.getLogger(__name__)

# Configurable maintenance flag rules (never hardcoded in prompt)
SMOKE_MAINTENANCE_SCORE_THRESHOLD = 6.0
SMOKE_MAINTENANCE_TRIGGER_COLORS = {"black", "blue"}
MAINTENANCE_REASON = "possible incomplete combustion or oil burning, inspect"


class RawSmokeAnalysis(BaseModel):
    level: SmokeLevel = Field(default="none")
    color: SmokeColor = Field(default="none")
    score_0_10: float = Field(default=0.0, ge=0.0, le=10.0)

    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs):
        if isinstance(obj, dict):
            # Normalize synonyms
            lvl = str(obj.get("level", "none")).lower().strip()
            if lvl in ("low", "medium", "moderate"):
                obj["level"] = "light"
            elif lvl in ("high", "severe", "dense"):
                obj["level"] = "heavy"
            elif lvl not in ("none", "light", "heavy"):
                obj["level"] = "none"

            clr = str(obj.get("color", "none")).lower().strip()
            if clr in ("gray", "dark"):
                obj["color"] = "grey"
            elif clr not in ("white", "black", "blue", "grey", "none"):
                obj["color"] = "none"

            try:
                score = float(obj.get("score_0_10", 0.0))
                obj["score_0_10"] = max(0.0, min(10.0, score))
            except Exception:
                obj["score_0_10"] = 0.0
        return super().model_validate(obj, *args, **kwargs)


class RawInspectionResult(BaseModel):
    machine_type: MachineType = Field(default="other")
    fuel_type: Optional[str] = None
    rated_power_kw: Optional[float] = None
    rated_kva: Optional[float] = None
    nameplate_text: Optional[str] = None
    smoke: RawSmokeAnalysis = Field(default_factory=RawSmokeAnalysis)
    confidence_0_1: float = Field(default=0.5, ge=0.0, le=1.0)
    bbox: Optional[BoundingBox] = None

    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs):
        if isinstance(obj, dict):
            m_type = str(obj.get("machine_type", "other")).lower().strip()
            # Normalize common synonyms to closed list
            if "generator" in m_type or "genset" in m_type:
                obj["machine_type"] = "diesel_generator"
            elif "forklift" in m_type:
                obj["machine_type"] = "forklift"
            elif "truck" in m_type or "car" in m_type or "lorry" in m_type or "vehicle" in m_type:
                obj["machine_type"] = "truck"
            elif "boiler" in m_type:
                obj["machine_type"] = "boiler"
            elif "furnace" in m_type:
                obj["machine_type"] = "furnace"
            elif "compressor" in m_type:
                obj["machine_type"] = "compressor"
            elif m_type not in ("diesel_generator", "forklift", "truck", "boiler", "furnace", "compressor", "other", "none"):
                obj["machine_type"] = "other"

            # Normalize bbox if sent as [ymin, xmin, ymax, xmax] list
            bbox_raw = obj.get("bbox")
            if isinstance(bbox_raw, (list, tuple)) and len(bbox_raw) >= 4:
                obj["bbox"] = {
                    "x_min": float(bbox_raw[0]),
                    "y_min": float(bbox_raw[1]),
                    "x_max": float(bbox_raw[2]),
                    "y_max": float(bbox_raw[3]),
                }
            elif not isinstance(bbox_raw, dict):
                obj["bbox"] = None
        return super().model_validate(obj, *args, **kwargs)



def check_maintenance_flag(smoke: SmokeAnalysis) -> Tuple[bool, Optional[str]]:
    """
    Evaluates whether maintenance flag should be raised based on config:
    smoke score >= 6.0 or color in (black, blue) -> maintenance_flag=true
    """
    score = smoke.score_0_10
    color = smoke.color.lower() if smoke.color else "none"

    if score >= SMOKE_MAINTENANCE_SCORE_THRESHOLD or color in SMOKE_MAINTENANCE_TRIGGER_COLORS:
        return True, MAINTENANCE_REASON
    return False, None


def _get_mock_detection(source_file: str, frame_path: str, frame_index: int = 0) -> Detection:
    """Return realistic mock detections for demo clips when MOCK_VISION=1."""
    name_lower = Path(source_file).name.lower()
    
    if "nosmoke" in name_lower:
        smoke = SmokeAnalysis(level="none", color="none", score_0_10=1.0)
        m_flag = False
        m_type = "diesel_generator"
        nameplate = "CUMMINS 200 kVA SILENT DIESEL GENERATOR"
        kw = 160.0
        kva = 200.0
        fuel = "diesel"
    elif "blacksmoke" in name_lower or "smoke" in name_lower:
        smoke = SmokeAnalysis(level="heavy", color="black", score_0_10=8.4)
        m_flag = True
        m_type: MachineType = "diesel_generator"
        nameplate = "KIRLOSKAR GREEN 125 kW DIESEL GENSET 415V"
        kw = 125.0
        kva = 156.25
        fuel = "diesel"
    elif "forklift" in name_lower:
        smoke = SmokeAnalysis(level="none", color="none", score_0_10=0.5)
        m_flag = False
        m_type = "forklift"
        nameplate = "TOYOTA 2.5T DIESEL FORKLIFT 48V / DIESEL"
        kw = 37.0
        kva = None
        fuel = "diesel"
    elif "truck" in name_lower:
        smoke = SmokeAnalysis(level="light", color="grey", score_0_10=3.0)
        m_flag = False
        m_type = "truck"
        nameplate = "TATA MOTORS 1618 CR 16 TON HEAVY TRUCK"
        kw = 134.0
        kva = None
        fuel = "diesel"
    else:
        smoke = SmokeAnalysis(level="none", color="none", score_0_10=0.0)
        m_flag = False
        m_type = "other"
        nameplate = None
        kw = None
        kva = None
        fuel = None

    det_id = f"det_{Path(source_file).stem}_{frame_index}"
    return Detection(
        id=det_id,
        source_file=Path(source_file).name,
        frame_index=frame_index,
        frame_path=frame_path,
        machine_type=m_type,
        fuel_type=fuel,
        rated_power_kw=kw,
        rated_kva=kva,
        nameplate_text=nameplate,
        smoke=smoke,
        maintenance_flag=m_flag,
        confidence_0_1=0.92,
        bbox=BoundingBox(x_min=100.0, y_min=80.0, x_max=500.0, y_max=600.0),
    )


def _inspect_frame_with_llm(
    frame_bytes: bytes,
    source_file: str,
    frame_index: int,
    frame_path_str: str,
) -> Detection:
    """
    Call backend/llm.generate_json with the frame and inspection prompt.
    Validate with Pydantic. On invalid output, retry once with a repair instruction.
    On a second failure, return a low-confidence Detection with machine_type='other'
    and a flag 'vision_failed'. Never crashes.
    """
    det_id = f"det_{Path(source_file).stem}_{frame_index}"

    def fallback_detection(err_msg: str) -> Detection:
        logger.warning(f"Vision inspection failed for {source_file} frame {frame_index}: {err_msg}")
        smoke = SmokeAnalysis(level="none", color="none", score_0_10=0.0)
        return Detection(
            id=det_id,
            source_file=Path(source_file).name,
            frame_index=frame_index,
            frame_path=frame_path_str,
            machine_type="other",
            fuel_type=None,
            rated_power_kw=None,
            rated_kva=None,
            nameplate_text=None,
            smoke=smoke,
            maintenance_flag=False,
            confidence_0_1=0.1,
            bbox=None,
        )

    # First Attempt
    try:
        raw_json = llm.generate_json(prompt=INSPECTION_SYSTEM_PROMPT, images=[frame_bytes])
        parsed = RawInspectionResult.model_validate(raw_json)
    except Exception as first_exc:
        # Retry once with repair prompt
        logger.info(f"First vision LLM parsing attempt failed ({first_exc}), retrying with repair prompt...")
        try:
            repair_prompt = REPAIR_PROMPT.format(invalid_output=str(first_exc))
            # Provide the frame image as well during the repair retry
            repaired_json = llm.generate_json(prompt=repair_prompt, images=[frame_bytes])
            parsed = RawInspectionResult.model_validate(repaired_json)
        except Exception as second_exc:
            det = fallback_detection(f"Repair retry failed: {second_exc}")
            # Attach vision_failed indicator
            det.nameplate_text = "vision_failed"
            return det

    smoke_obj = SmokeAnalysis(
        level=parsed.smoke.level,
        color=parsed.smoke.color,
        score_0_10=parsed.smoke.score_0_10,
    )

    # Optical smoke analysis & plume localization
    bbox = parsed.bbox
    try:
        from backend.vision.smoke import analyze_smoke_optical, smoke_result_to_schema
        opt_res = analyze_smoke_optical(frame_bytes)
        # If optical analysis detects a higher smoke severity or confirms a plume
        if opt_res.score_0_10 > smoke_obj.score_0_10:
            smoke_obj = smoke_result_to_schema(opt_res)
        if bbox is None and opt_res.plume_bbox is not None:
            bbox = opt_res.plume_bbox
    except Exception as opt_err:
        logger.debug(f"Optical smoke analysis skipped: {opt_err}")

    m_flag, _ = check_maintenance_flag(smoke_obj)

    return Detection(
        id=det_id,
        source_file=Path(source_file).name,
        frame_index=frame_index,
        frame_path=frame_path_str,
        machine_type=parsed.machine_type,
        fuel_type=parsed.fuel_type,
        rated_power_kw=parsed.rated_power_kw,
        rated_kva=parsed.rated_kva,
        nameplate_text=parsed.nameplate_text,
        smoke=smoke_obj,
        maintenance_flag=m_flag,
        confidence_0_1=parsed.confidence_0_1,
        bbox=bbox,
    )


def merge_detections(detections: List[Detection], source_file: str) -> Detection:
    """
    Merge per-frame outputs into one Detection per distinct machine:
    - majority vote on machine_type
    - highest-confidence nameplate text (or most detailed)
    - worst (highest) smoke score
    - re-evaluate maintenance flag
    """
    if not detections:
        smoke = SmokeAnalysis(level="none", color="none", score_0_10=0.0)
        return Detection(
            id=f"det_{Path(source_file).stem}_merged",
            source_file=Path(source_file).name,
            frame_index=0,
            frame_path=f"data/evidence/frames/{Path(source_file).stem}_0.jpg",
            machine_type="other",
            fuel_type=None,
            rated_power_kw=None,
            rated_kva=None,
            nameplate_text="vision_failed",
            smoke=smoke,
            maintenance_flag=False,
            confidence_0_1=0.1,
            bbox=None,
        )

    if len(detections) == 1:
        return detections[0]

    # 1. Majority vote on machine_type
    type_counts = Counter(d.machine_type for d in detections)
    # Exclude 'none' or 'other' if better types exist
    candidate_types = [t for t in type_counts.keys() if t not in ("none", "other")]
    if candidate_types:
        majority_type = max(candidate_types, key=lambda t: type_counts[t])
    else:
        majority_type = type_counts.most_common(1)[0][0]

    # 2. Highest confidence nameplate text
    nameplate_candidates = [
        d for d in detections
        if d.nameplate_text and d.nameplate_text != "vision_failed"
    ]
    if nameplate_candidates:
        best_nameplate_det = max(nameplate_candidates, key=lambda d: d.confidence_0_1)
        nameplate_text = best_nameplate_det.nameplate_text
        fuel_type = best_nameplate_det.fuel_type
        rated_power_kw = best_nameplate_det.rated_power_kw
        rated_kva = best_nameplate_det.rated_kva
    else:
        # Check if all had vision_failed
        if all(d.nameplate_text == "vision_failed" for d in detections):
            nameplate_text = "vision_failed"
        else:
            nameplate_text = None
        fuel_type = next((d.fuel_type for d in detections if d.fuel_type), None)
        rated_power_kw = next((d.rated_power_kw for d in detections if d.rated_power_kw is not None), None)
        rated_kva = next((d.rated_kva for d in detections if d.rated_kva is not None), None)

    # 3. Worst (highest) smoke score
    worst_smoke_det = max(detections, key=lambda d: d.smoke.score_0_10)
    worst_smoke = worst_smoke_det.smoke

    # 4. Maintenance flag
    maintenance_flag, _ = check_maintenance_flag(worst_smoke)

    # Average confidence among matching majority_type detections
    matching = [d for d in detections if d.machine_type == majority_type]
    avg_conf = sum(d.confidence_0_1 for d in matching) / len(matching) if matching else 0.5
    avg_conf = round(min(1.0, max(0.0, avg_conf)), 2)

    # Pick frame path with the highest smoke score or primary frame
    selected_frame = worst_smoke_det.frame_path
    selected_idx = worst_smoke_det.frame_index

    # Bounding box from best detection
    bbox = worst_smoke_det.bbox or next((d.bbox for d in detections if d.bbox), None)

    merged_id = f"det_{Path(source_file).stem}_merged"
    return Detection(
        id=merged_id,
        source_file=Path(source_file).name,
        frame_index=selected_idx,
        frame_path=selected_frame,
        machine_type=majority_type,
        fuel_type=fuel_type,
        rated_power_kw=rated_power_kw,
        rated_kva=rated_kva,
        nameplate_text=nameplate_text,
        smoke=worst_smoke,
        maintenance_flag=maintenance_flag,
        confidence_0_1=avg_conf,
        bbox=bbox,
    )


def process_media(
    media_path: str,
    file_id: Optional[str] = None,
    merge: bool = True,
) -> List[Detection]:
    """
    Full Vision Pipeline:
    1. Sample up to 8 frames, keep 4 sharpest (variance of Laplacian) or 1 for image.
    2. Save each used frame to data/evidence/frames/<file_id>_<idx>.jpg.
    3. Call LLM / Mock with inspection prompt and schema validation.
    4. Merge per-frame outputs into consolidated Detection if merge=True.
    5. Returns list of Detection objects (1 item if merged).
    """
    path = Path(media_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Media file not found: {media_path}")

    actual_file_id = file_id or path.stem

    # 1 & 2: Process frames and save to data/evidence/frames
    frames_data = process_media_frames(str(path), actual_file_id)

    # Check MOCK_VISION switch
    if settings.MOCK_VISION:
        per_frame = [
            _get_mock_detection(
                source_file=str(path.name),
                frame_path=str(saved_path.relative_to(settings.BASE_DIR)).replace("\\", "/"),
                frame_index=idx,
            )
            for idx, saved_path, _ in frames_data
        ]
        if merge:
            return [merge_detections(per_frame, path.name)]
        return per_frame

    # 3: Inspect each frame
    per_frame_detections: List[Detection] = []
    for idx, saved_path, frame_bytes in frames_data:
        rel_path_str = str(saved_path.relative_to(settings.BASE_DIR)).replace("\\", "/")
        det = _inspect_frame_with_llm(
            frame_bytes=frame_bytes,
            source_file=path.name,
            frame_index=idx,
            frame_path_str=rel_path_str,
        )
        per_frame_detections.append(det)

    if merge:
        return [merge_detections(per_frame_detections, path.name)]
    return per_frame_detections
