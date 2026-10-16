"""
Unit and integration tests for smoke detection API and YOLO engine.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.config import settings

client = TestClient(app)


def test_smoke_model_status_endpoint():
    response = client.get("/api/vision/smoke/status")
    assert response.status_code == 200
    data = response.json()
    assert "yolo_model_loaded" in data
    assert "optical_engine_available" in data
    assert data["optical_engine_available"] is True


def test_detect_smoke_valid_image():
    valid_dir = settings.DATA_DIR / "datasets" / "valid"
    images = list(valid_dir.glob("*.jpg"))
    if not images:
        pytest.skip("No validation images found")

    sample_img = images[0]
    response = client.post(f"/api/vision/smoke/detect?image_path={sample_img.as_posix()}")
    assert response.status_code == 200
    data = response.json()
    assert "score_0_10" in data
    assert "level" in data
    assert "color" in data
    assert "maintenance_flag" in data
    assert 0.0 <= data["score_0_10"] <= 10.0
    assert data["method"] in ("yolo_model", "optical_cv")


def test_detect_smoke_file_upload(tmp_path):
    from PIL import Image, ImageDraw
    img_path = tmp_path / "test_plume.jpg"
    img = Image.new("RGB", (320, 320), color=(200, 210, 225))
    draw = ImageDraw.Draw(img)
    draw.ellipse([80, 50, 240, 210], fill=(20, 20, 20))
    img.save(str(img_path))

    with open(img_path, "rb") as f:
        response = client.post(
            "/api/vision/smoke/detect",
            files={"file": ("test_plume.jpg", f, "image/jpeg")}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score_0_10"] >= 4.0
    assert data["level"] in ("light", "heavy")
    assert data["method"] in ("yolo_model", "optical_cv")


def test_upload_bill_endpoint(tmp_path, monkeypatch):
    from PIL import Image
    img_path = tmp_path / "test_bill.png"
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    img.save(str(img_path))

    mock_ocr = [
        ("MSEDCL Bill", [[0,0],[200,0],[200,20],[0,20]], 0.95),
        ("Units 2500 kWh", [[0,20],[200,20],[200,40],[0,40]], 0.92),
        ("Total Rs. 20000.00", [[0,40],[200,40],[200,60],[0,60]], 0.90),
    ]
    monkeypatch.setattr("backend.ocr.reader.run_ocr", lambda _: mock_ocr)
    monkeypatch.setattr("backend.ocr.pipeline.run_ocr", lambda _: mock_ocr)
    monkeypatch.setattr("backend.ocr.pipeline.gemini_fallback_extract", lambda *a, **kw: {})

    with open(img_path, "rb") as f:
        resp = client.post(
            "/api/upload?media_hint=bill",
            files={"files": ("test_bill.png", f, "image/png")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "uploaded" in data
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["file_type"] == "bill"
    assert data["uploaded"][0]["bill"]["quantity"] == 2500.0


def test_calculate_endpoint():
    payload = {
        "bills": [
            {
                "id": "bill_01",
                "source_file": "elec.pdf",
                "bill_type": "electricity",
                "period_start": "2024-03-01",
                "period_end": "2024-03-31",
                "quantity": 1000.0,
                "unit": "kWh",
                "amount_inr": 8000.0,
                "supplier": "MSEDCL",
                "confidence_0_1": 0.95,
                "field_boxes": {},
                "method": "ocr",
                "user_confirmed": True,
            }
        ],
        "gensets": [
            {
                "detection": {
                    "id": "det_dg",
                    "source_file": "gen.mp4",
                    "frame_index": 1,
                    "frame_path": "data/evidence/frames/gen_1.jpg",
                    "machine_type": "diesel_generator",
                    "fuel_type": "diesel",
                    "rated_power_kw": 100.0,
                    "rated_kva": 125.0,
                    "nameplate_text": "Kirloskar 100kW",
                    "smoke": {
                        "level": "none",
                        "color": "none",
                        "score_0_10": 0.0,
                    },
                    "maintenance_flag": False,
                    "confidence_0_1": 0.9,
                },
                "hours_per_month": 10.0,
                "load_pct": 75.0,
            }
        ],
    }

    resp = client.post("/api/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "emission_lines" in data
    assert len(data["emission_lines"]) == 2
    assert "totals" in data
    assert data["totals"]["grand_total"]["co2e_kg"] > 0.0

