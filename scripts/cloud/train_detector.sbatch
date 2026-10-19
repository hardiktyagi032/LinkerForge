#!/usr/bin/env bash
# Template only: adapt partition, GPU, time, environment and paths to the college cluster.
# This file has not been submitted or validated on the target Slurm image.
#SBATCH --job-name=linkerforge-detector
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=linkerforge-detector-%j.log

set -euo pipefail

: "${LINKERFORGE_REPO:?Set an absolute checkout path}"
: "${LINKERFORGE_TRAIN_URL:?Set immutable curated reference train JSONL URL/path}"
: "${LINKERFORGE_VALIDATION_URL:?Set immutable curated reference validation JSONL URL/path}"
: "${LINKERFORGE_RUN_DIR:?Set a writable run directory outside Git}"

cd "$LINKERFORGE_REPO"
export PYTHONPATH="$LINKERFORGE_REPO/src"

python -c 'import torch; assert torch.cuda.is_available(), "CUDA unavailable"; print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))'
python scripts/run_training_suite.py \
  --detector-train "$LINKERFORGE_TRAIN_URL" \
  --detector-validation "$LINKERFORGE_VALIDATION_URL" \
  --output-dir "$LINKERFORGE_RUN_DIR" \
  --epochs 10 --batch-size 16
