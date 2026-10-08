#!/usr/bin/env bash
# Run only INSIDE an already-approved, running GPU environment.
# This script never creates a Pod, downloads model weights, or installs packages.
set -euo pipefail
echo "TRELLIS v1 / RTX A5000 local preflight (read-only)"
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "ERROR: nvidia-smi unavailable; no GPU check possible" >&2
  exit 2
fi
nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader
python3 - <<'PY'
import importlib.util
import os
import subprocess
import sys
print("Python:",sys.version.split()[0])
spec=importlib.util.find_spec("torch")
if spec is None:
    print("PyTorch: NOT INSTALLED (no installation attempted)")
    sys.exit(0)
import torch
print("PyTorch:",torch.__version__)
print("CUDA runtime:",torch.version.cuda)
print("CUDA available:",torch.cuda.is_available())
if torch.cuda.is_available():
    props=torch.cuda.get_device_properties(0)
    print("GPU:",props.name)
    print("VRAM GiB:",round(props.total_memory/1024**3,2))
    if props.total_memory < 16*1024**3:
        print("FAIL: less than TRELLIS v1 minimum 16 GiB")
        sys.exit(3)
else:
    print("FAIL: PyTorch cannot see CUDA")
    sys.exit(3)
PY
echo "Preflight complete. No model loaded and no inference started."
