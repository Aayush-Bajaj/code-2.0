#!/usr/bin/env python3
"""
YOLO Smoke Dataset Converter and Training Pipeline.

Provides industrial automation for:
1. Converting COCO annotations (_annotations.coco.json) into YOLO format (.txt)
2. Generating standard dataset config (data/datasets/smoke.yaml)
3. GPU-accelerated training with CUDA when available (with CPU fallback)
4. Augmentation, early stopping, and checkpoint saving
5. Comprehensive evaluation reporting (Precision, Recall, mAP50, mAP50-95)
6. Exporting trained model weights to data/models/smoke_yolo.pt for production deployment.
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import settings

DATASETS_DIR = settings.DATA_DIR / "datasets"
MODELS_DIR = settings.DATA_DIR / "models"
CONFIG_FILE = DATASETS_DIR / "smoke.yaml"


def convert_coco_to_yolo(split: str = "valid") -> int:
    """Convert COCO annotations into YOLO .txt format alongside images."""
    split_dir = DATASETS_DIR / split
    coco_json = split_dir / "_annotations.coco.json"

    if not coco_json.exists():
        print(f"[!] Annotation file not found: {coco_json}")
        return 0

    print(f"Reading {coco_json}...")
    with open(coco_json, "r", encoding="utf-8") as f:
        coco_data = json.load(f)

    images = {img["id"]: img for img in coco_data.get("images", [])}
    annotations = coco_data.get("annotations", [])

    img_anns: Dict[int, List[dict]] = {}
    for ann in annotations:
        img_anns.setdefault(ann["image_id"], []).append(ann)

    converted_count = 0
    for img_id, img_info in images.items():
        fname = img_info["file_name"]
        w = float(img_info.get("width", 640))
        h = float(img_info.get("height", 640))

        label_path = split_dir / Path(fname).with_suffix(".txt")
        lines = []

        for ann in img_anns.get(img_id, []):
            cat_id = ann.get("category_id", 0)
            bbox = ann.get("bbox", [])
            if len(bbox) != 4 or w <= 0 or h <= 0:
                continue

            bx, by, bw, bh = bbox
            x_center = (bx + (bw / 2.0)) / w
            y_center = (by + (bh / 2.0)) / h
            w_norm = bw / w
            h_norm = bh / h

            x_center = max(0.0, min(1.0, x_center))
            y_center = max(0.0, min(1.0, y_center))
            w_norm = max(0.0, min(1.0, w_norm))
            h_norm = max(0.0, min(1.0, h_norm))

            lines.append(f"{cat_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")

        with open(label_path, "w", encoding="utf-8") as lf:
            lf.write("\n".join(lines) + "\n")
        converted_count += 1

    print(f"[+] Converted {converted_count} image labels for {split} split.")
    return converted_count


def generate_yaml_config() -> Path:
    """Generate YOLO smoke.yaml dataset configuration."""
    yaml_content = f"""# Carbon Passport Smoke Object Detection Dataset
path: {DATASETS_DIR.as_posix()}
train: train
val: valid

names:
  0: smoke
"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"[+] Generated dataset configuration: {CONFIG_FILE}")
    return CONFIG_FILE


