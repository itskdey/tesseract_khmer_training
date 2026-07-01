#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_NAME="${MODEL_NAME:-khm_custom}"
OUTPUT_DIR="$ROOT_DIR/output"
TARGET="$OUTPUT_DIR/$MODEL_NAME.traineddata"

mkdir -p "$OUTPUT_DIR"

candidate_paths=(
  "$OUTPUT_DIR/$MODEL_NAME.traineddata"
  "$OUTPUT_DIR/tessdata/$MODEL_NAME.traineddata"
  "$ROOT_DIR/tesstrain/data/$MODEL_NAME.traineddata"
  "$ROOT_DIR/tesstrain/data/$MODEL_NAME/$MODEL_NAME.traineddata"
)

source_model=""
for candidate in "${candidate_paths[@]}"; do
  if [[ -f "$candidate" ]]; then
    source_model="$candidate"
    break
  fi
done

if [[ -z "$source_model" ]]; then
  echo "ERROR: Could not find trained model for $MODEL_NAME."
  echo "Looked in:"
  for candidate in "${candidate_paths[@]}"; do
    echo "  $candidate"
  done
  echo "Run training first with: make train"
  exit 1
fi

if [[ "$source_model" != "$TARGET" ]]; then
  cp "$source_model" "$TARGET"
fi

echo "Exported: $TARGET"
