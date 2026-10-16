# Carbon Passport Smoke Detection ML Engine

This document outlines the architecture, training procedure, evaluation benchmarks, and backend integration for the smoke detection machine learning engine.

---

## 1. Dataset Overview

- **Source**: Keremberke Smoke Object Detection Dataset
- **Train Split**: `data/datasets/train/` (15,096 images, 640×640)
- **Validation Split**: `data/datasets/valid/` (4,322 images, 640×640)
- **Annotation Format**: Preserved original COCO format (`_annotations.coco.json`) and dual-exported normalized YOLO format (`.txt`)
- **Single Class**: `0: smoke`
- **Config File**: `data/datasets/smoke.yaml`

---

## 2. Model Architecture & Training

- **Base Model**: `yolov8n.pt` (Ultralytics YOLOv8 Nano)
- **Hyperparameters**:
  - Image size: 640×640 (default) / 320×320 (speed optimized)
  - Optimizer: AdamW (`lr=0.002, momentum=0.9`)
  - Loss: Box loss (IoU), Classification loss, Distribution Focal Loss (DFL)
  - Augmentations: Mosaic (1.0), Horizontal Flip (0.5), HSV color jitter (`h=0.015, s=0.7, v=0.4`)
  - Checkpoints: `best.pt` automatically deployed to `data/models/smoke_yolo.pt`
- **Device Support**: Automatic CUDA GPU acceleration when PyTorch CUDA is enabled, with high-speed CPU fallback.

### Completed Training Validation Metrics (on 4,322 Valid Images)

| Metric | Score | Percentage |
|---|---|---|
| **Precision (P)** | `0.5218` | **52.18%** |
| **Recall (R)** | `0.6189` | **61.89%** |
| **mAP@50** | `0.5286` | **52.86%** |
| **mAP@50-95** | `0.2294` | **22.94%** |
| **Inference Latency** | `6.5 ms / image` | **> 150 FPS** |

*Metrics recorded in `data/evidence/smoke_training_metrics.json`.*

---

## 3. Optical Smoke Colorimetry & Ringelmann Scale

In addition to bounding box localization, `backend/vision/smoke.py` extracts industrial metrics compliant with EPA / ISO standards:
- **Ringelmann Opacity Scale (0.0 to 10.0)**:
  - `< 2.0`: None (clear exhaust)
  - `2.0 - 5.9`: Light / moderate exhaust
  - `6.0 - 10.0`: Heavy exhaust (triggers maintenance flag & engine uncertainty widening)
- **Exhaust Plume Color**:
  - `black`: Incomplete combustion soot (air-to-fuel ratio, injector wear)
  - `blue`: Engine burning lubricating oil (piston ring / turbo seal wear)
  - `white`: Water vapor / coolant steam
  - `grey`: Cold engine unburned fuel
- **Maintenance Rule**: `score >= 6.0` or color in (`black`, `blue`) raises `maintenance_flag = True` with reason `"possible incomplete combustion or oil burning, inspect"`.

---

## 4. Reusable Scripts

### Train / Re-train Model
```powershell
py scripts/train_smoke_yolo.py --train --epochs 5 --fraction 0.05 --batch 16 --imgsz 640
```

### CLI Inference on Single Image / Video
```powershell
py scripts/detect_smoke.py data/datasets/valid/H_03383_png.rf.60acbffc990edce5cb8c1a57240c748a.jpg
```
*Saves annotated visualization to `data/evidence/annotated/`.*

### Dataset Benchmark on Validation Split
```powershell
py scripts/eval_smoke_dataset.py --split valid --samples 50
```

---

## 5. API Endpoints

- `GET /api/vision/smoke/status`: Returns loaded weights path and model readiness.
- `POST /api/vision/smoke/detect`: Accepts image file upload or `image_path` query parameter, returning JSON:
  ```json
  {
    "score_0_10": 9.9,
    "level": "heavy",
    "color": "grey",
    "opacity_pct": 99.0,
    "maintenance_flag": true,
    "maintenance_reason": "possible incomplete combustion or oil burning, inspect",
    "confidence": 0.99,
    "plume_bbox": {"x_min": 52.2, "y_min": 30.5, "x_max": 632.8, "y_max": 625.1},
    "method": "yolo_model"
  }
  ```