def train_yolo(
    epochs: int = 5,
    batch_size: int = 16,
    imgsz: int = 640,
    fraction: float = 0.05,
    patience: int = 5,
    base_model: str = "yolov8n.pt",
) -> Optional[dict]:
    """
    Launch Ultralytics YOLO training with automatic CUDA/CPU selection,
    early stopping, augmentations, and evaluation metrics logging.
    """
    try:
        import torch
        from ultralytics import YOLO
    except ImportError as e:
        print(f"\n[!] Missing dependencies for YOLO training: {e}")
        return None

    cuda_avail = torch.cuda.is_available()
    device = 0 if cuda_avail else "cpu"
    device_name = torch.cuda.get_device_name(0) if cuda_avail else "CPU"

    print("\n" + "=" * 80)
    print("         TRAINING YOLO SMOKE DETECTION MODEL FOR CARBON PASSPORT")
    print("=" * 80)
    print(f"Dataset Config : {CONFIG_FILE}")
    print(f"Base Model     : {base_model}")
    print(f"Device         : {device} ({device_name})")
    print(f"Epochs         : {epochs}")
    print(f"Batch Size     : {batch_size}")
    print(f"Image Size     : {imgsz}")
    print(f"Data Fraction  : {fraction * 100:.1f}% of train dataset")
    print(f"Early Stopping : patience={patience}")
    print("=" * 80 + "\n")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model = YOLO(base_model)

    train_results = model.train(
        data=str(CONFIG_FILE),
        epochs=epochs,
        batch=batch_size,
        imgsz=imgsz,
        fraction=fraction,
        patience=patience,
        device=device,
        project=str(MODELS_DIR),
        name="smoke_training",
        exist_ok=True,
        save=True,
        save_period=1,
        # Industrial augmentations
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        fliplr=0.5,
        mosaic=1.0,
        verbose=True,
    )

    # Formal validation evaluation
    print("\n--- Running Validation on Valid Split ---")
    val_metrics = model.val(
        data=str(CONFIG_FILE),
        split="val",
        imgsz=imgsz,
        batch=batch_size,
        device=device,
    )

    precision = float(val_metrics.box.mp)
    recall = float(val_metrics.box.mr)
    map50 = float(val_metrics.box.map50)
    map50_95 = float(val_metrics.box.map)

    print("\n" + "=" * 80)
    print("                  FINAL SMOKE MODEL EVALUATION METRICS                  ")
    print("=" * 80)
    print(f"• Precision (P)    : {precision:.4f} ({precision * 100.0:.2f}%)")
    print(f"• Recall (R)       : {recall:.4f} ({recall * 100.0:.2f}%)")
    print(f"• mAP@50           : {map50:.4f} ({map50 * 100.0:.2f}%)")
    print(f"• mAP@50-95        : {map50_95:.4f} ({map50_95 * 100.0:.2f}%)")
    print("=" * 80 + "\n")

    # Save metrics JSON artifact
    metrics_payload = {
        "model_name": "smoke_yolo",
        "base_model": base_model,
        "device": device_name,
        "epochs_trained": epochs,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "map50": round(map50, 4),
        "map50_95": round(map50_95, 4),
    }

    report_path = settings.DATA_DIR / "evidence" / "smoke_training_metrics.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)
    print(f"[+] Metrics saved to: {report_path}")

    # Copy best weights to data/models/smoke_yolo.pt for production deployment
    best_weights = MODELS_DIR / "smoke_training" / "weights" / "best.pt"
    target_weights = MODELS_DIR / "smoke_yolo.pt"
    if best_weights.exists():
        shutil.copy(best_weights, target_weights)
        print(f"[+] Deployed production weights to: {target_weights}")

    return metrics_payload


def main():
    parser = argparse.ArgumentParser(description="Prepare and Train YOLO Smoke Detector.")
    parser.add_argument("--prepare", action="store_true", help="Convert COCO labels to YOLO .txt format")
    parser.add_argument("--train", action="store_true", help="Train YOLO model on converted dataset")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--fraction", type=float, default=0.03, help="Fraction of training dataset to use (e.g. 0.03 = ~450 images)")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Image resolution")
    args = parser.parse_args()

    if args.prepare or not CONFIG_FILE.exists():
        print("Preparing YOLO dataset labels from COCO annotations...")
        convert_coco_to_yolo("valid")
        convert_coco_to_yolo("train")
        generate_yaml_config()

    if args.train:
        train_yolo(
            epochs=args.epochs,
            batch_size=args.batch,
            imgsz=args.imgsz,
            fraction=args.fraction,
        )


if __name__ == "__main__":
    main()
