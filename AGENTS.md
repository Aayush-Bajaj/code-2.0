# Global Rules

PROJECT: Carbon Passport, a 48-hour hackathon MVP. It estimates a small factory's carbon footprint from videos, photos and bills, and every number links back to its evidence. Audience: MSME suppliers and exporters. Judges score technical depth (30%), innovation (25%), practicality (20%), demo (15%), teamwork (10%).

STACK: Python 3.11, FastAPI, SQLModel + SQLite, pydantic v2, OpenCV, EasyOCR, Ultralytics YOLO (pretrained, optional), google-genai, ChromaDB, sentence-transformers, ReportLab, pytest. Frontend: plain HTML + CSS + vanilla JS + Chart.js, served by FastAPI. No Node build step.

NON-NEGOTIABLE RULES
1. Emission numbers come ONLY from backend/engine and data/factors/factors.csv. No LLM may create, change or round a number.
2. Never hardcode an emission factor, price or tariff in code. Never invent values. Unknown values are the literal string TODO_VERIFY and the code must refuse to run on them.
3. Every EmissionLine has at least one evidence_ref.
4. Smoke analysis never changes CO2e directly. It only widens the low/high range and raises a maintenance flag.
5. Results are estimates with low/high ranges. Never claim certification or regulatory compliance. Say the output 'supports the data these frameworks request'.
6. Secrets come only from environment variables (.env). Never print, log, echo or commit them.
7. All Gemini calls go through backend/llm.py (timeout, retry with backoff, JSON validation, SHA-256 file cache in data/cache/, MOCK_LLM and DEMO_OFFLINE switches).
8. Follow backend/schemas.py. Change a schema only by updating SPEC.md and every caller in the same change.
9. Write tests with every module. Run pytest before saying you are done and fix failures yourself.
10. Small focused commits. Do not edit outside your assigned module without saying so.

WORKFLOW
- For prompts marked CRITICAL: write a plan and STOP until I approve.
- Otherwise: brief plan, implement, run tests, then report: what you built, how to run it, what is mocked, known risks, and what I should verify by hand.
- When unsure about a fact, say so. Do not guess.
