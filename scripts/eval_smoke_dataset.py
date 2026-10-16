#!/usr/bin/env python3
"""
Evaluation and Benchmarking Script for Smoke Object Detection Dataset.

Evaluates Carbon Passport's optical smoke and plume detection engine on
the uploaded dataset (data/datasets/valid or data/datasets/train).

Metrics evaluated:
- Plume Detection Recall (% of smoke images where smoke was detected)
- Plume Bounding Box IoU against COCO ground truth
- Smoke Opacity & Ringelmann Score Distribution
- Maintenance Flag Trigger Rate (incomplete combustion identification)
- Optical Inference Latency (FPS and ms per frame)
"""

import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import settings
from backend.vision.smoke import analyze_smoke_optical, OpticalSmokeResult


def calculate_iou(boxA, boxB) -> float:
    """Compute Intersection over Union between two [xmin, ymin, xmax, ymax] boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interWidth = max(0.0, xB - xA)
    interHeight = max(0.0, yB - yA)
    interArea = interWidth * interHeight

    boxAArea = max(0.0, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(0.0, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

    unionArea = boxAArea + boxBArea - interArea
    if unionArea <= 0.0:
        return 0.0
    return interArea / unionArea


def run_benchmark(
    dataset_split: str = "valid",
    max_samples: int = 50,
    save_report: bool = True,
):
    dataset_dir = settings.DATA_DIR / "datasets" / dataset_split
    coco_path = dataset_dir / "_annotations.coco.json"

    if not dataset_dir.exists() or not coco_path.exists():
        print(f"[!] Dataset directory or annotation file not found: {coco_path}")
        return

    print("\n" + "=" * 80)
    print(f"      CARBON PASSPORT - SMOKE DATASET BENCHMARK ({dataset_split.upper()} SPLIT)")
    print("=" * 80)
    print(f"Dataset Path    : {dataset_dir}")
    print(f"COCO Annotations: {coco_path}")

    with open(coco_path, "r", encoding="utf-8") as f:
        coco_data = json.load(f)

    images = coco_data.get("images", [])
    annotations = coco_data.get("annotations", [])

    # Map image_id -> list of gt bounding boxes [xmin, ymin, xmax, ymax]
    gt_map: Dict[int, List[List[float]]] = {}
    for ann in annotations:
        img_id = ann["image_id"]
        # COCO bbox: [x, y, width, height]
        x, y, w, h = ann["bbox"]
        gt_map.setdefault(img_id, []).append([x, y, x + w, y + h])

    eval_images = images if max_samples <= 0 else images[:max_samples]
    total_eval = len(eval_images)
    print(f"Total Available : {len(images)} images")
    print(f"Evaluating      : {total_eval} sample images\n")

    detected_count = 0
    maintenance_count = 0
    ious: List[float] = []
    latencies: List[float] = []
    scores: List[float] = []
    colors_count: Dict[str, int] = {}

    print(f"{'Image File':<42} | {'GT Boxes':<8} | {'Score':<6} | {'Color':<6} | {'Maint':<6} | {'IoU':<6} | {'Time(ms)':<8}")
    print("-" * 94)

    for img_meta in eval_images:
        img_id = img_meta["id"]
        fname = img_meta["file_name"]
        img_path = dataset_dir / fname

        if not img_path.exists():
            continue

        gt_boxes = gt_map.get(img_id, [])

        t0 = time.perf_counter()
        res: OpticalSmokeResult = analyze_smoke_optical(img_path)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt_ms)

        is_detected = (res.level != "none" or res.score_0_10 >= 2.0 or res.plume_bbox is not None)
        if is_detected:
            detected_count += 1

        if res.maintenance_flag:
            maintenance_count += 1

        scores.append(res.score_0_10)
        colors_count[res.color] = colors_count.get(res.color, 0) + 1

        best_iou = 0.0
        if res.plume_bbox is not None and gt_boxes:
            pred_box = [res.plume_bbox.x_min, res.plume_bbox.y_min, res.plume_bbox.x_max, res.plume_bbox.y_max]
            best_iou = max(calculate_iou(pred_box, gt) for gt in gt_boxes)
            ious.append(best_iou)

        print(
            f"{fname[:40]:<42} | "
            f"{len(gt_boxes):<8} | "
            f"{res.score_0_10:<6.1f} | "
            f"{res.color:<6} | "
            f"{str(res.maintenance_flag):<6} | "
            f"{best_iou:<6.2f} | "
            f"{dt_ms:<8.1f}"
        )

    print("-" * 94)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    recall_rate = (detected_count / total_eval) * 100.0 if total_eval else 0.0
    maint_rate = (maintenance_count / total_eval) * 100.0 if total_eval else 0.0
    avg_iou = (sum(ious) / len(ious)) if ious else 0.0
    avg_score = (sum(scores) / len(scores)) if scores else 0.0

    print("\nBENCHMARK SUMMARY:")
    print(f"• Total Evaluated Images     : {total_eval}")
    print(f"• Plume Detection Recall     : {recall_rate:.1f}% ({detected_count}/{total_eval})")
    print(f"• Maintenance Flags Triggered: {maint_rate:.1f}% ({maintenance_count}/{total_eval})")
    print(f"• Average Plume BBox IoU     : {avg_iou:.3f}")
    print(f"• Average Opacity Score      : {avg_score:.2f} / 10.0")
    print(f"• Dominant Plume Colors      : {colors_count}")
    print(f"• Average Latency per Frame  : {avg_latency:.1f} ms ({1000.0 / avg_latency:.1f} FPS)")

    if save_report:
        report_dir = settings.DATA_DIR / "evidence"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"smoke_benchmark_{dataset_split}.json"
        report_payload = {
            "dataset_split": dataset_split,
            "total_evaluated": total_eval,
            "detection_recall_pct": round(recall_rate, 2),
            "maintenance_flag_pct": round(maint_rate, 2),
            "average_iou": round(avg_iou, 3),
            "average_opacity_score": round(avg_score, 2),
            "color_distribution": colors_count,
            "average_latency_ms": round(avg_latency, 2),
            "fps": round(1000.0 / avg_latency, 1) if avg_latency > 0 else 0.0,
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2)
        print(f"\n[+] Detailed benchmark report saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark Carbon Passport Optical Smoke Detector on Dataset.")
    parser.add_argument("--split", choices=["valid", "train"], default="valid", help="Dataset split to evaluate")
    parser.add_argument("--samples", type=int, default=25, help="Number of samples to evaluate (0 for all)")
    args = parser.parse_args()

    run_benchmark(dataset_split=args.split, max_samples=args.samples)


if __name__ == "__main__":
    main()
