# Carbon Passport — Calculation Engine Specification & Audit Guide

This document explains every mathematical formula, factor derivation, uncertainty boundary, and reconciliation protocol in the Carbon Passport deterministic emission engine.

Judges and auditors can trace every numerical result back to the authoritative equations and reference data sources documented below.

---

## 1. Core Principles & Zero-LLM Invariant

1. **Deterministic Calculation**:
   - Emission numbers come exclusively from `backend/engine` and `data/factors/factors.csv`.
   - **No Large Language Model (LLM) is ever allowed to calculate, adjust, or round numbers.**
2. **Strict Verification Guard (`TODO_VERIFY`)**:
   - The engine never invents factors or assumes default national values without verification.
   - Any factor marked `TODO_VERIFY`, empty, or non-numeric causes the engine to immediately raise `MissingFactorError` and refuse execution.
3. **Auditable Evidence Chain**:
   - Every `EmissionLine` contains a non-empty `evidence_refs` array pointing to cryptographic hashes, source filenames, extracted video frame timestamps, or scanned invoice coordinate boxes.
4. **Display-Time Rounding**:
   - Calculations use 64-bit IEEE 754 floating point arithmetic. Values are formatted and rounded only when rendered to the user interface or exported report.

---

## 2. Emission Formulas & Worked Examples

### 2.1 Scope 2: Purchased Electricity (Grid)

#### Plain Language
Purchased electricity emissions represent the greenhouse gases emitted by power plants supplying the regional/national electrical grid per unit of electricity delivered to the factory meter.

#### Formula
$$\text{CO}_2\text{e (kg)} = \text{Electricity Activity (kWh)} \times \text{Grid Emission Factor}\ (\text{kg CO}_2\text{e / kWh})$$

*Unit Normalisation*:
- If consumption is reported in Megawatt-hours ($\text{MWh}$), it is normalised: $\text{kWh} = \text{MWh} \times 1000$.
- Units labelled as `"units"` on Indian utility bills are equivalent to $1\ \text{kWh}$.

#### Factor Reference
- **Factor ID**: `EF_IN_GRID_ELEC`
- **Source**: Central Electricity Authority (CEA), Ministry of Power, Government of India — *CO2 Baseline Database for the Indian Power Sector*.

#### Worked Example
- **Input Bill**: 18,450.0 kWh from BESCOM March invoice.
- **Factor**: $0.716\ \text{kg CO}_2\text{e/kWh}$
- **Calculation**:
  $$18{,}450.0\ \text{kWh} \times 0.716\ \text{kg CO}_2\text{e/kWh} = 13{,}210.20\ \text{kg CO}_2\text{e}$$
- **Formula Text Output**:
  `"18450.0 kWh x 0.716 kg CO2e/kWh = 13210.2 kg"`
- **Uncertainty ($\pm 5\%$)**:
  - $\text{Low}: 13{,}210.20 \times 0.95 = 12{,}549.69\ \text{kg}$
  - $\text{High}: 13{,}210.20 \times 1.05 = 13{,}870.71\ \text{kg}$

---

### 2.2 Scope 1: Diesel Fuel Bill (Stationary Combustion)

#### Plain Language
Fuel consumed on-site in backup diesel generator sets or boilers releases carbon dioxide, methane, and nitrous oxide through direct hydrocarbon combustion.

#### Formula
$$\text{CO}_2\text{e (kg)} = \text{Fuel Consumed (Litres)} \times \text{Diesel Emission Factor}\ (\text{kg CO}_2\text{e / Litre})$$

*Unit Enforcement*:
- Volume must be in Litres ($L$). Gallons (`gal`) are explicitly rejected with `UnitError`.

#### Factor Reference
- **Factor ID**: `EF_DIESEL_STATIONARY`
- **Source**: IPCC 2006 Guidelines for National Greenhouse Gas Inventories & India MoEFCC GHG Platform.

