"""
Frame extraction, sharpness computation, and image preprocessing utilities for vision pipeline.
Uses OpenCV when available and gracefully falls back to Pillow/NumPy if OpenCV native DLL
is blocked by OS Application Control policies.
"""

import io
from pathlib import Path
from typing import List, Tuple
import numpy as np
from PIL import Image, ImageFilter

from backend.config import settings

EVIDENCE_FRAMES_DIR = settings.DATA_DIR / "evidence" / "frames"

try:
    import cv2
    _OPENCV_AVAILABLE = True
except Exception:
    cv2 = None
    _OPENCV_AVAILABLE = False


def calculate_sharpness_pil(img: Image.Image) -> float:
    """Calculate image sharpness score using Laplacian convolution with PIL + numpy."""
    gray = img.convert("L")
    # 3x3 Laplacian kernel: [[0, 1, 0], [1, -4, 1], [0, 1, 0]]
    laplacian_kernel = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=0)
    filtered = gray.filter(laplacian_kernel)
    arr = np.asarray(filtered, dtype=np.float64)
    return float(np.var(arr))


def calculate_sharpness(frame_or_img) -> float:
    """Calculate image sharpness score using the variance of the Laplacian."""
    if _OPENCV_AVAILABLE and isinstance(frame_or_img, np.ndarray) and cv2 is not None:
        try:
            if frame_or_img.size == 0:
                return 0.0
            gray = cv2.cvtColor(frame_or_img, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            return float(laplacian.var())
        except Exception:
            pass

    if isinstance(frame_or_img, np.ndarray):
        # Convert numpy array to PIL Image
        if frame_or_img.ndim == 2:
            img = Image.fromarray(frame_or_img)
        elif frame_or_img.ndim == 3:
            # Assuming BGR if 3 channel
            img = Image.fromarray(frame_or_img[:, :, ::-1])
        else:
            return 0.0
        return calculate_sharpness_pil(img)
    elif isinstance(frame_or_img, Image.Image):
        return calculate_sharpness_pil(frame_or_img)
    return 0.0


def _extract_frames_opencv(
    video_path: Path,
    max_sample_frames: int = 8,
    keep_top_k: int = 4,
) -> List[Tuple[int, bytes, float]]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video file at {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        raise ValueError(f"Video contains 0 frames: {video_path}")

    sample_count = min(max_sample_frames, total_frames)
    if total_frames <= sample_count:
        sample_indices = list(range(total_frames))
    else:
        step = total_frames / float(sample_count)
        sample_indices = [int(i * step) for i in range(sample_count)]

    candidates: List[Tuple[int, bytes, float]] = []
    for f_idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        sharpness = calculate_sharpness(frame)
        success, buffer = cv2.imencode(".jpg", frame)
        if success:
            candidates.append((f_idx, buffer.tobytes(), sharpness))

    cap.release()
    candidates.sort(key=lambda x: x[2], reverse=True)
    selected = candidates[:keep_top_k]
    selected.sort(key=lambda x: x[0])
    return selected


def _extract_frames_pil_fallback(
    video_path: Path,
    max_sample_frames: int = 8,
    keep_top_k: int = 4,
) -> List[Tuple[int, bytes, float]]:
    """Fallback if video frames cannot be opened natively (e.g. animated GIF or single image)."""
    try:
        im = Image.open(str(video_path))
        candidates: List[Tuple[int, bytes, float]] = []
        frame_idx = 0
        while True:
            rgb = im.convert("RGB")
            buf = io.BytesIO()
            rgb.save(buf, format="JPEG")
            b = buf.getvalue()
            sharpness = calculate_sharpness_pil(rgb)
            candidates.append((frame_idx, b, sharpness))
            frame_idx += 1
            if frame_idx >= max_sample_frames:
                break
            try:
                im.seek(frame_idx)
            except EOFError:
                break
        candidates.sort(key=lambda x: x[2], reverse=True)
        selected = candidates[:keep_top_k]
        selected.sort(key=lambda x: x[0])
        return selected
    except Exception as e:
        raise ValueError(f"Cannot decode video frames without OpenCV or standard container support: {e}")


def process_media_frames(
    media_path: str,
    file_id: str,
    max_sample_frames: int = 8,
    keep_top_k: int = 4,
) -> List[Tuple[int, Path, bytes]]:
    """
    Sample frames from a video or load an image file.
    1. Sample up to 8 frames, then keep the 4 sharpest (variance of Laplacian).
       For images, use the image itself.
    2. Save each used frame to data/evidence/frames/<file_id>_<idx>.jpg.
    Returns list of tuples: (frame_index, saved_frame_path, jpeg_bytes)
    """
    path = Path(media_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Media file not found: {media_path}")

    EVIDENCE_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}

    results: List[Tuple[int, Path, bytes]] = []

    # Case 1: Image input
    if suffix in image_extensions:
        img = Image.open(str(path)).convert("RGB")
        target_path = EVIDENCE_FRAMES_DIR / f"{file_id}_0.jpg"
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()
        with open(target_path, "wb") as f:
            f.write(jpeg_bytes)
        results.append((0, target_path, jpeg_bytes))
        return results

    # Case 2: Video input
    if _OPENCV_AVAILABLE and cv2 is not None:
        try:
            selected = _extract_frames_opencv(path, max_sample_frames, keep_top_k)
        except Exception:
            selected = _extract_frames_pil_fallback(path, max_sample_frames, keep_top_k)
    else:
        selected = _extract_frames_pil_fallback(path, max_sample_frames, keep_top_k)

    if not selected:
        raise ValueError(f"No frames could be extracted from {path}")

    for f_idx, jpeg_bytes, _ in selected:
        target_path = EVIDENCE_FRAMES_DIR / f"{file_id}_{f_idx}.jpg"
        with open(target_path, "wb") as f:
            f.write(jpeg_bytes)
        results.append((f_idx, target_path, jpeg_bytes))

    return results
