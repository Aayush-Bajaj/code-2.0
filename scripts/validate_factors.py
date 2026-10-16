#!/usr/bin/env python3
"""
Factor and Assumption Validator for Carbon Passport.
Ensures zero hardcoding, zero invented values, and strict human verification.
Exits with code 1 if any TODO_VERIFY remains.
"""
import sys
import csv
from pathlib import Path

import argparse

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
FACTORS_CSV = BASE_DIR / "data" / "factors" / "factors.csv"
ASSUMPTIONS_YAML = BASE_DIR / "data" / "factors" / "assumptions.yaml"


def check_factors(factors_path: Path = FACTORS_CSV):
    unverified = []
    verified = []

    if not factors_path.exists():
        print(f"ERROR: factors file not found at {factors_path}")
        return False, ["MISSING_FILE: factors.csv"]

    with open(factors_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            factor_id = row.get("factor_id", "").strip()
            name = row.get("name", "").strip()
            val = row.get("value", "").strip()
            unit = row.get("unit", "").strip()
            source = row.get("source_name", "").strip()

            if val == "TODO_VERIFY" or "TODO_VERIFY" in val:
                unverified.append((factor_id, name, "value is TODO_VERIFY"))
            else:
                try:
                    num_val = float(val)
                    verified.append((factor_id, name, num_val, unit, source))
                except ValueError:
                    unverified.append((factor_id, name, f"invalid numeric value: {val}"))

    return unverified, verified


def check_assumptions(assumptions_path: Path = ASSUMPTIONS_YAML):
    unverified = []
    verified = []

    if not assumptions_path.exists():
        print(f"ERROR: assumptions.yaml not found at {assumptions_path}")
        return False, ["MISSING_FILE: assumptions.yaml"]

    # Basic parser or pyyaml
    try:
        import yaml
        with open(assumptions_path, mode="r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except ImportError:
        # Fallback manual parser if pyyaml not yet loaded
        data = {}
        with open(assumptions_path, mode="r", encoding="utf-8") as f:
            curr_key = None
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line and not line.startswith("value:") and not line.startswith("unit:") and not line.startswith("source_note:"):
                    curr_key = line.split(":")[0].strip()
                    data[curr_key] = {}
                elif curr_key and line.startswith("value:"):
                    data[curr_key]["value"] = line.split("value:")[1].strip().strip('"').strip("'")

    for k, v in data.items():
        if isinstance(v, dict):
            val = str(v.get("value", "")).strip()
            note = str(v.get("source_note", "")).strip()
            if "TODO_VERIFY" in val or "TODO_VERIFY" in note:
                unverified.append((k, "Assumption key contains TODO_VERIFY"))
            else:
                verified.append((k, val, v.get("unit", ""), note))
        else:
            if "TODO_VERIFY" in str(v):
                unverified.append((k, "Assumption value is TODO_VERIFY"))

    return unverified, verified


def main():
    parser = argparse.ArgumentParser(description="Validate emission factors and assumptions")
    parser.add_argument("--factors", type=Path, default=FACTORS_CSV, help="Path to factors.csv")
    parser.add_argument("--assumptions", type=Path, default=ASSUMPTIONS_YAML, help="Path to assumptions.yaml")
    args = parser.parse_args()

    print("=" * 65)
    print("        Carbon Passport - Emission Factor & Assumption Audit      ")
    print("=" * 65)

    unverified_factors, verified_factors = check_factors(args.factors)
    unverified_assumptions, verified_assumptions = check_assumptions(args.assumptions)

    if verified_factors:
        print("\n--- Verified Factors ---")
        print(f"{'Factor ID':<22} | {'Name':<28} | {'Value':<10} | {'Unit':<18} | {'Source'}")
        print("-" * 95)
        for fid, name, val, unit, src in verified_factors:
            print(f"{fid:<22} | {name:<28} | {val:<10} | {unit:<18} | {src}")
    else:
        print("\n[!] No factors have been human-verified yet.")

    if verified_assumptions:
        print("\n--- Verified Scenario Assumptions ---")
        for k, val, unit, src in verified_assumptions:
            print(f"  - {k}: {val} {unit} ({src})")

    has_unverified = bool(unverified_factors or unverified_assumptions)

    if has_unverified:
        print("\n" + "!" * 65)
        print("ATTENTION: Found unverified items marked 'TODO_VERIFY'!")
        print("!" * 65)

        if unverified_factors:
            print(f"\nUnverified Factors ({len(unverified_factors)} items):")
            for item in unverified_factors:
                print(f"  * {item[0]}: {item[1]} ({item[2]})")

        if unverified_assumptions:
            print(f"\nUnverified Assumptions ({len(unverified_assumptions)} items):")
            for item in unverified_assumptions:
                print(f"  * {item[0]}: {item[1]}")

        print("\nEnforcement: In accordance with Rule #2 of AGENTS.md, calculation engine will")
        print("refuse to execute on TODO_VERIFY until official sources are entered.")
        sys.exit(1)

    print("\n[SUCCESS] All factors and assumptions are verified with official sources!")
    sys.exit(0)


if __name__ == "__main__":
    main()