#### Worked Example
- **Input Bill**: Fuel delivery receipt of $662.83\ \text{L}$ of commercial High Speed Diesel (HSD).
- **Factor**: $2.68\ \text{kg CO}_2\text{e/L}$
- **Calculation**:
  $$662.83\ \text{L} \times 2.68\ \text{kg CO}_2\text{e/L} = 1{,}776.3844\ \text{kg CO}_2\text{e}$$
- **Formula Text Output**:
  `"662.83 L x 2.68 kg CO2e/L = 1776.3844 kg"`

---

### 2.3 Scope 3: Road Freight Transport (Upstream Logistics)

#### Plain Language
Transportation of raw materials or outbound goods carried by third-party logistics operators (rigid diesel trucks) calculated based on cargo mass multiplied by transit distance.

#### Formula
$$\text{CO}_2\text{e (kg)} = \text{Freight Activity (tonne-km)} \times \text{Freight Factor}\ (\text{kg CO}_2\text{e / tonne-km})$$

#### Factor Reference
- **Factor ID**: `EF_ROAD_FREIGHT`
- **Source**: India GHG Program / GLEC Framework for Logistics Emissions.

#### Worked Example
- **Input Consignment Note**: 15 tonnes of steel billets transported over $375\ \text{km} \rightarrow 15 \times 375 = 5{,}625.0\ \text{tonne-km}$.
- **Factor**: $0.115\ \text{kg CO}_2\text{e / tonne-km}$
- **Calculation**:
  $$5{,}625.0\ \text{tonne-km} \times 0.115\ \text{kg CO}_2\text{e/tonne-km} = 646.875\ \text{kg CO}_2\text{e}$$

---

### 2.4 Scope 1: Machine Vision Estimate (Diesel Generator)

#### Plain Language
When utility fuel bills are missing, delayed, or require verification, the vision pipeline identifies generator nameplate capacity from equipment video clips. Operational runtime hours and average load factor are supplied as verified user inputs (never guessed from short video clips).

#### Electrical Conversion Rule
If the generator nameplate specifies apparent power in $\text{kVA}$ rather than active power in $\text{kW}$, the engine converts using standard industrial power factor ($\text{PF} = 0.8$):
$$\text{Rated kW} = \text{Rated kVA} \times 0.80$$
This conversion is recorded directly in the auditable `formula_text`.

#### Specific Fuel Consumption (SFC) Load Curve
Generator fuel efficiency varies significantly with operating load. The engine applies piecewise linear interpolation across calibrated benchmark load points in `factors.csv`:

| Load Point | Factor ID | Calibrated SFC (L/kWh) |
| :--- | :--- | :--- |
| **25%** | `SFC_DG_LOAD_25` | 0.300 |
| **50%** | `SFC_DG_LOAD_50` | 0.280 |
| **75%** | `SFC_DG_LOAD_75` | 0.260 |
| **100%** | `SFC_DG_LOAD_100` | 0.240 |

Interpolation equation for load $L \in [L_1, L_2]$:
$$\text{SFC}(L) = \text{SFC}(L_1) + \left(\frac{L - L_1}{L_2 - L_1}\right) \times (\text{SFC}(L_2) - \text{SFC}(L_1))$$

#### Total Combustion Equation
$$\text{Estimated Litres} = \text{Rated kW} \times \left(\frac{\text{Load \%}}{100}\right) \times \text{Hours} \times \text{SFC}(L)$$
$$\text{CO}_2\text{e (kg)} = \text{Estimated Litres} \times \text{EF\_DIESEL\_STATIONARY}$$

#### Worked Example
- **Nameplate Vision Output**: $125.0\ \text{kVA}$ Kirloskar Green DG set.
  - Active Power: $125.0 \times 0.8 = 100.0\ \text{kW}$.
- **User Inputs**:
  - Operating Hours: $60.0\ \text{hours/month}$.
  - Average Operating Load: $62.5\%$.
- **SFC Interpolation** (between 50% and 75%):
  $$\text{SFC}(62.5\%) = 0.280 + \left(\frac{62.5 - 50.0}{75.0 - 50.0}\right) \times (0.260 - 0.280) = 0.270\ \text{L/kWh}$$
