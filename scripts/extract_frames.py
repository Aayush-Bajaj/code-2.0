#!/usr/bin/env python3
"""
Extract N evenly spaced frames from a video file using OpenCV.
Saves frames to: data/samples/frames/<video_name>/<idx>.jpg
Calculates sharpness score (variance of Laplacian) and saves a sidecar JSON.
"""
import os
import sys
import json
import argparse
from pathlib import Path
import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
FRAMES_BASE_DIR = BASE_DIR / "data" / "samples" / "frames"


def calculate_sharpness(frame_bgr: np.ndarray) -> float:
    """Calculate image sharpness score using the variance of the Laplacian."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())


def extract_frames(video_path: str, num_frames: int = 10, output_dir: str = None) -> Path:
    video_file = Path(video_path).resolve()
    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_file}")

    video_name = video_file.stem
    if output_dir:
        target_dir = Path(output_dir).resolve()
    else:
        target_dir = FRAMES_BASE_DIR / video_name

    target_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        raise ValueError(f"Failed to open video file: {video_file}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    duration_sec = total_frames / fps if fps > 0 else 0.0

    if total_frames <= 0:
        cap.release()
        raise ValueError(f"Video contains 0 frames: {video_file}")

    # Determine frame indices to capture
    if total_frames <= num_frames:
        frame_indices = list(range(total_frames))
    else:
        step = total_frames / float(num_frames)
        frame_indices = [int(i * step) for i in range(num_frames)]

    extracted_metadata = []

    for idx, target_frame_no in enumerate(frame_indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_no)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        sharpness = calculate_sharpness(frame)
        frame_filename = f"{idx:04d}.jpg"
        frame_path = target_dir / frame_filename

        cv2.imwrite(str(frame_path), frame)

        extracted_metadata.append({
            "index": idx,
            "frame_number": target_frame_no,
            "timestamp_seconds": round(target_frame_no / fps, 3),
            "filename": frame_filename,
            "relative_path": str(frame_path.relative_to(BASE_DIR)).replace("\\", "/"),
            "sharpness_laplacian_var": round(sharpness, 2),
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
        })

    cap.release()

    sidecar_data = {
        "video_file": str(video_file.name),
        "total_frames": total_frames,
        "fps": fps,
        "duration_seconds": round(duration_sec, 2),
        "frames_extracted": len(extracted_metadata),
        "frames": extracted_metadata,
    }

    sidecar_path = target_dir / "frames_metadata.json"
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(sidecar_data, f, indent=2)

    print(f"Extracted {len(extracted_metadata)} frames to {target_dir}")
    print(f"Sidecar metadata saved to {sidecar_path}")
    return sidecar_path


def main():
    parser = argparse.ArgumentParser(description="Extract N evenly spaced frames from video with sharpness scores.")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("-n", "--num-frames", type=int, default=10, help="Number of frames to extract (default: 10)")
    parser.add_argument("-o", "--output-dir", default=None, help="Custom output directory")

    args = parser.parse_args()
    extract_frames(args.video, args.num_frames, args.output_dir)


if __name__ == "__main__":
    main()
