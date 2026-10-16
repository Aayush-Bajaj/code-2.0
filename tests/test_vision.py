"""
Unit and integration tests for backend/vision.
Tests with Gemini client mocked:
1. Valid JSON
2. Invalid JSON then repair
3. API failure fallback (never crash, returns other with vision_failed)
4. Frame extraction and variance of Laplacian sharpness ranking
5. Merge logic (majority vote, highest confidence nameplate, worst smoke score)
6. Maintenance flag thresholds (score >= 6.0 and black/blue color triggers)
7. MOCK_VISION switch
"""

import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import pytest

from backend.config import settings
from backend import llm
from backend.schemas import Detection, SmokeAnalysis, BoundingBox
from backend.vision import (
    process_media,
    merge_detections,
    check_maintenance_flag,
    process_media_frames,
    calculate_sharpness,
    SMOKE_MAINTENANCE_SCORE_THRESHOLD,
)
from backend.vision.pipeline import _inspect_frame_with_llm, _get_mock_detection


@pytest.fixture
def dummy_image_file(tmp_path) -> Path:
    img_path = tmp_path / "test_image.jpg"
    img = Image.new("RGB", (200, 200), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw high-contrast shapes to produce high Laplacian variance
    draw.rectangle([20, 20, 100, 100], fill=(255, 255, 255))
    draw.line([0, 0, 200, 200], fill=(255, 0, 0), width=5)
    img.save(str(img_path))
    return img_path


@pytest.fixture
def dummy_multiframe_file(tmp_path) -> Path:
    # Use multi-frame GIF to test multi-frame sampling without external cv2 DLL
    gif_path = tmp_path / "test_video.gif"
    frames = []
    for i in range(10):
        im = Image.new("RGB", (128, 128), color=(i * 20, i * 20, i * 20))
        draw = ImageDraw.Draw(im)
        if i == 4:
            # Frame 4 has highest edge contrast
            draw.line([0, 0, 128, 128], fill=(255, 255, 255), width=4)
            draw.rectangle([10, 10, 50, 50], fill=(255, 0, 0))
        frames.append(im)
    frames[0].save(str(gif_path), save_all=True, append_images=frames[1:], duration=100, loop=0)
    return gif_path


def test_calculate_sharpness():
    blank = Image.new("RGB", (100, 100), color=(0, 0, 0))
    sharp_blank = calculate_sharpness(blank)
    assert sharp_blank == 0.0

    textured_bytes = bytearray(i % 256 for i in range(100 * 100 * 3))
    textured_arr = np.frombuffer(textured_bytes, dtype=np.uint8).reshape((100, 100, 3))
    sharp_textured = calculate_sharpness(textured_arr)
    assert sharp_textured > sharp_blank


def test_process_media_frames_image(dummy_image_file):
    frames = process_media_frames(str(dummy_image_file), file_id="img1")
    assert len(frames) == 1
    idx, saved_path, frame_bytes = frames[0]
    assert idx == 0
    assert saved_path.exists()
    assert len(frame_bytes) > 0


def test_process_media_frames_multiframe(dummy_multiframe_file):
    # From 10 frames, sample up to 8, select top 4 sharpest
    frames = process_media_frames(str(dummy_multiframe_file), file_id="vid1", max_sample_frames=8, keep_top_k=4)
    assert len(frames) == 4
    for idx, path, b in frames:
        assert path.exists()
        assert len(b) > 0


def test_valid_json_inspection(monkeypatch):
    sample_response = {
        "machine_type": "diesel_generator",
        "fuel_type": "diesel",
        "rated_power_kw": 125.0,
        "rated_kva": 156.25,
        "nameplate_text": "KIRLOSKAR GREEN 125 kW",
        "smoke": {
            "level": "heavy",
            "color": "black",
            "score_0_10": 8.5
        },
        "confidence_0_1": 0.95,
        "bbox": {"x_min": 50.0, "y_min": 60.0, "x_max": 200.0, "y_max": 300.0}
    }

    monkeypatch.setattr(llm, "generate_json", lambda prompt, images=None: sample_response)

    det = _inspect_frame_with_llm(
        frame_bytes=b"fake_bytes",
        source_file="test.mp4",
        frame_index=0,
        frame_path_str="data/evidence/frames/test_0.jpg"
    )

    assert det.machine_type == "diesel_generator"
    assert det.rated_power_kw == 125.0
    assert det.smoke.score_0_10 == 8.5
    assert det.maintenance_flag is True
    assert det.confidence_0_1 == 0.95
    assert det.nameplate_text == "KIRLOSKAR GREEN 125 kW"


def test_invalid_json_then_repair(monkeypatch):
    call_count = {"val": 0}

    valid_response = {
        "machine_type": "forklift",
        "fuel_type": "diesel",
        "rated_power_kw": 40.0,
        "nameplate_text": "Toyota Forklift",
        "smoke": {
            "level": "none",
            "color": "none",
            "score_0_10": 0.5
        },
        "confidence_0_1": 0.9
    }

    def mock_generate_json(prompt, images=None):
        call_count["val"] += 1
        if call_count["val"] == 1:
            # First attempt returns malformed structure that fails model_validate
            raise ValueError("Malformed JSON or schema failure from LLM")
        else:
            # Repair attempt succeeds
            return valid_response

    monkeypatch.setattr(llm, "generate_json", mock_generate_json)

    det = _inspect_frame_with_llm(
        frame_bytes=b"fake_bytes",
        source_file="forklift.mp4",
        frame_index=1,
        frame_path_str="data/evidence/frames/forklift_1.jpg"
    )

    assert call_count["val"] == 2
    assert det.machine_type == "forklift"
    assert det.smoke.score_0_10 == 0.5
    assert det.maintenance_flag is False


def test_api_failure_fallback_never_crashes(monkeypatch):
    def mock_fail(prompt, images=None):
        raise RuntimeError("Network timeout or LLM error")

    monkeypatch.setattr(llm, "generate_json", mock_fail)

    det = _inspect_frame_with_llm(
        frame_bytes=b"fake_bytes",
        source_file="fail_test.mp4",
        frame_index=2,
        frame_path_str="data/evidence/frames/fail_test_2.jpg"
    )

    assert det.machine_type == "other"
    assert det.nameplate_text == "vision_failed"
    assert det.confidence_0_1 == 0.1
    assert det.smoke.level == "none"
    assert det.maintenance_flag is False


def test_merge_detections_logic():
    det1 = Detection(
        id="det1",
        source_file="video.mp4",
        frame_index=0,
        frame_path="data/evidence/frames/video_0.jpg",
        machine_type="diesel_generator",
        nameplate_text="Kirloskar 100kW",
        smoke=SmokeAnalysis(level="light", color="grey", score_0_10=3.0),
        maintenance_flag=False,
        confidence_0_1=0.8,
    )
    det2 = Detection(
        id="det2",
        source_file="video.mp4",
        frame_index=1,
        frame_path="data/evidence/frames/video_1.jpg",
        machine_type="diesel_generator",
        nameplate_text="Kirloskar 100kW DG",
        smoke=SmokeAnalysis(level="heavy", color="black", score_0_10=8.0),
        maintenance_flag=True,
        confidence_0_1=0.95,
    )
    det3 = Detection(
        id="det3",
        source_file="video.mp4",
        frame_index=2,
        frame_path="data/evidence/frames/video_2.jpg",
        machine_type="boiler",
        nameplate_text=None,
        smoke=SmokeAnalysis(level="light", color="white", score_0_10=2.0),
        maintenance_flag=False,
        confidence_0_1=0.6,
    )

    merged = merge_detections([det1, det2, det3], "video.mp4")

    # Majority vote
    assert merged.machine_type == "diesel_generator"
    # Highest confidence nameplate
    assert merged.nameplate_text == "Kirloskar 100kW DG"
    # Worst smoke score
    assert merged.smoke.score_0_10 == 8.0
    assert merged.smoke.color == "black"
    assert merged.maintenance_flag is True


def test_maintenance_flag_thresholds():
    # Score < 6.0 and safe color -> False
    smoke_safe = SmokeAnalysis(level="light", color="grey", score_0_10=5.9)
    flag, _ = check_maintenance_flag(smoke_safe)
    assert flag is False

    # Score >= 6.0 -> True
    smoke_high = SmokeAnalysis(level="heavy", color="white", score_0_10=6.0)
    flag, reason = check_maintenance_flag(smoke_high)
    assert flag is True
    assert "incomplete combustion" in reason

    # Black smoke even with score < 6 -> True
    smoke_black = SmokeAnalysis(level="light", color="black", score_0_10=4.0)
    flag, _ = check_maintenance_flag(smoke_black)
    assert flag is True

    # Blue smoke even with score < 6 -> True
    smoke_blue = SmokeAnalysis(level="light", color="blue", score_0_10=3.0)
    flag, _ = check_maintenance_flag(smoke_blue)
    assert flag is True


def test_mock_vision_pipeline(dummy_image_file, monkeypatch):
    monkeypatch.setattr(settings, "MOCK_VISION", True)

    results = process_media(str(dummy_image_file), merge=True)
    assert len(results) == 1
    det = results[0]
    assert isinstance(det, Detection)
    assert det.source_file == dummy_image_file.name
    assert Path(det.frame_path).name.endswith(".jpg")
