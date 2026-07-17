#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INPUT_DIR="${INPUT_DIR:-$ROOT_DIR/train_one}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/output}"
MODEL_NAME="${MODEL_NAME:-khm_custom}"
MAX_ITERATIONS="${MAX_ITERATIONS:-2}"
LEARNING_RATE="${LEARNING_RATE:-0.00001}"
BASE_MODEL="$ROOT_DIR/tessdata_best/khm.traineddata"
CURRENT_MODEL="$OUTPUT_DIR/$MODEL_NAME.traineddata"

cd "$ROOT_DIR"

if [[ ! -d "$INPUT_DIR" ]]; then
  echo "ERROR: Input folder does not exist: $INPUT_DIR"
  exit 1
fi

shopt -s nullglob
images=("$INPUT_DIR"/*.png)
texts=("$INPUT_DIR"/*.gt.txt)

if [[ "${#images[@]}" -ne 1 || "${#texts[@]}" -ne 1 ]]; then
  echo "ERROR: Put exactly one .png and one .gt.txt file in: $INPUT_DIR"
  echo "The names must match, for example:"
  echo "  sample.png"
  echo "  sample.gt.txt"
  exit 1
fi

image="${images[0]}"
stem="$(basename "$image" .png)"
expected_text="$INPUT_DIR/$stem.gt.txt"
if [[ ! -f "$expected_text" ]]; then
  echo "ERROR: Missing matching text file: $expected_text"
  exit 1
fi
if [[ ! -s "$expected_text" ]] || [[ -z "$(tr -d '[:space:]' < "$expected_text")" ]]; then
  echo "ERROR: Ground-truth text is empty: $expected_text"
  exit 1
fi

if [[ -f "$CURRENT_MODEL" ]]; then
  seed_model="$CURRENT_MODEL"
  echo "Continuing from current model: $CURRENT_MODEL"
elif [[ -f "$BASE_MODEL" ]]; then
  seed_model="$BASE_MODEL"
  echo "No custom model found; starting from: $BASE_MODEL"
else
  echo "ERROR: No starting model found. Run: make setup"
  exit 1
fi

if [[ ! -f tesstrain/generate_line_box.py ]]; then
  echo "ERROR: official tesstrain is missing. Run: make setup"
  exit 1
fi

mkdir -p "$OUTPUT_DIR" "$OUTPUT_DIR/backups"
run_dir="$(mktemp -d "$OUTPUT_DIR/.train-one.XXXXXX")"
trap 'rm -rf "$run_dir"' EXIT

training_dir="$run_dir/training"
checkpoint_dir="$run_dir/checkpoints"
mkdir -p "$training_dir" "$checkpoint_dir"

# Use real copies because Tesseract may not follow sandboxed temporary symlinks.
cp "$image" "$training_dir/sample.png"
cp "$expected_text" "$training_dir/sample.gt.txt"

python3 tesstrain/generate_line_box.py \
  -i "$training_dir/sample.png" \
  -t "$training_dir/sample.gt.txt" \
  > "$training_dir/sample.box"
tesseract "$training_dir/sample.png" "$training_dir/sample" --psm 13 lstm.train

printf '%s\n' "$training_dir/sample.lstmf" > "$run_dir/list.train"
# Tesseract requires an evaluation list. Reusing the supplied example here is
# only a runtime requirement; it is not presented as a general accuracy score.
printf '%s\n' "$training_dir/sample.lstmf" > "$run_dir/list.eval"

combine_tessdata -e "$seed_model" "$run_dir/seed.lstm" >/dev/null

lstmtraining \
  --debug_interval 0 \
  --traineddata "$seed_model" \
  --old_traineddata "$seed_model" \
  --continue_from "$run_dir/seed.lstm" \
  --learning_rate "$LEARNING_RATE" \
  --model_output "$checkpoint_dir/$MODEL_NAME" \
  --train_listfile "$run_dir/list.train" \
  --eval_listfile "$run_dir/list.eval" \
  --max_iterations "$MAX_ITERATIONS" \
  --target_error_rate 0.01 \
  2>&1 | tee "$run_dir/training.log"

checkpoint="$checkpoint_dir/${MODEL_NAME}_checkpoint"
if [[ ! -s "$checkpoint" ]]; then
  echo "ERROR: Training finished without producing a checkpoint."
  exit 1
fi

candidate="$run_dir/$MODEL_NAME.traineddata"
lstmtraining \
  --stop_training \
  --continue_from "$checkpoint" \
  --traineddata "$seed_model" \
  --model_output "$candidate"

if [[ ! -s "$candidate" ]]; then
  echo "ERROR: Training finished without producing a model."
  exit 1
fi

# Verify that Tesseract can unpack the final candidate before replacement.
combine_tessdata -u "$candidate" "$run_dir/verify" >/dev/null

timestamp="$(date +%Y%m%d-%H%M%S)"
if [[ -f "$CURRENT_MODEL" ]]; then
  backup="$OUTPUT_DIR/backups/${MODEL_NAME}-${timestamp}.traineddata"
  cp "$CURRENT_MODEL" "$backup"
  echo "Previous model backed up to: $backup"
fi

cp "$candidate" "$CURRENT_MODEL"

echo
echo "Updated model: $CURRENT_MODEL"
echo "Trained from:  $(basename "$image") + $(basename "$expected_text")"
echo "Iterations:    $MAX_ITERATIONS"
echo "Learning rate: $LEARNING_RATE"
