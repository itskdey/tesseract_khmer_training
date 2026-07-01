#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as exc:
    raise SystemExit(
        "Missing Python dependency: Pillow\n"
        "Install it with:\n\n"
        "  python3 -m pip install Pillow\n"
    ) from exc


def line_text(line: ET.Element) -> str:
    parts: list[str] = []
    for word in line.findall("word"):
        text_node = word.find("text")
        if text_node is not None and text_node.text is not None:
            parts.append(text_node.text)
    return "".join(parts).strip()


def line_bbox(line: ET.Element) -> tuple[int, int, int, int] | None:
    boxes: list[tuple[int, int, int, int]] = []
    for bbox in line.findall("./word/bbox"):
        try:
            boxes.append(
                (
                    int(float(bbox.attrib["x1"])),
                    int(float(bbox.attrib["y1"])),
                    int(float(bbox.attrib["x2"])),
                    int(float(bbox.attrib["y2"])),
                )
            )
        except (KeyError, ValueError):
            continue

    if not boxes:
        return None

    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import annotated archive XML into Tesseract line image ground truth."
    )
    parser.add_argument(
        "--archive-dir",
        default="../archive",
        type=Path,
        help="Path to archive containing PNG_Files/ and XML_Files/.",
    )
    parser.add_argument("--output-dir", default="ground_truth", type=Path)
    parser.add_argument("--line-images-dir", default="line_images", type=Path)
    parser.add_argument("--prefix", default="kh_archive")
    parser.add_argument("--padding", default=4, type=int)
    parser.add_argument("--limit", default=0, type=int, help="Optional max number of lines to import.")
    parser.add_argument(
        "--clear-output",
        action="store_true",
        help="Remove existing .png/.gt.txt files in output directories before importing.",
    )
    args = parser.parse_args()

    root = Path.cwd()
    archive_dir = (root / args.archive_dir).resolve()
    png_dir = archive_dir / "PNG_Files" / "PNG_Files"
    xml_dir = archive_dir / "XML_Files" / "XML_Files"
    output_dir = (root / args.output_dir).resolve()
    line_images_dir = (root / args.line_images_dir).resolve()

    if not png_dir.is_dir():
        print(f"ERROR: PNG directory not found: {png_dir}")
        return 1
    if not xml_dir.is_dir():
        print(f"ERROR: XML directory not found: {xml_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    line_images_dir.mkdir(parents=True, exist_ok=True)

    if args.clear_output:
        for directory in (output_dir, line_images_dir):
            for path in directory.glob("*.png"):
                path.unlink()
            for path in directory.glob("*.gt.txt"):
                path.unlink()

    xml_files = sorted(xml_dir.glob("*.xml"), key=lambda path: path.stem)
    if not xml_files:
        print(f"ERROR: No XML files found in {xml_dir}")
        return 1

    imported = 0
    skipped = 0

    for xml_path in xml_files:
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError as exc:
            print(f"SKIP XML parse error: {xml_path} ({exc})")
            skipped += 1
            continue

        image_name = tree.getroot().findtext("image") or f"{xml_path.stem}.png"
        image_path = png_dir / image_name
        if not image_path.exists():
            print(f"SKIP missing image: {image_path}")
            skipped += 1
            continue

        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")

            for line in tree.findall(".//line"):
                text = line_text(line)
                bbox = line_bbox(line)
                if not text or bbox is None:
                    skipped += 1
                    continue

                x1, y1, x2, y2 = bbox
                x1 = max(0, x1 - args.padding)
                y1 = max(0, y1 - args.padding)
                x2 = min(image.width, x2 + args.padding)
                y2 = min(image.height, y2 + args.padding)
                if x2 <= x1 or y2 <= y1:
                    skipped += 1
                    continue

                imported += 1
                out_stem = f"{args.prefix}_{imported:06d}"
                line_image_path = output_dir / f"{out_stem}.png"
                gt_path = output_dir / f"{out_stem}.gt.txt"

                crop = image.crop((x1, y1, x2, y2))
                crop.save(line_image_path)
                gt_path.write_text(text + "\n", encoding="utf-8")
                shutil.copy2(line_image_path, line_images_dir / line_image_path.name)

                if args.limit and imported >= args.limit:
                    print(f"Imported {imported} annotated line(s).")
                    print(f"Skipped {skipped} item(s).")
                    return 0

    print(f"Imported {imported} annotated line(s).")
    print(f"Skipped {skipped} item(s).")
    return 0 if imported else 1


if __name__ == "__main__":
    raise SystemExit(main())
