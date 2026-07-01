#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
from pathlib import Path


def link_or_copy(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        target.symlink_to(source.resolve())
    except OSError:
        target.write_bytes(source.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a smaller Tesseract ground-truth subset.")
    parser.add_argument("--source-dir", default="ground_truth", type=Path)
    parser.add_argument("--output-dir", default="ground_truth_fast", type=Path)
    parser.add_argument("--limit", default=5000, type=int)
    parser.add_argument("--seed", default=42, type=int)
    parser.add_argument("--prefix", default="kh_fast")
    parser.add_argument("--clear-output", action="store_true")
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.clear_output:
        for pattern in ("*.png", "*.gt.txt", "*.box", "*.lstmf"):
            for path in output_dir.glob(pattern):
                if path.exists() or path.is_symlink():
                    path.unlink()

    candidates = []
    for image_path in sorted(source_dir.glob("*.png")):
        gt_path = image_path.with_suffix(".gt.txt")
        if gt_path.exists() and gt_path.read_text(encoding="utf-8").strip():
            candidates.append((image_path, gt_path))

    if not candidates:
        print(f"ERROR: No valid source pairs found in {source_dir}")
        return 1

    rng = random.Random(args.seed)
    rng.shuffle(candidates)
    selected = candidates[: min(args.limit, len(candidates))]

    for index, (image_path, gt_path) in enumerate(selected, start=1):
        stem = f"{args.prefix}_{index:05d}"
        link_or_copy(image_path, output_dir / f"{stem}.png")
        link_or_copy(gt_path, output_dir / f"{stem}.gt.txt")

    print(f"Created {len(selected)} pair subset in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
