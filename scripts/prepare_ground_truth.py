#!/usr/bin/env python3
"""
Prepare empty Khmer line-level ground-truth files.

This script finds images in raw_pages/, optionally crops each page into line
bands using a simple projection-based detector, and writes line images plus
matching empty .gt.txt files into ground_truth/.

The .gt.txt files are intentionally empty. Fill them manually with the exact
Khmer text shown in each line image before training.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image, ImageOps
except ImportError as exc:
    raise SystemExit(
        "Missing Python dependency: Pillow\n"
        "Install it with:\n\n"
        "  python3 -m pip install Pillow\n"
    ) from exc


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def iter_images(directory: Path) -> Iterable[Path]:
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def detect_line_boxes(
    image: Image.Image,
    threshold: int,
    min_line_height: int,
    min_gap: int,
    padding: int,
) -> list[tuple[int, int, int, int]]:
    gray = ImageOps.grayscale(image)
    # Treat darker pixels as ink. This works best for clean black text on light paper.
    rows_with_ink: list[int] = []
    width, height = gray.size
    pixels = gray.load()

    for y in range(height):
        dark_pixels = 0
        for x in range(width):
            if pixels[x, y] < threshold:
                dark_pixels += 1
        if dark_pixels > max(2, width * 0.002):
            rows_with_ink.append(y)

    if not rows_with_ink:
        return [(0, 0, width, height)]

    bands: list[tuple[int, int]] = []
    start = rows_with_ink[0]
    previous = rows_with_ink[0]

    for y in rows_with_ink[1:]:
        if y - previous > min_gap:
            bands.append((start, previous))
            start = y
        previous = y
    bands.append((start, previous))

    boxes: list[tuple[int, int, int, int]] = []
    for top, bottom in bands:
        if bottom - top + 1 < min_line_height:
            continue
        y1 = max(0, top - padding)
        y2 = min(height, bottom + padding + 1)
        boxes.append((0, y1, width, y2))

    return boxes or [(0, 0, width, height)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create line images and empty .gt.txt files.")
    parser.add_argument("--raw-dir", default="raw_pages", type=Path)
    parser.add_argument("--output-dir", default="ground_truth", type=Path)
    parser.add_argument("--also-copy-to-line-images", action="store_true")
    parser.add_argument("--line-images-dir", default="line_images", type=Path)
    parser.add_argument("--threshold", default=210, type=int)
    parser.add_argument("--min-line-height", default=18, type=int)
    parser.add_argument("--min-gap", default=8, type=int)
    parser.add_argument("--padding", default=6, type=int)
    parser.add_argument(
        "--whole-page",
        action="store_true",
        help="Do not crop into lines; create one image per page.",
    )
    args = parser.parse_args()

    root = Path.cwd()
    raw_dir = (root / args.raw_dir).resolve()
    output_dir = (root / args.output_dir).resolve()
    line_images_dir = (root / args.line_images_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    if args.also_copy_to_line_images:
        line_images_dir.mkdir(parents=True, exist_ok=True)

    pages = list(iter_images(raw_dir))
    if not pages:
        print(f"No page images found in {raw_dir}")
        print("Add scanned pages first, then run this script again.")
        return 1

    line_number = 1
    for page in pages:
        with Image.open(page) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            boxes = (
                [(0, 0, image.width, image.height)]
                if args.whole_page
                else detect_line_boxes(
                    image,
                    threshold=args.threshold,
                    min_line_height=args.min_line_height,
                    min_gap=args.min_gap,
                    padding=args.padding,
                )
            )

            for box in boxes:
                line_name = f"line_{line_number:04d}"
                line_path = output_dir / f"{line_name}.png"
                gt_path = output_dir / f"{line_name}.gt.txt"
                crop = image.crop(box)
                crop.save(line_path)
                gt_path.touch(exist_ok=True)

                if args.also_copy_to_line_images:
                    crop.save(line_images_dir / f"{line_name}.png")

                print(f"Created {line_path.name} and {gt_path.name}")
                line_number += 1

    print()
    print(f"Created {line_number - 1} line image(s) in {output_dir}")
    print("Now manually fill every .gt.txt file with the exact Khmer text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
