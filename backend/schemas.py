from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# -------------------------------------------------------------------------
# Sub-models
# -------------------------------------------------------------------------

MachineType = Literal[
    "diesel_generator",
    "forklift",
    "truck",
    "boiler",
    "furnace",
    "compressor",
    "other",
    "none",
]

SmokeLevel = Literal["none", "light", "heavy"]
SmokeColor = Literal["white", "black", "blue", "grey", "none"]


class SmokeAnalysis(BaseModel):
    level: SmokeLevel = Field(..., description="Opacity level: none, light, or heavy")
    color: SmokeColor = Field(..., description="Smoke color signature")
    score_0_10: float = Field(..., ge=0.0, le=10.0, description="Smoke opacity score from 0.0 to 10.0")


class BoundingBox(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float


class ValidationSummary(BaseModel):
    passed: bool = Field(..., description="Whether validation checks passed")
    untraceable_numbers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of any numbers that lack an evidence trace",
    )


# -------------------------------------------------------------------------
# 1. Detection Contract
# -------------------------------------------------------------------------

class Detection(BaseModel):
    id: str = Field(..., description="Unique detection identifier")
    source_file: str = Field(..., description="Original video or image filename")
    frame_index: int = Field(..., description="Zero-based frame sequence number")
    frame_path: str = Field(..., description="Path to extracted evidence frame")
    machine_type: MachineType = Field(..., description="Classified machinery category")
    fuel_type: Optional[str] = Field(None, description="Inferred or detected fuel type, e.g. diesel, natural_gas")
    rated_power_kw: Optional[float] = Field(None, description="Rated power in kW")
    rated_kva: Optional[float] = Field(None, description="Rated apparent power in kVA")
    nameplate_text: Optional[str] = Field(None, description="Raw or parsed OCR text from nameplate")
    smoke: SmokeAnalysis = Field(..., description="Optical smoke evaluation")
    maintenance_flag: bool = Field(
        ...,
        description="Flag raised if heavy smoke or anomalies detected (widens low/high uncertainty range, never changes baseline CO2e)",
    )
    confidence_0_1: float = Field(..., ge=0.0, le=1.0, description="Classification / detection confidence score")
    bbox: Optional[BoundingBox] = Field(None, description="Normalized or pixel bounding box coordinates")


# -------------------------------------------------------------------------
# 2. BillExtraction Contract
# -------------------------------------------------------------------------

BillType = Literal["electricity", "diesel", "freight"]
ExtractionMethod = Literal["ocr", "gemini_fallback"]


class BillExtraction(BaseModel):
    id: str = Field(..., description="Unique extraction record ID")
    source_file: str = Field(..., description="Filename or URI of input bill/invoice")
    bill_type: BillType = Field(..., description="Utility or operational bill category")
    period_start: str = Field(..., description="Billing cycle start (ISO-8601 or YYYY-MM-DD)")
    period_end: str = Field(..., description="Billing cycle end (ISO-8601 or YYYY-MM-DD)")
    quantity: float = Field(..., description="Quantity consumed / activity volume")
    unit: str = Field(..., description="Measurement unit (e.g., kWh, L, tkm)")
    amount_inr: float = Field(..., description="Billed financial amount in INR")
    supplier: str = Field(..., description="Vendor / utility service provider name")
    confidence_0_1: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")
    field_boxes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Bounding coordinates and visual anchors for extracted fields",
    )
    method: ExtractionMethod = Field(..., description="Primary OCR engine or fallback LLM parsing")
    user_confirmed: bool = Field(
        default=False,
        description="Whether an MSME user has manually validated or edited extracted parameters",
    )


# -------------------------------------------------------------------------
# 3. EmissionLine Contract
# -------------------------------------------------------------------------

ScopeNumber = Literal[1, 2, 3]
CalculationMethod = Literal["bill", "video_estimate", "reconciled"]


