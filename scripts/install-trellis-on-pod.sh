#!/usr/bin/env bash
set -euo pipefail
# Run INSIDE an NVIDIA/CUDA-enabled RunPod GPU Pod after checking the rental price.
# Not executed by Vercel, and does not start or rent GPUs.
command -v nvidia-smi >/dev/null || { echo "NVIDIA GPU not detected"; exit 1; }
command -v conda >/dev/null || { echo "Conda missing: choose a CUDA + Conda template"; exit 1; }
nvidia-smi
if [[ ! -d TRELLIS ]]; then
  git clone --recurse-submodules https://github.com/microsoft/TRELLIS.git
fi
cd TRELLIS
# Official Microsoft TRELLIS setup recipe; compilation/download can take a while.
. ./setup.sh --new-env --basic --xformers --flash-attn --diffoctreerast --spconv --mipgaussian --kaolin --nvdiffrast
echo "TRELLIS dependencies installed. Test with example.py after setting a sample image."
