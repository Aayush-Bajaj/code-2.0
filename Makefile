PYTHON ?= python

.PHONY: setup run test seed demo help

help:
	@echo "Available targets:"
	@echo "  setup : Install project dependencies"
	@echo "  run   : Start FastAPI development server"
	@echo "  test  : Run pytest test suite"
	@echo "  seed  : Seed initial factor tables and sample data"
	@echo "  demo  : Run local demo with mock flags enabled"

setup:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m uvicorn backend.api.main:app --reload --port 8000

test:
	$(PYTHON) -m pytest tests -v

seed:
	$(PYTHON) scripts/seed_factors.py

demo:
	DEMO_OFFLINE=1 MOCK_LLM=1 MOCK_VISION=1 $(PYTHON) -m uvicorn backend.api.main:app --reload --port 8000
