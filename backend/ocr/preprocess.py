"""
Image preprocessing for OCR quality improvement.
Steps: grayscale → deskew (minAreaRect on thresholded contours) → denoise → adaptive threshold.
Always keeps the original JPEG bytes as evidence.
Falls back to Pillow path when the cv2 DLL is blocked by OS policy.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image, ImageFilter, ImageOps

try:
    import cv2
    _CV2_OK = True
except Exception:
    cv2 = None  # type: ignore
    _CV2_OK = False


# --------------------------------------------------------------------------- #
#  Public helpers
# --------------------------------------------------------------------------- #

def load_image_bytes(path: str) -> bytes:
    """Return raw JPEG bytes of the original file (unchanged)."""
    with open(path, "rb") as f:
        return f.read()


def pil_to_jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def preprocess_for_ocr(image_path: str) -> Tuple[Image.Image, bytes]:
    """
    Preprocess a bill image for OCR.

    Returns:
        (preprocessed_pil_image, original_jpeg_bytes)
    """
    original_bytes = load_image_bytes(image_path)

    if _CV2_OK and cv2 is not None:
        processed = _preprocess_cv2(image_path)
    else:
        processed = _preprocess_pil(image_path)

    return processed, original_bytes


# --------------------------------------------------------------------------- #
#  OpenCV path
# --------------------------------------------------------------------------- #

def _preprocess_cv2(image_path: str) -> Image.Image:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"cv2.imread could not read {image_path}")

    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Deskew using minAreaRect on the largest cluster of text blobs
    gray = _deskew_cv2(gray)

    # 3. Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # 4. Adaptive threshold (Otsu + Gaussian)
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(binary)


def _deskew_cv2(gray: np.ndarray) -> np.ndarray:
    """Estimate skew angle using minAreaRect and rotate to correct it."""
    try:
        # Threshold to find text blobs
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        if coords.shape[0] < 50:
            return gray
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        # Normalise angle to [-45, 45]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) < 0.5:
            return gray  # negligible skew
        h, w = gray.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rotated = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
        return rotated
    except Exception:
        return gray


# --------------------------------------------------------------------------- #
#  Pillow fallback path
# --------------------------------------------------------------------------- #

def _preprocess_pil(image_path: str) -> Image.Image:
    """Pillow-only preprocessing when cv2 is unavailable."""
    img = Image.open(image_path).convert("L")  # grayscale

    # Deskew via Pillow (limited — only large-angle detection)
    img = _deskew_pil(img)

    # Sharpen / denoise lightly
    img = img.filter(ImageFilter.SHARPEN)

    # Threshold via point map (Otsu-like fixed threshold)
    arr = np.asarray(img, dtype=np.uint8)
    threshold = int(np.percentile(arr, 60))
    binary = img.point(lambda p: 255 if p > threshold else 0, "L")
    return binary


def _deskew_pil(img: Image.Image) -> Image.Image:
    """Very coarse deskew using projection profile on PIL image."""
    try:
        arr = 255 - np.asarray(img, dtype=np.uint8)
        # Find best angle in [-10, 10]
        best_angle, best_var = 0.0, -1.0
        for angle in range(-10, 11):
            rotated = Image.fromarray(arr).rotate(angle, expand=False, fillcolor=0)
            r_arr = np.asarray(rotated)
            row_sums = r_arr.sum(axis=1).astype(float)
            var = float(np.var(row_sums))
            if var > best_var:
                best_var = var
                best_angle = float(angle)
        if abs(best_angle) > 0.5:
            return img.rotate(-best_angle, resample=Image.BICUBIC, expand=False, fillcolor=255)
        return img
    except Exception:
        return img
