#!/usr/bin/env python3
"""
CLI Smoke Detection Tool for Carbon Passport.

Performs real-time smoke and plume detection on images and video clips.
Outputs bounding boxes, Ringelmann opacity score, plume color, and maintenance flags.
Optionally draws and saves annotated visualization to data/evidence/.
"""

import sys
import json
import time
import argparse
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import settings
from backend.vision.smoke import analyze_smoke_optical, OpticalSmokeResult


def run_detection(source_path: str, save_annotated: bool = True):
    path = Path(source_path).resolve()
    if not path.exists():
        print(f"[!] Source file not found: {source_path}")
        return

    print("\n" + "=" * 70)
    print("             CARBON PASSPORT - SMOKE DETECTION INFERENCE")
    print("=" * 70)
    print(f"Source Media : {path}")

    t0 = time.perf_counter()
    res: OpticalSmokeResult = analyze_smoke_optical(path)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    print(f"\nRESULTS:")
    print(f"• Detection Method   : {res.method.upper()}")
    print(f"• Smoke Level        : {res.level.upper()}")
    print(f"• Opacity Score      : {res.score_0_10:.1f} / 10.0 (Ringelmann Scale)")
    print(f"• Plume Color        : {res.color.upper()}")
    print(f"• Maintenance Flag   : {res.maintenance_flag}")
    if res.maintenance_reason:
        print(f"• Maintenance Reason : {res.maintenance_reason}")
    print(f"• Confidence         : {res.confidence_0_1 * 100.0:.1f}%")
    print(f"• Inference Latency  : {dt_ms:.1f} ms")

    if res.plume_bbox is not None:
        b = res.plume_bbox
        print(f"• Plume Bounding Box : [{b.x_min:.1f}, {b.y_min:.1f}, {b.x_max:.1f}, {b.y_max:.1f}]")
    else:
        print("• Plume Bounding Box : None (Clean exhaust)")

    if save_annotated and path.suffix.lower() in (".jpg", ".jpeg", ".png"):
        img = cv2.imread(str(path))
        if img is not None and res.plume_bbox is not None:
            b = res.plume_bbox
            p1 = (int(b.x_min), int(b.y_min))
            p2 = (int(b.x_max), int(b.y_max))
            color_bgr = (0, 0, 255) if res.maintenance_flag else (0, 255, 0)
            cv2.rectangle(img, p1, p2, color_bgr, 3)

            label = f"Smoke: {res.score_0_10:.1f} ({res.color}) | Maint: {res.maintenance_flag}"
            cv2.putText(img, label, (p1[0], max(25, p1[1] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_bgr, 2)

            out_dir = settings.DATA_DIR / "evidence" / "annotated"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"smoke_det_{path.name}"
            cv2.imwrite(str(out_path), img)
            print(f"[+] Saved annotated visualization to: {out_path}")

    # JSON output
    output_dict = {
        "source": path.name,
        "method": res.method,
        "score_0_10": res.score_0_10,
        "level": res.level,
        "color": res.color,
        "maintenance_flag": res.maintenance_flag,
        "maintenance_reason": res.maintenance_reason,
        "confidence": res.confidence_0_1,
        "bbox": [res.plume_bbox.x_min, res.plume_bbox.y_min, res.plume_bbox.x_max, res.plume_bbox.y_max] if res.plume_bbox else None,
        "latency_ms": round(dt_ms, 2),
    }
    return output_dict


def main():
    parser = argparse.ArgumentParser(description="Carbon Passport CLI Smoke Detection Tool.")
    parser.add_argument("source", help="Path to image or video clip")
    parser.add_argument("--no-save", action="store_true", help="Do not save annotated output image")
    args = parser.parse_args()

    run_detection(args.source, save_annotated=not args.no_save)


if __name__ == "__main__":
    main()
