# Carbon Passport 🌿

> **Automated Carbon Footprint Estimation Platform with Multimodal Evidence Auditing**

Carbon Passport is a project concept for estimating the carbon footprint of MSME and small manufacturing facilities using utility bills, equipment photos, and chimney or generator videos. Its goal is to connect reported estimates to traceable evidence.

## Project overview

The platform is designed around five main capabilities:

1. **Utility and fuel bill ingestion** — OCR-based extraction of electricity, diesel, natural gas, and freight information, with confidence scoring.
2. **Visual and video auditing** — computer-vision workflows to inspect machinery and smoke-related evidence.
3. **Deterministic calculation engine** — emission calculations based on configured emission-factor data, with low, estimate, and high ranges.
4. **Digital-twin scenarios** — what-if exploration of options such as rooftop solar and equipment electrification.
5. **Evidence and reporting** — evidence-linked audit bundles and downloadable PDF reports.

The project is framed around sustainability reporting workflows and references frameworks such as the GHG Protocol, EU CBAM, and SEBI BRSR. Outputs should be treated as estimates and reviewed against source records and applicable standards.

## Technology stack

| Layer | Technologies |
|---|---|
| Backend | FastAPI, Python 3.12, Uvicorn, Pydantic v2, SQLModel |
| Computer vision | OpenCV, Ultralytics YOLOv8, PIL |
| OCR and documents | EasyOCR, PyPDF, ReportLab |
| Generative AI integration | Google GenAI / Gemini |
| Retrieval | ChromaDB, sentence-transformers |
| Frontend | HTML, CSS, JavaScript, Chart.js |
| Testing | pytest |

## Run locally

### 1. Clone the repository

```bash
git clone https://github.com/Aayush-Bajaj/code-2.0.git
cd code-2.0
```

### 2. Create and activate a Python 3.12 environment

**Windows (PowerShell):**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and configure the values required for your environment. The project includes mock/offline switches for supported development workflows. Do not commit API keys or other secrets.

### 5. Run the environment check

```bash
python scripts/check_env.py
```

### 6. Start the application

```bash
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

- Web application: http://localhost:8000
- Swagger API documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Run tests

```bash
pytest tests/ -v
```

You can also run focused test modules, for example:

```bash
pytest tests/test_engine.py -v
pytest tests/test_smoke.py tests/test_vision.py -v
pytest tests/test_all_endpoints.py -v
```

## High-level project structure

```text
backend/
  api/          API routes
  engine/       Emission calculation logic
  evidence/     Evidence bundle generation
  ocr/          Document and bill extraction
  rag/          Retrieval workflows
  twin/         Scenario simulation
  vision/       Computer-vision workflows
  config.py     Configuration
  llm.py        Gemini integration
  schemas.py    Pydantic schemas
frontend/       HTML, CSS, and JavaScript application
data/           Factors, samples, documents, and model assets
docs/           Specifications and guides
scripts/        Utility and evaluation scripts
tests/          Automated tests
```

## Design principles

- Keep numerical calculations in the calculation engine rather than asking a language model to invent values.
- Link reported line items to their source evidence where supported by the workflow.
- Make estimation ranges and assumptions visible.
- Treat computer-vision outputs as supporting evidence, not as a substitute for verified measurements.
- Review outputs against source records and relevant reporting requirements before using them for formal decisions.

## License

This repository currently includes an MIT License. See the [LICENSE](LICENSE) file for its terms.
