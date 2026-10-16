"""
Exceptions for the Carbon Passport calculation engine.
All custom engine errors inherit from EngineError.
"""

from __future__ import annotations
from typing import List


class EngineError(Exception):
    """Base exception for all emission engine errors."""
    pass


class MissingFactorError(EngineError):
    """Raised when an emission factor or assumption is missing, non-numeric, or TODO_VERIFY."""
    pass


class UnitError(EngineError):
    """Raised when an unrecognised or prohibited unit (e.g. gallons) is encountered."""
    pass


class NeedsUserInput(EngineError):
    """
    Raised when calculation cannot proceed because required human inputs are missing.
    In particular, equipment runtime hours and load factor must never be guessed from video clips.
    """
    def __init__(self, missing_fields: List[str], message: str | None = None):
        self.missing_fields = missing_fields
        msg = message or f"Calculation requires human user input for: {', '.join(missing_fields)}"
        super().__init__(msg)
