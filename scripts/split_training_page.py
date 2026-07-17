#!/usr/bin/env python3
"""Convert one page image plus multi-line text into line-level training pairs."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
from io import StringIO
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as exc:
    raise SystemExit(
        "Missing Python dependency: Pillow\nInstall it with:\n\n"
        "  python3 -m pip install Pillow"
    ) from exc


def text_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def detect_bands(
    image: Image.Image, threshold: int, min_gap: int, padding: int = 6
) -> list[tuple[int, int, int, int]]:
    gray = ImageOps.autocontrast(ImageOps.grayscale(image))
    width, height = gray.size
    pixels = gray.load()
    minimum_ink = max(3, int(width * 0.0015))
    ink_rows: list[int] = []

    for y in range(height):
        dark = 0
        for x in range(width):
            if pixels[x, y] < threshold:
                dark += 1
                if dark >= minimum_ink:
                    ink_rows.append(y)
                    break

    if not ink_rows:
        return []

    bands: list[tuple[int, int]] = []
    top = previous = ink_rows[0]
    for y in ink_rows[1:]:
        if y - previous > min_gap:
            bands.append((top, previous))
            top = y
        previous = y
    bands.append((top, previous))

    boxes: list[tuple[int, int, int, int]] = []
    for top, bottom in bands:
        # Ignore isolated dust while retaining small Khmer marks grouped nearby.
        if bottom - top + 1 < 4:
            continue
        boxes.append(
            (0, max(0, top - padding), width, min(height, bottom + padding + 1))
        )
    return boxes


def tesseract_line_boxes(
    image_path: Path, image_size: tuple[int, int], padding: int = 6
) -> list[tuple[int, int, int, int]]:
    tessdata_dir = Path(__file__).resolve().parents[1] / "tessdata_best"
    result = subprocess.run(
        [
            "tesseract",
            str(image_path),
            "stdout",
            "--tessdata-dir",
            str(tessdata_dir),
            "-l",
            "khm",
            "--psm",
            "6",
            "tsv",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return []

    width, height = image_size
    boxes: list[tuple[int, int, int, int]] = []
    for row in csv.DictReader(StringIO(result.stdout), delimiter="\t"):
        try:
            if int(row["level"]) != 4:
                continue
            left = int(row["left"])
            top = int(row["top"])
            line_width = int(row["width"])
            line_height = int(row["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if line_width <= 0 or line_height <= 0:
            continue
        boxes.append(
            (
                max(0, left - padding),
                max(0, top - padding),
                min(width, left + line_width + padding),
                min(height, top + line_height + padding),
            )
        )
    return sorted(boxes, key=lambda box: (box[1], box[0]))


def guided_valley_boxes(
    image: Image.Image, expected: int
) -> list[tuple[int, int, int, int]]:
    """Split at the lightest rows near expected line boundaries."""
    gray = ImageOps.autocontrast(ImageOps.grayscale(image))
    width, height = gray.size
    pixels = gray.load()
    darkness: list[int] = []
    for y in range(height):
        score = 0
        for x in range(width):
            value = pixels[x, y]
            if value < 235:
                score += 235 - value
        darkness.append(score)

    nonblank = [index for index, score in enumerate(darkness) if score > width * 2]
    if not nonblank:
        return []
    content_top = nonblank[0]
    content_bottom = nonblank[-1] + 1
    content_height = content_bottom - content_top
    if content_height < expected * 4:
        return []

    boundaries = [content_top]
    search_radius = max(3, content_height // (expected * 3))
    for index in range(1, expected):
        ideal = content_top + round(content_height * index / expected)
        low = max(boundaries[-1] + 3, ideal - search_radius)
        high = min(content_bottom - 3, ideal + search_radius)
        if high <= low:
            return []
        boundary = min(
            range(low, high + 1),
            key=lambda y: sum(darkness[max(0, y - 2) : min(height, y + 3)]),
        )
        boundaries.append(boundary)
    boundaries.append(content_bottom)

    padding = 6
    return [
        (
            0,
            max(0, boundaries[index] - padding),
            width,
            min(height, boundaries[index + 1] + padding),
        )
        for index in range(expected)
    ]


def find_matching_boxes(
    image: Image.Image, image_path: Path, expected: int
) -> tuple[list[tuple[int, int, int, int]], set[int], str]:
    layout_boxes = tesseract_line_boxes(image_path, image.size)
    attempts: set[int] = {len(layout_boxes)}
    if len(layout_boxes) == expected:
        return layout_boxes, attempts, "Tesseract layout analysis"

    candidates: list[tuple[int, int, list[tuple[int, int, int, int]]]] = []
    for threshold in (210, 195, 225, 180, 235):
        for min_gap in (8, 6, 10, 4, 12, 16):
            boxes = detect_bands(image, threshold=threshold, min_gap=min_gap)
            attempts.add(len(boxes))
            if len(boxes) == expected:
                score = abs(threshold - 210) + abs(min_gap - 8) * 3
                candidates.append((score, min_gap, boxes))
    if not candidates:
        guided = guided_valley_boxes(image, expected)
        if len(guided) == expected:
            return guided, attempts, "ground-truth-guided whitespace splitting"
        return [], attempts, ""
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2], attempts, "pixel projection"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--text", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    lines = text_lines(args.text)
    if not lines:
        print(f"ERROR: Ground truth is empty: {args.text}")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if len(lines) == 1:
        shutil.copy2(args.image, args.output_dir / "sample_0001.png")
        (args.output_dir / "sample_0001.gt.txt").write_text(
            lines[0] + "\n", encoding="utf-8"
        )
        print("Prepared 1 line-level training pair.")
        return 0

    with Image.open(args.image) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        boxes, detected_counts, method = find_matching_boxes(
            image, args.image, len(lines)
        )
        if not boxes:
            counts = ", ".join(str(value) for value in sorted(detected_counts))
            print(
                f"ERROR: Ground truth contains {len(lines)} non-empty lines, but "
                f"automatic page segmentation found these possible line counts: {counts}."
            )
            print("Use a clean page image, or crop it into one image per text line.")
            return 1

        for index, (box, text) in enumerate(zip(boxes, lines), start=1):
            stem = f"sample_{index:04d}"
            image.crop(box).save(args.output_dir / f"{stem}.png")
            (args.output_dir / f"{stem}.gt.txt").write_text(
                text + "\n", encoding="utf-8"
            )

    print(f"Split page into {len(lines)} line-level training pairs using {method}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
