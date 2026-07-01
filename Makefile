MODEL_NAME ?= khm_custom
START_MODEL ?= khm
TESSDATA ?= ./tessdata_best
GROUND_TRUTH_DIR ?= ./ground_truth
OUTPUT_DIR ?= ./output
MAX_ITERATIONS ?= 10000
RATIO_TRAIN ?= 0.90
TESSTRAIN_JOBS ?= 4
FAST_LIMIT ?= 5000
BATCH_SIZE ?= 2000

.PHONY: check setup import-archive prepare fast-subset batch batch-finalize batch-status batch-reset validate train train-fast train-batch export compare clean

check:
	./scripts/check_tools.sh

setup:
	./scripts/setup_training.sh

import-archive:
	python3 scripts/import_archive_xml.py --archive-dir ../archive --clear-output

fast-subset:
	python3 scripts/create_ground_truth_subset.py --source-dir ground_truth --output-dir ground_truth_fast --limit "$(FAST_LIMIT)" --clear-output

batch:
	python3 scripts/create_ground_truth_batch.py create --source-dir ground_truth --batch-dir ground_truth_batch --batch-size "$(BATCH_SIZE)"

batch-finalize:
	python3 scripts/create_ground_truth_batch.py finalize --source-dir ground_truth --batch-dir ground_truth_batch

batch-status:
	python3 scripts/create_ground_truth_batch.py status --source-dir ground_truth

batch-reset:
	python3 scripts/create_ground_truth_batch.py reset --source-dir ground_truth

prepare:
	python3 scripts/prepare_ground_truth.py

validate:
	python3 scripts/validate_ground_truth.py --ground-truth-dir ground_truth

train:
	MODEL_NAME="$(MODEL_NAME)" START_MODEL="$(START_MODEL)" TESSDATA="$(TESSDATA)" GROUND_TRUTH_DIR="$(GROUND_TRUTH_DIR)" OUTPUT_DIR="$(OUTPUT_DIR)" MAX_ITERATIONS="$(MAX_ITERATIONS)" RATIO_TRAIN="$(RATIO_TRAIN)" TESSTRAIN_JOBS="$(TESSTRAIN_JOBS)" ./scripts/train.sh

train-fast: fast-subset
	$(MAKE) train GROUND_TRUTH_DIR=./ground_truth_fast MAX_ITERATIONS=1500 TESSTRAIN_JOBS=8

train-batch: batch
	$(MAKE) train GROUND_TRUTH_DIR=./ground_truth_batch MAX_ITERATIONS=1500 TESSTRAIN_JOBS=8
	$(MAKE) batch-finalize

export:
	MODEL_NAME="$(MODEL_NAME)" ./scripts/export_model.sh

compare:
	./scripts/compare_ocr.sh

clean:
	rm -rf output/checkpoints output/khm_custom output/list.train output/list.eval output/*.lstm output/*.checkpoint
