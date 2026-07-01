#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$ROOT_DIR/test_images"
OUTPUT_DIR="$ROOT_DIR/output/comparison"
CUSTOM_MODEL="$ROOT_DIR/output/khm_custom.traineddata"
BASE_MODEL="$ROOT_DIR/tessdata_best/khm.traineddata"

mkdir -p "$OUTPUT_DIR"

if [[ ! -f "$CUSTOM_MODEL" ]]; then
  echo "ERROR: Missing custom model: $CUSTOM_MODEL"
  echo "Run: make export"
  exit 1
fi

if [[ ! -f "$BASE_MODEL" ]]; then
  echo "ERROR: Missing base Khmer model: $BASE_MODEL"
  echo "Run: make setup"
  exit 1
fi

shopt -s nullglob
images=(
  "$TEST_DIR"/*.png
  "$TEST_DIR"/*.jpg
  "$TEST_DIR"/*.jpeg
  "$TEST_DIR"/*.tif
  "$TEST_DIR"/*.tiff
  "$TEST_DIR"/*.bmp
)

if [[ "${#images[@]}" -eq 0 ]]; then
  echo "ERROR: No test images found in $TEST_DIR"
  exit 1
fi

for image in "${images[@]}"; do
  base="$(basename "$image")"
  stem="${base%.*}"
  old_txt="$OUTPUT_DIR/${stem}.khm.txt"
  custom_txt="$OUTPUT_DIR/${stem}.khm_custom.txt"
  side_by_side="$OUTPUT_DIR/${stem}.side_by_side.txt"

  echo "OCR comparison for $base"
  tesseract "$image" "$OUTPUT_DIR/${stem}.khm" -l khm --tessdata-dir "$ROOT_DIR/tessdata_best"
  tesseract "$image" "$OUTPUT_DIR/${stem}.khm_custom" -l khm_custom --tessdata-dir "$ROOT_DIR/output"

  {
    printf "IMAGE: %s\n\n" "$base"
    printf "===== khm =====\n"
    cat "$old_txt"
    printf "\n\n===== khm_custom =====\n"
    cat "$custom_txt"
    printf "\n"
  } > "$side_by_side"

  echo "  wrote $old_txt"
  echo "  wrote $custom_txt"
  echo "  wrote $side_by_side"
done

echo "Comparison output is in: $OUTPUT_DIR"
