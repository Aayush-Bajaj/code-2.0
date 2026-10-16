import json
import pytest
import subprocess
import sys
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
BILLS_DIR = BASE_DIR / "data" / "bills"
GT_PATH = BILLS_DIR / "ground_truth.json"
VALIDATE_SCRIPT = BASE_DIR / "scripts" / "validate_factors.py"


def test_validate_factors_fails_on_todo_verify(tmp_path):
    """Verify scripts/validate_factors.py returns non-zero when TODO_VERIFY is encountered."""
    unverified_yaml = tmp_path / "unverified_assumptions.yaml"
    unverified_yaml.write_text("test_key:\n  value: TODO_VERIFY\n  unit: inr\n  source_note: unverified\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT), "--assumptions", str(unverified_yaml)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "TODO_VERIFY" in result.stdout or "TODO_VERIFY" in result.stderr


def test_validate_factors_passes_on_production_data():
    """Verify scripts/validate_factors.py returns 0 on production factors and assumptions."""
    result = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Validation failed with: {result.stdout}\n{result.stderr}"
    assert "All factors and assumptions are verified" in result.stdout


def test_ground_truth_and_bills_generated():
    """Verify all 15 synthetic bills exist and ground_truth.json matches their filenames."""
    assert GT_PATH.exists(), "ground_truth.json does not exist"

    with open(GT_PATH, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    assert len(ground_truth) == 15, f"Expected 15 bills, got {len(ground_truth)}"

    types = {"electricity": 0, "diesel": 0, "freight": 0}
    for filename, item in ground_truth.items():
        bill_path = BILLS_DIR / filename
        assert bill_path.exists(), f"Bill file {filename} does not exist on disk"

        # Verify image is valid PNG
        with Image.open(bill_path) as img:
            assert img.format == "PNG"
            assert img.width > 500
            assert img.height > 500

        # Verify fields
        assert "bill_id" in item
        assert "bill_type" in item
        assert item["bill_type"] in types
        types[item["bill_type"]] += 1
        assert "supplier" in item
        assert item["quantity"] > 0
        assert item["amount_inr"] > 0

    assert types["electricity"] == 5
    assert types["diesel"] == 5
    assert types["freight"] == 5
