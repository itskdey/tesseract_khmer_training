#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODEL_NAME="${MODEL_NAME:-khm_custom}"
START_MODEL="${START_MODEL:-khm}"
TESSDATA="${TESSDATA:-$ROOT_DIR/tessdata_best}"
GROUND_TRUTH_DIR="${GROUND_TRUTH_DIR:-$ROOT_DIR/ground_truth}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/output}"
MAX_ITERATIONS="${MAX_ITERATIONS:-10000}"
RATIO_TRAIN="${RATIO_TRAIN:-0.90}"
TESSTRAIN_JOBS="${TESSTRAIN_JOBS:-4}"

cd "$ROOT_DIR"

if [[ "$TESSDATA" != /* ]]; then
  TESSDATA="$ROOT_DIR/${TESSDATA#./}"
fi

python3 scripts/validate_ground_truth.py --ground-truth-dir "$GROUND_TRUTH_DIR"

if [[ ! -f "$TESSDATA/$START_MODEL.traineddata" ]]; then
  echo "ERROR: Missing base model: $TESSDATA/$START_MODEL.traineddata"
  echo "Run: make setup"
  exit 1
fi

if [[ ! -f "tesstrain/Makefile" ]]; then
  echo "ERROR: official tesstrain is missing or incomplete."
  echo "Run: make setup"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

TESSTRAIN_MAKE="${TESSTRAIN_MAKE:-}"
if [[ -z "$TESSTRAIN_MAKE" ]]; then
  if command -v gmake >/dev/null 2>&1; then
    TESSTRAIN_MAKE="gmake"
  else
    TESSTRAIN_MAKE="make"
  fi
fi

echo "Starting Khmer fine-tuning..."
echo "  MODEL_NAME=$MODEL_NAME"
echo "  START_MODEL=$START_MODEL"
echo "  TESSDATA=$TESSDATA"
echo "  GROUND_TRUTH_DIR=$GROUND_TRUTH_DIR"
echo "  OUTPUT_DIR=$OUTPUT_DIR"
echo "  MAX_ITERATIONS=$MAX_ITERATIONS"
echo "  RATIO_TRAIN=$RATIO_TRAIN"
echo "  TESSTRAIN_MAKE=$TESSTRAIN_MAKE"
echo "  TESSTRAIN_JOBS=$TESSTRAIN_JOBS"

"$TESSTRAIN_MAKE" -j "$TESSTRAIN_JOBS" -C tesstrain training \
  MODEL_NAME="$MODEL_NAME" \
  START_MODEL="$START_MODEL" \
  TESSDATA="$TESSDATA" \
  MAX_ITERATIONS="$MAX_ITERATIONS" \
  RATIO_TRAIN="$RATIO_TRAIN" \
  GROUND_TRUTH_DIR="$GROUND_TRUTH_DIR" \
  OUTPUT_DIR="$OUTPUT_DIR"

echo "Training command finished."
echo "Run: make export"
