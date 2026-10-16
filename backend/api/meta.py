"""
backend/api/meta.py — Read-only metadata endpoints for sources and equivalent activity calculations.

Endpoints:
  - GET /meta/sources: returns factors, generator datasheets, assumptions status & how_to_fill, regulations, models.
  - GET /meta/equivalents: calculates equivalents (litres of diesel, kWh of grid electricity) strictly from factors.csv.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.config import settings

router = APIRouter(prefix="/meta", tags=["Metadata"])


class FactorSourceRow(BaseModel):
    factor_id: str
    name: str
    value: float
    unit: str
    source_name: str
    source_url: str
    year: str
    notes: str


class AssumptionMeta(BaseModel):
    key: str
    value: Any
    unit: str
    status: str  # "verified" or "needs_input"
    how_to_fill: str
    notes: str


class SourcesResponse(BaseModel):
    factors: List[FactorSourceRow]
    generator_datasheets: List[Dict[str, Any]]
    assumptions: List[AssumptionMeta]
    regulations: List[Dict[str, str]]
    models_and_tools: List[Dict[str, str]]


class EquivalentsResponse(BaseModel):
    co2e_kg: float
    diesel_litres: float
    diesel_factor: float
    diesel_text: str
    grid_kwh: float
    grid_factor: float
    grid_text: str


def _load_csv_factors() -> List[FactorSourceRow]:
    rows: List[FactorSourceRow] = []
    csv_path = settings.FACTORS_FILE
    if not csv_path.exists():
        return rows

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                val = float(r["value"])
            except ValueError:
                continue
            rows.append(
                FactorSourceRow(
                    factor_id=r["factor_id"].strip(),
                    name=r["name"].strip(),
                    value=val,
                    unit=r["unit"].strip(),
                    source_name=r["source_name"].strip(),
                    source_url=r["source_url"].strip(),
                    year=r["year"].strip(),
                    notes=r.get("notes", "").strip(),
                )
            )
    return rows


def _load_assumptions_meta() -> List[AssumptionMeta]:
    meta: List[AssumptionMeta] = []
    yaml_path = settings.DATA_DIR / "factors" / "assumptions.yaml"
    if not yaml_path.exists():
        return meta

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    for k, v in data.items():
        if not isinstance(v, dict):
            continue
        val = v.get("value")
        unit = v.get("unit", "")
        source_note = v.get("source_note", "")

        is_verified = False
        try:
            float(val)
            is_verified = True
        except (ValueError, TypeError):
            is_verified = False

        status = "verified" if is_verified else "needs_input"
        how_to_fill = source_note.replace("TODO_VERIFY - ", "").strip()

        meta.append(
            AssumptionMeta(
                key=k,
                value=val,
                unit=unit,
                status=status,
                how_to_fill=how_to_fill,
                notes=source_note,
            )
        )
    return meta


@router.get("/sources", response_model=SourcesResponse)
def get_sources():
    """
    Returns full provenance of factors, datasheets, assumptions status,
    regulatory documents, and AI/vision models.
    """
    factors = _load_csv_factors()
    assumptions = _load_assumptions_meta()

    generator_datasheets = [
        {
            "model": "Cummins C140D5P / QSB5.9-G1",
            "rated_capacity": "140 kVA / 112 kW prime power",
            "load_points": [
                {"load_pct": 75, "sfc_l_per_kwh": 0.2765, "fuel_flow_lph": 23.2},
                {"load_pct": 100, "sfc_l_per_kwh": 0.2614, "fuel_flow_lph": 29.3},
            ],
            "tolerance_pct": "+5% manufacturer tolerance applied as upper range bound",
            "interpolation_rule": "Linear interpolation between 75% and 100%. Below 75%, clamp to 75% point with load_below_datasheet_range flag.",
        },
        {
            "model": "Cummins QSB6.7-G12",
            "rated_capacity": "200 kVA / 160 kW prime power",
            "load_points": [
                {"load_pct": 75, "sfc_l_per_kwh": 0.2680, "fuel_flow_lph": 32.1},
                {"load_pct": 100, "sfc_l_per_kwh": 0.2540, "fuel_flow_lph": 40.6},
            ],
            "tolerance_pct": "+5% manufacturer tolerance applied as upper range bound",
            "interpolation_rule": "Linear interpolation between 75% and 100%. Never extrapolate.",
        },
    ]

    regulations = [
        {
            "id": "cbam",
            "title": "EU Carbon Border Adjustment Mechanism (CBAM)",
            "document": "Regulation (EU) 2023/956 Guidance on Transitional Reporting",
            "relevance": "Direct (Scope 1) and indirect (Scope 2) embedded emissions calculations for steel, aluminium, and industrial goods exports.",
        },
        {
            "id": "brsr",
            "title": "SEBI Business Responsibility and Sustainability Reporting (BRSR)",
            "document": "SEBI BRSR Core Framework Principle 6 (Environment)",
            "relevance": "Mandatory Scope 1 and Scope 2 GHG metrics for top 1000 listed entities and Tier-1 supply chain disclosures.",
        },
        {
            "id": "ghg_protocol",
            "title": "GHG Protocol Corporate Standard",
            "document": "WRI / WBCSD Corporate Accounting and Reporting Standard",
            "relevance": "Accounting boundary rules (Scope 1, 2, 3), activity data multiplication, and inventory uncertainty ranges.",
        },
    ]

    models_and_tools = [
        {
            "component": "LLM & Vision Text Generation",
            "technology": "Google Gemini 2.5 / 3.8",
            "role": "Multimodal bill structure extraction and narrative generation constrained strictly to locked FACTS.",
        },
        {
            "component": "Document OCR",
            "technology": "EasyOCR",
            "role": "Local text and bounding box extraction from electricity invoices, diesel slips, and nameplates.",
        },
        {
            "component": "Machinery & Smoke Vision",
            "technology": "Ultralytics YOLOv8 + Optical Ringelmann Engine",
            "role": "Detection of industrial machinery and plume opacity/color evaluation for maintenance flags.",
        },
        {
            "component": "Vector Embeddings & RAG",
            "technology": "Sentence-Transformers (all-MiniLM-L6-v2) + ChromaDB",
            "role": "Semantic retrieval of regulatory text passages with strict citation enforcement.",
        },
    ]

    return SourcesResponse(
        factors=factors,
        generator_datasheets=generator_datasheets,
        assumptions=assumptions,
        regulations=regulations,
        models_and_tools=models_and_tools,
    )


@router.get("/equivalents", response_model=EquivalentsResponse)
def get_equivalents(co2e_kg: float = Query(..., ge=0.0, description="Emissions in kg CO2e to convert")):
    """
    Converts a kg CO2e value into plain-language equivalents (litres of diesel, kWh of grid electricity)
    strictly derived from factors.csv. Never hardcodes conversion constants.
    """
    factors = _load_csv_factors()
    factor_dict = {f.factor_id: f for f in factors}

    # Diesel factor
    diesel_f = factor_dict.get("diesel_mineral_l")
    if not diesel_f or diesel_f.value <= 0:
        raise HTTPException(status_code=500, detail="Missing or invalid 'diesel_mineral_l' in factors.csv")

    # Grid factor
    grid_f = factor_dict.get("grid_india_wa")
    if not grid_f or grid_f.value <= 0:
        raise HTTPException(status_code=500, detail="Missing or invalid 'grid_india_wa' in factors.csv")

    diesel_litres = co2e_kg / diesel_f.value
    grid_kwh = co2e_kg / grid_f.value

    return EquivalentsResponse(
        co2e_kg=co2e_kg,
        diesel_litres=round(diesel_litres, 1),
        diesel_factor=diesel_f.value,
        diesel_text=f"Same as burning {diesel_litres:,.1f} litres of diesel fuel",
        grid_kwh=round(grid_kwh, 1),
        grid_factor=grid_f.value,
        grid_text=f"Equivalent to {grid_kwh:,.1f} kWh of grid electricity",
    )
