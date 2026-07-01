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


def read_lines(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def valid_stems(source_dir: Path) -> list[str]:
    stems: list[str] = []
    for image_path in sorted(source_dir.glob("*.png")):
        gt_path = image_path.with_suffix(".gt.txt")
        if gt_path.exists() and gt_path.read_text(encoding="utf-8").strip():
            stems.append(image_path.stem)
    return stems


def clear_batch_dir(batch_dir: Path) -> None:
    batch_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.gt.txt", "*.box", "*.lstmf", ".batch_manifest.txt"):
        for path in batch_dir.glob(pattern):
            if path.exists() or path.is_symlink():
                path.unlink()


def create_batch(args: argparse.Namespace) -> int:
    source_dir = args.source_dir.resolve()
    batch_dir = args.batch_dir.resolve()
    used_file = args.used_file.resolve()
    pending_file = batch_dir / ".batch_manifest.txt"

    used = read_lines(used_file)
    stems = valid_stems(source_dir)
    remaining = [stem for stem in stems if stem not in used]

    if not remaining:
        print("No unused ground-truth pairs remain.")
        return 1

    rng = random.Random(args.seed + len(used))
    rng.shuffle(remaining)
    selected = sorted(remaining[: min(args.batch_size, len(remaining))])

    clear_batch_dir(batch_dir)
    for index, stem in enumerate(selected, start=1):
        out_stem = f"batch_{index:05d}"
        link_or_copy(source_dir / f"{stem}.png", batch_dir / f"{out_stem}.png")
        link_or_copy(source_dir / f"{stem}.gt.txt", batch_dir / f"{out_stem}.gt.txt")

    write_lines(pending_file, selected)
    print(f"Created batch with {len(selected)} pair(s).")
    print(f"Used before this batch: {len(used)}")
    print(f"Remaining after this batch succeeds: {len(remaining) - len(selected)}")
    print(f"Batch directory: {batch_dir}")
    return 0


def finalize_batch(args: argparse.Namespace) -> int:
    batch_dir = args.batch_dir.resolve()
    used_file = args.used_file.resolve()
    pending_file = batch_dir / ".batch_manifest.txt"

    pending = sorted(read_lines(pending_file))
    if not pending:
        print(f"ERROR: No pending batch manifest found at {pending_file}")
        return 1

    used = read_lines(used_file)
    merged = sorted(used.union(pending))
    write_lines(used_file, merged)
    pending_file.unlink()

    print(f"Marked {len(pending)} pair(s) as used.")
    print(f"Total used: {len(merged)}")
    return 0


def status(args: argparse.Namespace) -> int:
    source_dir = args.source_dir.resolve()
    used_file = args.used_file.resolve()
    stems = set(valid_stems(source_dir))
    used = read_lines(used_file).intersection(stems)
    print(f"Total valid pairs: {len(stems)}")
    print(f"Used pairs:        {len(used)}")
    print(f"Remaining pairs:   {len(stems) - len(used)}")
    return 0


def reset(args: argparse.Namespace) -> int:
    used_file = args.used_file.resolve()
    if used_file.exists():
        used_file.unlink()
    print(f"Reset used manifest: {used_file}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create non-repeating ground-truth batches.")
    parser.add_argument("command", choices=("create", "finalize", "status", "reset"))
    parser.add_argument("--source-dir", default="ground_truth", type=Path)
    parser.add_argument("--batch-dir", default="ground_truth_batch", type=Path)
    parser.add_argument("--used-file", default="output/batches/used_stems.txt", type=Path)
    parser.add_argument("--batch-size", default=2000, type=int)
    parser.add_argument("--seed", default=2026, type=int)
    args = parser.parse_args()

    if args.command == "create":
        return create_batch(args)
    if args.command == "finalize":
        return finalize_batch(args)
    if args.command == "status":
        return status(args)
    if args.command == "reset":
        return reset(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
