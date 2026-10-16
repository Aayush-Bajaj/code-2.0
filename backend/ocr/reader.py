"""
EasyOCR wrapper with lazy singleton loading.
Falls back to a simple Pillow + regex stub when easyocr is not installed,
returning empty results so the pipeline can still invoke the LLM fallback.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Each result: (text, [[x1,y1],[x2,y1],[x2,y2],[x1,y2]], confidence)
OCRResult = Tuple[str, List[List[int]], float]

_READER: Optional[object] = None
_EASYOCR_AVAILABLE = False

try:
    import easyocr as _easyocr_mod
    _EASYOCR_AVAILABLE = True
except Exception:
    _easyocr_mod = None  # type: ignore


def _get_reader():
    global _READER
    if _READER is not None:
        return _READER
    if not _EASYOCR_AVAILABLE:
        logger.warning("easyocr not installed – OCR will return empty results and rely on LLM fallback.")
        return None
    try:
        logger.info("Loading EasyOCR model (en + hi) – first call may be slow…")
        _READER = _easyocr_mod.Reader(["en", "hi"], gpu=False, verbose=False)
        logger.info("EasyOCR ready.")
        return _READER
    except Exception as exc:
        logger.warning(f"EasyOCR init failed: {exc}")
        return None


def run_ocr(pil_image: Image.Image) -> List[OCRResult]:
    """
    Run EasyOCR on a preprocessed PIL image.
    Returns list of (text, quad_box, confidence).
    Returns empty list if EasyOCR unavailable (triggers LLM fallback).
    """
    reader = _get_reader()
    if reader is None:
        return []

    arr = np.asarray(pil_image.convert("RGB"), dtype=np.uint8)
    try:
        raw = reader.readtext(arr, detail=1, paragraph=False)
        results: List[OCRResult] = []
        for item in raw:
            box, text, conf = item
            # Ensure box is list-of-list-of-ints
            norm_box = [[int(pt[0]), int(pt[1])] for pt in box]
            results.append((str(text), norm_box, float(conf)))
        return results
    except Exception as exc:
        logger.warning(f"EasyOCR readtext failed: {exc}")
        return []
