#!/usr/bin/env python3
"""
Downloads smoke dataset (train.zip and valid.zip) from Hugging Face
with progress bar and resume support, then extracts into data/raw/smoke/.
"""
import os
import sys
import zipfile
import requests
from pathlib import Path
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
TARGET_DIR = BASE_DIR / "data" / "raw" / "smoke"
TARGET_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOADS = [
    {
        "name": "train.zip",
        "url": "https://huggingface.co/datasets/keremberke/smoke-object-detection/resolve/main/data/train.zip",
        "extract_to": TARGET_DIR / "train",
    },
    {
        "name": "valid.zip",
        "url": "https://huggingface.co/datasets/keremberke/smoke-object-detection/resolve/main/data/valid.zip",
        "extract_to": TARGET_DIR / "valid",
    },
]


def download_with_resume(url: str, dest_path: Path):
    temp_path = dest_path.with_suffix(".zip.part")
    existing_size = temp_path.stat().st_size if temp_path.exists() else 0

    headers = {}
    if existing_size > 0:
        headers["Range"] = f"bytes={existing_size}-"

    print(f"Connecting to {url}...")
    response = requests.get(url, headers=headers, stream=True, timeout=30)

    # 416 Range Not Satisfiable -> file already complete
    if response.status_code == 416:
        print("Range not satisfiable; file already complete.")
        temp_path.rename(dest_path)
        return

    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0)) + existing_size
    mode = "ab" if existing_size > 0 else "wb"

    with open(temp_path, mode) as f, tqdm(
        desc=dest_path.name,
        initial=existing_size,
        total=total_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            if chunk:
                f.write(chunk)
                bar.update(len(chunk))

    temp_path.rename(dest_path)
    print(f"Saved: {dest_path}")


def extract_zip(zip_path: Path, extract_dir: Path):
    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {zip_path.name} to {extract_dir}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)
    print(f"Extracted to {extract_dir}")


def main():
    print("=== Downloading Smoke Dataset (Smoke100) ===")
    for item in DOWNLOADS:
        zip_file = TARGET_DIR / item["name"]
        if not zip_file.exists():
            download_with_resume(item["url"], zip_file)
        else:
            print(f"Already downloaded: {zip_file}")

        if not item["extract_to"].exists() or not any(item["extract_to"].iterdir()):
            extract_zip(zip_file, item["extract_to"])
        else:
            print(f"Already extracted: {item['extract_to']}")

    print("=== Download and extraction complete ===")


if __name__ == "__main__":
    main()
