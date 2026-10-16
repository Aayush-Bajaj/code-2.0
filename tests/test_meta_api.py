"""
Tests for backend/api/meta.py:
  - GET /meta/sources: factor rows, datasheets, assumptions status & how_to_fill.
  - GET /meta/equivalents: derives diesel litres and grid kWh strictly from factors.csv.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_meta_sources(client):
    resp = client.get("/meta/sources")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "factors" in data
    assert len(data["factors"]) >= 5
    factor_ids = [f["factor_id"] for f in data["factors"]]
    assert "diesel_mineral_l" in factor_ids
    assert "grid_india_wa" in factor_ids

    assert "generator_datasheets" in data
    assert len(data["generator_datasheets"]) >= 1

    assert "assumptions" in data
    assert len(data["assumptions"]) >= 4
    for a in data["assumptions"]:
        assert a["status"] in ("verified", "needs_input")
        assert "how_to_fill" in a

    assert "regulations" in data
    assert "models_and_tools" in data


def test_get_meta_equivalents(client):
    # Test converting 2680.0 kg CO2e
    # In factors.csv, diesel_mineral_l = 2.68 kg CO2e/L
    # 2680.0 / 2.68 = 1000.0 litres of diesel
    resp = client.get("/meta/equivalents?co2e_kg=2680.0")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["co2e_kg"] == 2680.0
    assert data["diesel_litres"] == pytest.approx(1000.0, rel=1e-2)
    assert data["diesel_factor"] == 2.68
    assert "1,000.0" in data["diesel_text"] or "1000.0" in data["diesel_text"]

    # In factors.csv, grid_india_wa = 0.716 kg CO2e/kWh
    # 2680.0 / 0.716 = ~3743.0 kWh
    assert data["grid_factor"] == 0.716
    assert data["grid_kwh"] == pytest.approx(2680.0 / 0.716, rel=1e-2)


def test_get_meta_equivalents_validation(client):
    # Negative co2e_kg should be rejected
    resp = client.get("/meta/equivalents?co2e_kg=-10.0")
    assert resp.status_code == 422
