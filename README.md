# Tesseract Khmer Training

Standalone, GitHub-ready workspace for fine-tuning Khmer Tesseract OCR and
exporting a custom model:

```text
output/khm_custom.traineddata
```

This project is intentionally separate from any Flutter app. It does not modify
Flutter project files.

## Features

- Fine-tunes from `tessdata_best/khm.traineddata`
- Uses official `tesseract-ocr/tesstrain`
- Generates Tesseract-compatible line image and `.gt.txt` pairs
- Imports annotated XML datasets into line-level ground truth
- Validates missing or empty ground truth before training
- Supports full training, fast subset training, and non-repeating batch training
- Compares original `khm` OCR output against `khm_custom`
- Exports `output/khm_custom.traineddata`

## Repository Layout

```text
tesseract_khmer_training/
  raw_pages/          # local scanned pages, not committed
  line_images/        # generated line images, not committed
  ground_truth/       # generated/manual training pairs, not committed
  test_images/        # local OCR test images, not committed
  scripts/            # setup, import, validation, training helpers
  tesstrain/          # official tesstrain clone, not committed
  tessdata_best/      # downloaded base models, not committed
  output/             # checkpoints, comparisons, exported model, not committed
  Makefile
```

## Requirements

macOS with Homebrew:

```sh
brew install tesseract wget unzip git make python
python3 -m pip install Pillow
```

Homebrew installs modern GNU Make as `gmake`. The training wrapper uses `gmake`
automatically because macOS `/usr/bin/make` is too old for official `tesstrain`.

Check your machine:

```sh
make check
```

## Setup

Clone official `tesstrain` and download base models:

```sh
make setup
```

This prepares:

```text
tesstrain/
tessdata_best/khm.traineddata
tessdata_best/eng.traineddata
```

## Prepare Ground Truth From Scans

Place scanned Khmer page images in:

```text
raw_pages/
```

Supported formats:

```text
.png .jpg .jpeg .tif .tiff .bmp
```

Generate line images and empty `.gt.txt` files:

```sh
make prepare
```

Then manually fill each `.gt.txt` with the exact Khmer text shown in the
matching image.

Ground-truth rules:

- Do not fake Khmer text.
- Do not use OCR output as final ground truth.
- Manually verify every `.gt.txt`.
- Every `.png` must have a matching non-empty `.gt.txt`.

Validate before training:

```sh
make validate
```

## Import Annotated Archive XML

If you have an annotated `archive/` folder beside this project:

```text
../archive/
  PNG_Files/PNG_Files/
  XML_Files/XML_Files/
```

Import XML line annotations:

```sh
make import-archive
```

This creates cropped line images and `.gt.txt` files in `ground_truth/` using
the supplied XML text annotations.

## Training Modes

### Full Training

Uses all valid pairs in `ground_truth/`:

```sh
make train TESSTRAIN_JOBS=8
```

Default full settings:

```text
MODEL_NAME=khm_custom
START_MODEL=khm
TESSDATA=./tessdata_best
MAX_ITERATIONS=10000
RATIO_TRAIN=0.90
```

Full training can take many hours on large datasets.

### Fast First Model

Create a smaller random subset and train fewer iterations:

```sh
make train-fast
```

Change subset size:

```sh
make train-fast FAST_LIMIT=10000
```

### Non-Repeating Batch Training

Train in chunks without reusing the same source lines:

```sh
make train-batch
```

By default this creates a fresh 2,000-line batch in `ground_truth_batch/`,
trains it, and marks those original source lines as used only if training
succeeds.

Check used and remaining lines:

```sh
make batch-status
```

Change batch size:

```sh
make train-batch BATCH_SIZE=5000
```

Reset used-line history:

```sh
make batch-reset
```

The used manifest is stored at:

```text
output/batches/used_stems.txt
```

## Export

After training finishes:

```sh
make export
```

Final model:

```text
output/khm_custom.traineddata
```

## Compare Original vs Custom OCR

Put test images into:

```text
test_images/
```

Run:

```sh
make compare
```

Results are written to:

```text
output/comparison/
```

For each test image:

```text
example.khm.txt
example.khm_custom.txt
example.side_by_side.txt
```

## Use In Flutter

This repository does not modify Flutter apps. After export, manually copy:

```text
output/khm_custom.traineddata
```

to your Flutter app's Tesseract asset location.

## Data And Model Policy

Large local data and generated models are ignored by Git:

- raw scans
- generated ground truth
- `tesstrain/`
- `tessdata_best/*.traineddata`
- checkpoints
- exported `.traineddata` files

Keep private scans and copyrighted datasets out of GitHub.

## License

MIT. See [LICENSE](LICENSE).
