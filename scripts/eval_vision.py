#!/usr/bin/env python3
"""
Evaluation script for Carbon Passport Vision Pipeline.
Evaluates video clips in data/samples/clips against expected ground-truth labels
in data/samples/labels.json. Prints an honest evaluation table and logs failures.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.vision.pipeline import process_media
from backend.config import settings

DEFAULT_CLIPS_DIR = BASE_DIR / "data" / "samples" / "clips"
DEFAULT_LABELS_FILE = BASE_DIR / "data" / "samples" / "labels.json"


def load_expected_labels(labels_file: Path) -> Dict[str, Any]:
    if not labels_file.exists():
        # Provide default template labels if not yet filled
        sample_defaults = {
            "generator_blacksmoke.mp4": {
                "machine_type": "diesel_generator",
                "maintenance_flag": True,
                "smoke_level": "heavy"
            },
            "generator_nosmoke.mp4": {
                "machine_type": "diesel_generator",
                "maintenance_flag": False,
                "smoke_level": "none"
            },
            "forklift.mp4": {
                "machine_type": "forklift",
                "maintenance_flag": False,
                "smoke_level": "none"
            },
            "truck.mp4": {
                "machine_type": "truck",
                "maintenance_flag": False,
                "smoke_level": "light"
            }
        }
        with open(labels_file, "w", encoding="utf-8") as f:
            json.dump(sample_defaults, f, indent=2)
        return sample_defaults

    with open(labels_file, "r", encoding="utf-8") as f:
        return json.load(f)


def run_evaluation(clips_dir: Path, labels_file: Path, mock: bool = False):
    settings.MOCK_VISION = mock

    labels = load_expected_labels(labels_file)
    clip_files = list(clips_dir.glob("*.mp4")) + list(clips_dir.glob("*.avi")) + list(clips_dir.glob("*.mov"))

    print("\n=========================================================================================")
    print("                    CARBON PASSPORT - VISION PIPELINE EVALUATION                         ")
    print("=========================================================================================\n")
    print(f"Clips Directory : {clips_dir}")
    print(f"Labels File     : {labels_file}")
    print(f"MOCK_VISION     : {settings.MOCK_VISION}")
    print(f"Total Clips     : {len(clip_files)}\n")

    if not clip_files:
        print("[!] No video clips found in directory. Please place clips under data/samples/clips/.")
        print("    Example expected clips: generator_blacksmoke.mp4, generator_nosmoke.mp4, forklift.mp4, truck.mp4")
        return

    # Header
    col_w = [26, 16, 16, 10, 10, 8, 8]
    header = (
        f"{'Clip Filename':<{col_w[0]}} | "
        f"{'Pred Machine':<{col_w[1]}} | "
        f"{'Exp Machine':<{col_w[2]}} | "
        f"{'Pred Maint':<{col_w[3]}} | "
        f"{'Exp Maint':<{col_w[4]}} | "
        f"{'Smoke':<{col_w[5]}} | "
        f"{'Match':<{col_w[6]}}"
    )
    print(header)
    print("-" * len(header))

    total = 0
    machine_matches = 0
    maintenance_matches = 0
    failures = []

    for clip in sorted(clip_files):
        total += 1
        clip_name = clip.name
        expected = labels.get(clip_name, {})

        try:
            detections = process_media(str(clip), merge=True)
            det = detections[0]
            pred_machine = det.machine_type
            pred_maint = det.maintenance_flag
            pred_smoke = det.smoke.score_0_10
        except Exception as e:
            pred_machine = "ERROR"
            pred_maint = False
            pred_smoke = 0.0
            failures.append((clip_name, f"Pipeline exception: {e}"))

        exp_machine = expected.get("machine_type", "N/A")
        exp_maint = expected.get("maintenance_flag", None)

        m_match = (pred_machine == exp_machine) if exp_machine != "N/A" else True
        flag_match = (pred_maint == exp_maint) if exp_maint is not None else True

        if m_match and exp_machine != "N/A":
            machine_matches += 1
        if flag_match and exp_maint is not None:
            maintenance_matches += 1

        overall_ok = m_match and flag_match
        match_str = "PASS" if overall_ok else "FAIL"

        if not overall_ok:
            failures.append((
                clip_name,
                f"Mismatch - Machine: (pred={pred_machine}, exp={exp_machine}), "
                f"Maintenance: (pred={pred_maint}, exp={exp_maint})"
            ))

        print(
            f"{clip_name:<{col_w[0]}} | "
            f"{pred_machine:<{col_w[1]}} | "
            f"{str(exp_machine):<{col_w[2]}} | "
            f"{str(pred_maint):<{col_w[3]}} | "
            f"{str(exp_maint):<{col_w[4]}} | "
            f"{pred_smoke:<{col_w[5]}.1f} | "
            f"{match_str:<{col_w[6]}}"
        )

    print("-" * len(header))
    labeled_count = sum(1 for c in clip_files if c.name in labels)
    print(f"\nSummary:")
    print(f"- Total Evaluated: {total}")
    print(f"- Labeled Clips  : {labeled_count}")
    if labeled_count > 0:
        machine_acc = (machine_matches / labeled_count) * 100.0
        maint_acc = (maintenance_matches / labeled_count) * 100.0
        print(f"- Machine Type Accuracy  : {machine_acc:.1f}% ({machine_matches}/{labeled_count})")
        print(f"- Maintenance Flag Match : {maint_acc:.1f}% ({maintenance_matches}/{labeled_count})")

    if failures:
        print("\nFailures / Discrepancies:")
        for fname, reason in failures:
            print(f"  * {fname}: {reason}")
    else:
        print("\nAll labeled clips matched predictions successfully!")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Carbon Passport vision pipeline on sample clips.")
    parser.add_argument("--clips-dir", default=str(DEFAULT_CLIPS_DIR), help="Directory containing clip files")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS_FILE), help="Path to ground truth labels JSON")
    parser.add_argument("--mock", action="store_true", help="Force MOCK_VISION=1 for test run")
    args = parser.parse_args()

    clips_dir = Path(args.clips_dir)
    labels_file = Path(args.labels)

    clips_dir.mkdir(parents=True, exist_ok=True)
    run_evaluation(clips_dir, labels_file, mock=args.mock)


if __name__ == "__main__":
    main()
