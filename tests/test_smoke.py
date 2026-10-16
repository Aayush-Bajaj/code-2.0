"""
Unit and integration tests for backend/vision/smoke.py (Optical Smoke Analysis).
Tests:
1. Clean image returns smoke level 'none', score < 2.0, maintenance_flag False.
2. Heavy black soot plume returns color 'black', score >= 6.0, maintenance_flag True.
3. Blueish exhaust plume returns color 'blue', maintenance_flag True.
4. Maintenance rule boundaries (5.9 vs 6.0 and color triggers).
5. Plume bounding box extraction and boundary validity.
6. Integration test on actual sample from data/datasets/valid.
"""

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import pytest

from backend.config import settings
from backend.vision.smoke import (
    analyze_smoke_optical,
    evaluate_maintenance,
    smoke_result_to_schema,
    OpticalSmokeResult,
    SMOKE_MAINTENANCE_SCORE_THRESHOLD,
)
from backend.schemas import SmokeAnalysis


@pytest.fixture
def clean_image_path(tmp_path) -> Path:
    """Create a clean background image with no smoke."""
    path = tmp_path / "clean_sky.jpg"
    # Create smooth bright background (like clear daylight/sky)
    img = Image.new("RGB", (640, 640), color=(200, 220, 240))
    img.save(str(path))
    return path


@pytest.fixture
def black_smoke_image_path(tmp_path) -> Path:
    """Create an image with a distinct dark soot plume."""
    path = tmp_path / "black_smoke.jpg"
    img = Image.new("RGB", (640, 640), color=(220, 230, 245))
    draw = ImageDraw.Draw(img)
    # Draw a dense dark plume in the upper middle
    draw.ellipse([180, 100, 460, 420], fill=(25, 25, 25))
    draw.ellipse([220, 80, 420, 300], fill=(35, 35, 35))
    img.save(str(path))
    return path


@pytest.fixture
def blue_smoke_image_path(tmp_path) -> Path:
    """Create an image with a distinct bluish plume (oil burning)."""
    path = tmp_path / "blue_smoke.jpg"
    img = Image.new("RGB", (640, 640), color=(220, 220, 220))
    draw = ImageDraw.Draw(img)
    # Bluish plume (B significantly greater than R)
    draw.ellipse([200, 120, 440, 400], fill=(70, 110, 190))
    img.save(str(path))
    return path


def test_clean_image_smoke_analysis(clean_image_path):
    res = analyze_smoke_optical(clean_image_path)
    assert isinstance(res, OpticalSmokeResult)
    assert res.level == "none"
    assert res.score_0_10 < 2.0
    assert res.maintenance_flag is False
    assert res.plume_bbox is None


def test_black_smoke_plume_analysis(black_smoke_image_path):
    res = analyze_smoke_optical(black_smoke_image_path)
    assert isinstance(res, OpticalSmokeResult)
    assert res.color == "black"
    assert res.score_0_10 >= SMOKE_MAINTENANCE_SCORE_THRESHOLD
    assert res.level == "heavy"
    assert res.maintenance_flag is True
    assert res.maintenance_reason is not None
    assert "incomplete combustion" in res.maintenance_reason
    assert res.plume_bbox is not None
    assert res.plume_bbox.x_min >= 0
    assert res.plume_bbox.x_max <= 640
    assert res.plume_bbox.y_min >= 0
    assert res.plume_bbox.y_max <= 640


def test_blue_smoke_plume_analysis(blue_smoke_image_path):
    res = analyze_smoke_optical(blue_smoke_image_path)
    assert isinstance(res, OpticalSmokeResult)
    assert res.color == "blue"
    assert res.maintenance_flag is True
    assert "incomplete combustion" in str(res.maintenance_reason)


def test_evaluate_maintenance_boundaries():
    # Below 6.0 and safe color -> False
    flag, reason = evaluate_maintenance(5.9, "grey")
    assert flag is False
    assert reason is None

    # At threshold -> True
    flag, reason = evaluate_maintenance(6.0, "grey")
    assert flag is True
    assert "incomplete combustion" in reason

    # Black color triggers maintenance regardless of score
    flag, reason = evaluate_maintenance(3.0, "black")
    assert flag is True

    # Blue color triggers maintenance regardless of score
    flag, reason = evaluate_maintenance(2.5, "blue")
    assert flag is True

    # None / empty color
    flag, _ = evaluate_maintenance(1.0, "none")
    assert flag is False


def test_smoke_result_to_schema():
    res = OpticalSmokeResult(
        score_0_10=7.5,
        level="heavy",
        color="black",
        opacity_pct=75.0,
        plume_bbox=None,
        maintenance_flag=True,
        maintenance_reason="test",
        confidence_0_1=0.9,
        method="optical_cv",
    )
    schema_obj = smoke_result_to_schema(res)
    assert isinstance(schema_obj, SmokeAnalysis)
    assert schema_obj.score_0_10 == 7.5
    assert schema_obj.level == "heavy"
    assert schema_obj.color == "black"


def test_integration_valid_dataset_image():
    """Test running optical smoke analyzer on an actual image from data/datasets/valid."""
    valid_dir = settings.DATA_DIR / "datasets" / "valid"
    if not valid_dir.exists():
        pytest.skip("data/datasets/valid not found")

    images = list(valid_dir.glob("*.jpg"))
    if not images:
        pytest.skip("No JPG images in data/datasets/valid")

    test_img = images[0]
    res = analyze_smoke_optical(test_img)
    assert isinstance(res, OpticalSmokeResult)
    assert 0.0 <= res.score_0_10 <= 10.0
    assert res.level in ("none", "light", "heavy")
    assert res.color in ("none", "black", "blue", "grey", "white")
    assert 0.0 <= res.confidence_0_1 <= 1.0
