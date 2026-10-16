"""
backend/twin — Factory digital twin simulation module.

Public API:
  - Facility         : structured container for confirmed inputs
  - ScenarioInputs   : Pydantic model for what-if lever values (validated + clamped)
  - simulate()       : run a full scenario, returns ScenarioResult
  - MissingAssumptionError : raised when a TODO_VERIFY assumption is needed
"""

from backend.twin.simulator import (
    Facility,
    ScenarioInputs,
    simulate,
    MissingAssumptionError,
)

__all__ = ["Facility", "ScenarioInputs", "simulate", "MissingAssumptionError"]