- **Litres Consumed**:
  $$100.0\ \text{kW} \times 0.625 \times 60.0\ \text{hours} \times 0.270\ \text{L/kWh} = 1{,}012.5\ \text{Litres}$$
- **Emissions** (with factor $2.68\ \text{kg/L}$):
  $$1{,}012.5\ \text{L} \times 2.68\ \text{kg/L} = 2{,}713.5\ \text{kg CO}_2\text{e}$$

---

## 3. Uncertainty Quantification & Widening Rules

Every emission line produces deterministic lower (`low_kg`) and upper (`high_kg`) bounds:

### Named Parameters (`backend/engine/uncertainty.py`)

1. **`BILL_BASE_UNCERTAINTY = 0.05` ($\pm 5\%$)**:
   - Accounts for revenue meter precision tolerances and utility billing cycle date cutoff shifts.
2. **`BILL_LOW_CONF_WIDENING = 0.05` ($\pm 5\%$)**:
   - If OCR text extraction confidence is below $0.70$, uncertainty spreads to $\pm 10\%$.
   - Flag appended: `ocr_low_confidence_widened`.
3. **`DETECTION_LOAD_POINTS = 15.0` ($\pm 15$ percentage points)**:
   - Accounts for human estimation error in reporting operational load factor. For an input of $60\%$, the bounds are evaluated at $[45\%, 75\%]$.
4. **`DETECTION_FUEL_USE_PCT = 0.10` ($\pm 10\%$)**:
   - Factory engine wear, turbocharger condition, and seasonal temperature variance on SFC.
5. **Optical Smoke Widening Rule (`DETECTION_SMOKE_WIDENING = 0.10`)**:
   - **Crucial Rule**: Optical smoke analysis **never alters baseline $\text{CO}_2\text{e}$ directly**.
   - If smoke score $\ge 6.0$ or exhaust color is `black` or `blue`:
     - Range is widened by an additional $\pm 10\%$ to reflect unburnt hydrocarbon and soot inefficiencies.
     - Flag appended: `smoke_inefficiency_widened`.
     - System raises maintenance advisory flag: `possible incomplete combustion or oil burning, inspect`.
6. **`DETECTION_LOW_CONF_WIDENING = 0.10`**:
   - If machine detection confidence is $< 0.60$, uncertainty range widens by an additional $\pm 10\%$.
   - Flag appended: `detection_low_confidence_widened`.

---

## 4. Reconciliation Protocol (`reconcile()`)

When an MSME has **both** fuel bills and equipment video estimates:

1. **Discrepancy Calculation**:
   $$\text{Percent Difference} = \frac{|\text{Video Estimate} - \text{Bill Activity}|}{\text{Bill Activity}} \times 100\%$$
2. **25% Mismatch Threshold**:
   - If $\text{Percent Difference} > 25.0\%$:
     - The flag `video_bill_mismatch` is added to the emission line.
     - Alert: Indicates potential unrecorded fuel pilferage, sub-metered auxiliary loads, or misstated operating log hours.
3. **Primary vs Cross-Check Invariant**:
   - The verified utility bill figure **always remains the primary baseline** (`co2e_kg = bill.co2e_kg`).
   - The video estimate is preserved as an audit cross-check inside `formula_text`.
   - Method is permanently tagged as `method="reconciled"`.
   - Evidence references from both the bill scan and video frames are concatenated.

---

## 5. Aggregation Protocol (`totals()`)

The engine computes exact Scope 1, Scope 2, and Scope 3 subtotals, alongside the Grand Total:

$$\text{Grand Total CO}_2\text{e} = \sum \text{Scope 1} + \sum \text{Scope 2} + \sum \text{Scope 3}$$
$$\text{Grand Low} = \sum \text{low\_kg}_i, \quad \text{Grand High} = \sum \text{high\_kg}_i$$

The engine enforces the mathematical invariant that the Grand Total equals the arithmetic sum of scope totals without rounding drift.