class EmissionLine(BaseModel):
    id: str = Field(..., description="Unique emission line item identifier")
    scope: ScopeNumber = Field(..., description="GHG Protocol Scope (1, 2, or 3)")
    category: str = Field(..., description="Emissions category (e.g., Stationary Combustion, Purchased Electricity)")
    activity_value: float = Field(..., description="Numerical volume of underlying activity")
    activity_unit: str = Field(..., description="Unit of activity (e.g., L, kWh, tonne-km)")
    factor_id: str = Field(..., description="Identifier pointing to factors.csv row")
    factor_value: float = Field(..., description="Emission factor coefficient")
    factor_unit: str = Field(..., description="Emission factor unit (e.g., kgCO2e/L, kgCO2e/kWh)")
    factor_source: str = Field(..., description="Authoritative registry/source (e.g., CEA v19, IPCC 2006, DEFRA)")
    factor_url: str = Field(..., description="Verifiable reference URL for emission factor")
    formula_text: str = Field(..., description="Plain-text formula representation: activity_value * factor_value")
    co2e_kg: float = Field(..., description="Deterministic baseline CO2e footprint in kg")
    low_kg: float = Field(..., description="Lower bound of uncertainty estimate in kg")
    high_kg: float = Field(..., description="Upper bound of uncertainty estimate in kg")
    evidence_refs: List[str] = Field(
        ...,
        min_length=1,
        description="Mandatory list of at least one evidence reference (frame path, crop, bill ID, sha256)",
    )
    method: CalculationMethod = Field(..., description="Method used to derive activity")
    flags: List[str] = Field(default_factory=list, description="Operational flags e.g., MAINTENANCE_WIDENED_RANGE")


# -------------------------------------------------------------------------
# 4. ScenarioResult Contract
# -------------------------------------------------------------------------

class ScenarioResult(BaseModel):
    scenario_inputs: Dict[str, Any] = Field(..., description="Input parameters tested (e.g. solar_pct, fuel_switch)")
    baseline_co2e_kg: float = Field(..., description="Baseline enterprise/process footprint in kg CO2e")
    new_co2e_kg: float = Field(..., description="Projected footprint under scenario in kg CO2e")
    delta_pct: float = Field(..., description="Percentage change in footprint (e.g., -24.5%)")
    inr_saved_per_month: float = Field(..., description="Projected recurring operational cost reduction in INR")
    capex_inr: float = Field(..., description="Estimated capital expenditure required in INR")
    payback_months: Optional[float] = Field(None, description="Estimated payback period in months; null if capex is zero or savings cannot be estimated")
    ranked_levers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Prioritized decarbonization levers ranked by ROI and abatement",
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Explicit assumptions and limitations documented for the scenario",
    )


# -------------------------------------------------------------------------
# 5. Report Contract
# -------------------------------------------------------------------------

class ReportSection(BaseModel):
    title: str = Field(..., description="Section title")
    content_markdown: str = Field(..., description="Text content formatted in markdown")
    charts: List[Dict[str, Any]] = Field(default_factory=list, description="Chart definitions and metadata")


class Report(BaseModel):
    sections: List[ReportSection] = Field(..., description="Ordered list of narrative report sections")
    facts_snapshot: Dict[str, Any] = Field(..., description="Immutable snapshot of inputs, equipment, and bills")
    number_map: Dict[str, str] = Field(
        ...,
        description="Mapping from every report number string to its exact calculation line or evidence ID",
    )
    validation: ValidationSummary = Field(
        ...,
        description="Automated audit verifying every reported number links back to evidence",
    )


# -------------------------------------------------------------------------
# 6. EvidenceBundle Contract
# -------------------------------------------------------------------------

class AuditStep(BaseModel):
    step_number: int = Field(..., description="Sequential step index in audit chain")
    description: str = Field(..., description="Explanation of transformation, measurement, or extraction")
    timestamp: str = Field(..., description="ISO-8601 timestamp")
    actor_or_component: str = Field(..., description="Component responsible (e.g. YOLOv8, EasyOCR, Engine)")


class EvidenceBundle(BaseModel):
    line_id: str = Field(..., description="Target EmissionLine identifier")
    audit_chain: List[AuditStep] = Field(..., description="Step-by-step cryptographic/audit trail")
    files: List[str] = Field(..., description="Paths to referenced raw files, frames, crops, or bills")
    hashes: Dict[str, str] = Field(
        ...,
        description="SHA-256 digests of all referenced evidence files for tamper-evident verification",
    )
