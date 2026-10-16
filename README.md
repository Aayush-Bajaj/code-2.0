# Carbon Passport 🌿

> **Automated Carbon Footprint Estimation Platform with Multimodal Evidence Auditing**  
> Estimates MSME and small manufacturing facilities' carbon footprints from utility bills, equipment photos, and chimney/generator videos. Every reported number links directly back to verifiable physical evidence.

---

## 📌 Project Overview

**Carbon Passport** is designed to solve the decarbonization and reporting barrier for MSME suppliers and exporters facing strict international sustainability reporting mandates (such as **EU CBAM**, **GHG Protocol**, and **SEBI BRSR**).

Rather than relying on generic manual surveys or unverified guesses, Carbon Passport processes:
1. **Utility & Fuel Bills**: Automated OCR parsing of electricity, diesel, natural gas, and freight invoices with confidence scoring.
2. **Visual & Video Auditing**: Computer vision (YOLOv8 + optical smoke density analysis) to identify running machinery, combustion anomalies, and generator smoke.
3. **Deterministic Calculation Engine**: Zero-hallucination emission accounting using standardized emission factor datasets (`factors.csv`), strictly computing Scope 1, Scope 2, and Scope 3 footprints with mathematical uncertainty ranges (`low`, `estimate`, `high`).
4. **Digital Twin Simulator**: Interactive what-if scenario testing (e.g., solar rooftop transition, diesel generator electrification, supplier optimization).
5. **Auditable Evidence & PDF Report**: Automatic generation of comprehensive audit bundles and downloadable PDF compliance reports.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12, Uvicorn, Pydantic v2, SQLModel) |
| **Computer Vision** | [OpenCV](https://opencv.org/), [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics), PIL |
| **OCR & Document Ingestion** | [EasyOCR](https://github.com/JaidedAI/EasyOCR), PyPDF / ReportLab |
| **Generative AI Gateway** | [Google GenAI / Gemini](https://ai.google.dev/) (with timeout, exponential backoff, SHA-256 caching & offline mock modes) |
| **Vector Search / RAG** | [ChromaDB](https://www.trychroma.com/), [sentence-transformers](https://sbert.net/) |
| **Frontend** | Modern Vanilla JavaScript (ES6+), HTML5, Semantic CSS3 (Glassmorphism & tokens), Chart.js |
| **Testing & CI** | [pytest](https://pytest.org/), automated test suites covering OCR, vision, engine, API, and twin |

---

## 📋 System Requirements

| Requirement | Specification |
|---|---|
| **Python** | **3.12** (`py -3.12` or `python3.12`) |
| **Operating System** | Windows 10/11, macOS (Apple Silicon / Intel), Linux (Ubuntu 20.04+) |
| **Hardware** | Minimum 4 GB RAM; CPU inference supported by default (CUDA GPU optional) |

---

## 🚀 Quick Start & Installation

### 1. Clone the Repository
```bash
git clone <repository_url>
cd "code clash 2.0"
```

### 2. Set Up a Python 3.12 Virtual Environment

**Windows:**
```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to create your local `.env`:

**Windows:**
```powershell
copy .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Open `.env` and fill in your configuration:
```env
# Gemini API Key (obtain from https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Execution & Demo switches (set MOCK_LLM=1 for offline testing without API keys)
MOCK_LLM=0
MOCK_VISION=0
DEMO_OFFLINE=0

# Hardware Acceleration (cpu by default)
DEVICE=cpu
```

### 5. Verify Setup
Run the environment diagnostic script to verify system compatibility:
```bash
python scripts/check_env.py
```

### 6. Run the Application
Start the FastAPI development server:
```bash
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

Open your browser and navigate to:
- **Web Application UI:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Running Tests

The test suite validates calculations, OCR extraction, vision pipelines, schemas, and API endpoints:

```bash
# Run all tests
pytest tests/ -v

# Run engine calculation tests
pytest tests/test_engine.py -v

# Run smoke and vision pipeline tests
pytest tests/test_smoke.py tests/test_vision.py -v

# Run API endpoint integration tests
pytest tests/test_all_endpoints.py -v
```

---

## 📂 Project Architecture

```
.
|-- backend/
|   |-- api/             # FastAPI route controllers (meta, upload, review, report, twin)
|   |-- engine/          # Deterministic emission calculation engine (no LLM in numbers)
|   |-- evidence/        # Evidence bundle builder linking data to sources
|   |-- ocr/             # Utility bill OCR parser with confidence metrics
|   |-- rag/             # ChromaDB vector retrieval for CBAM/GHG/BRSR standards
|   |-- twin/            # Digital Twin simulation engine for reduction scenarios
|   |-- vision/          # Smoke density classifier & YOLO machinery detector
|   |-- config.py        # Centralized configuration & environment loader
|   |-- llm.py           # Gemini gateway with caching, retry, and mock switches
|   +-- schemas.py       # Pydantic v2 models (single source of truth)
|-- data/
|   |-- bills/           # Sample utility bills for demonstration
|   |-- factors/         # Standard factors.csv & assumptions.yaml
|   |-- models/          # Trained weights (smoke_yolo.pt)
|   |-- rag_docs/        # Regulatory documents (CBAM, GHG Protocol, BRSR)
|   +-- samples/         # Video clips and test footage
|-- frontend/            # Vanilla HTML5, CSS3, ES6 modules, Chart.js
|   |-- css/             # Design tokens, motion, components, base styles
|   |-- js/              # Client store, router, API client, views, charts
|   +-- index.html       # Single Page Application entrypoint
|-- docs/                # Architecture specifications and demo guides
|-- scripts/             # Utility scripts for data preparation, eval, training
+-- tests/               # Comprehensive pytest suite and test fixtures
```

---

## 🔒 Governance & Core Accounting Principles

1. **Deterministic Calculations Only**: Emission figures are computed strictly by `backend/engine` using verifiable records and verified factor tables (`data/factors/factors.csv`). No LLM is permitted to generate or round numerical values.
2. **Every Number Has Evidence**: Every line item in an emission inventory contains an `evidence_ref` tracing back to an uploaded document, timestamped video frame, or recognized factor.
3. **Safe Smoke Adjustments**: Visual smoke detection never invents or arbitrarily modifies base CO2e values; it widens uncertainty ranges and triggers equipment maintenance alerts.
4. **Transparent Estimation Ranges**: All outputs present low/estimate/high ranges.
5. **Regulatory Framing**: The system supports data requested by frameworks such as GHG Protocol, CBAM, and BRSR; results are estimates designed for supplier audit readiness.

---

## 📄 License

This project is licensed under the MIT License.