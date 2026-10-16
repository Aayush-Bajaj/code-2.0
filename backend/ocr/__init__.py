"""
OCR Package — public interface.
"""

from backend.ocr.pipeline import extract_bill
from backend.ocr.parser import parse_ocr_results, ParseResult
from backend.ocr.preprocess import preprocess_for_ocr
from backend.ocr.reader import run_ocr

__all__ = [
    "extract_bill",
    "parse_ocr_results",
    "ParseResult",
    "preprocess_for_ocr",
    "run_ocr",
]
