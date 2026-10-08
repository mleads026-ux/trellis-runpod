#!/usr/bin/env bash
set -euo pipefail
export HF_HOME=/workspace/cache/huggingface
export TORCH_HOME=/workspace/cache/torch
export SPCONV_ALGO=native
mkdir -p /workspace/cache /workspace/output
if [ ! -d /workspace/TRELLIS/.git ]; then
  git clone --recurse-submodules https://github.com/microsoft/TRELLIS.git /workspace/TRELLIS
fi
cd /workspace/TRELLIS
if [ ! -f /workspace/.trellis-installed ]; then
  if ! command -v conda >/dev/null 2>&1; then echo "Conda is required by the pinned TRELLIS setup"; exit 2; fi
  . ./setup.sh --new-env --basic --xformers --flash-attn --diffoctreerast --spconv --mipgaussian --kaolin --nvdiffrast
  touch /workspace/.trellis-installed
fi
echo "TRELLIS_READY"
nvidia-smi
