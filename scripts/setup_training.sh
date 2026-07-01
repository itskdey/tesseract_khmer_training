#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESSTRAIN_DIR="$ROOT_DIR/tesstrain"
TESSDATA_DIR="$ROOT_DIR/tessdata_best"
TESSTRAIN_REPO="https://github.com/tesseract-ocr/tesstrain.git"
TESSDATA_BEST_BASE="https://github.com/tesseract-ocr/tessdata_best/raw/main"

mkdir -p "$TESSTRAIN_DIR" "$TESSDATA_DIR"

if [[ -d "$TESSTRAIN_DIR/.git" ]]; then
  echo "tesstrain already exists. Updating official tesstrain..."
  git -C "$TESSTRAIN_DIR" pull --ff-only
else
  if [[ -f "$TESSTRAIN_DIR/.gitkeep" ]] && [[ -z "$(find "$TESSTRAIN_DIR" -mindepth 1 -maxdepth 1 ! -name .gitkeep 2>/dev/null)" ]]; then
    rm "$TESSTRAIN_DIR/.gitkeep"
  fi

  if [[ -n "$(find "$TESSTRAIN_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
    echo "ERROR: $TESSTRAIN_DIR is not empty and is not a git clone."
    echo "Move its contents away or remove it, then run setup again."
    exit 1
  fi

  echo "Cloning official tesstrain into $TESSTRAIN_DIR..."
  git clone "$TESSTRAIN_REPO" "$TESSTRAIN_DIR"
fi

download_traineddata() {
  local lang="$1"
  local target="$TESSDATA_DIR/$lang.traineddata"

  if [[ -f "$target" ]]; then
    echo "$lang.traineddata already exists."
    return
  fi

  echo "Downloading tessdata_best/$lang.traineddata..."
  wget -O "$target" "$TESSDATA_BEST_BASE/$lang.traineddata"
}

download_traineddata khm
download_traineddata eng

echo "Setup complete."
echo "Base models are in: $TESSDATA_DIR"
echo "tesstrain is in:    $TESSTRAIN_DIR"
