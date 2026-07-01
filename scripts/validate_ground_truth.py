#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Tesseract line image ground truth.")
    parser.add_argument("--ground-truth-dir", default="ground_truth", type=Path)
    args = parser.parse_args()

    gt_dir = args.ground_truth_dir
    png_files = sorted(gt_dir.glob("*.png"))
    txt_files = sorted(gt_dir.glob("*.gt.txt"))

    failures = 0

    if not png_files:
        print(f"ERROR: No .png line images found in {gt_dir}")
        failures += 1

    print("Checking that every .png has a matching .gt.txt...")
    for png in png_files:
        expected = png.with_suffix(".gt.txt")
        if not expected.exists():
            print(f"MISSING TXT: {expected}")
            failures += 1

    print("Checking that every .gt.txt has a matching .png...")
    for txt in txt_files:
        expected = txt.with_name(txt.name.removesuffix(".gt.txt") + ".png")
        if not expected.exists():
            print(f"MISSING PNG: {expected}")
            failures += 1

    print("Checking that every .gt.txt is not empty...")
    for txt in txt_files:
        if not txt.read_text(encoding="utf-8").strip():
            print(f"EMPTY TXT:   {txt}")
            failures += 1

    if failures:
        print()
        print(f"Ground-truth validation failed with {failures} issue(s).")
        print("Training is blocked until all line images have manually corrected text.")
        return 1

    print("Ground-truth validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
