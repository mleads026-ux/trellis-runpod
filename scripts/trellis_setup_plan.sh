#!/usr/bin/env bash
# TRELLIS original preparation only. DRY RUN by default.
# Never starts a Pod or a GPU. Running install mode consumes time on an ALREADY running Pod.
set -euo pipefail
MODE="${1:---dry-run}"
REPO_URL="https://github.com/microsoft/TRELLIS.git"
if [[ "$MODE" != "--dry-run" && "$MODE" != "--install" ]]; then
  echo "Usage: bash scripts/trellis_setup_plan.sh [--dry-run|--install]" >&2
  exit 2
fi
echo "TRELLIS original (microsoft/TRELLIS) setup"
echo "Target: Linux, NVIDIA RTX A5000 24GB, image-to-3D inference"
echo "Source: $REPO_URL"
echo "Upstream install guide: https://github.com/microsoft/TRELLIS#installation"
echo "Recommended: inspect and pin upstream commit, use supported CUDA/PyTorch/Conda environment."
if [[ "$MODE" == "--dry-run" ]]; then
  echo "DRY RUN: no network calls, no installs, no GPU actions."
  echo "On an approved running Pod only: check nvidia-smi, install system dependencies,"
  echo "clone pinned official repo, review setup.sh flags, install with official instructions,"
  echo "download approved model weights, test one image, verify mesh export, terminate Pod."
  exit 0
fi
if [[ "${TRELLIS_SETUP_APPROVED:-}" != "yes" ]]; then
  echo "BLOCKED: set TRELLIS_SETUP_APPROVED=yes only after user-approved paid Pod launch and cost controls." >&2
  exit 3
fi
if [[ ! -f /etc/os-release ]] || ! grep -qi linux /proc/sys/kernel/ostype 2>/dev/null; then
  echo "BLOCKED: Linux environment required" >&2
  exit 3
fi
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "BLOCKED: GPU not detected; refusing install mode." >&2
  exit 3
fi
echo "GPU detected. No automatic clone/install: official dependencies require reviewed pinned versions."
echo "Follow official README only after recording GPU price, storage fees and termination deadline."
