# TRELLIS v1 first run — RTX A5000 — MANUAL ONLY

**Do not execute until a live Pod is explicitly approved, a separate termination guard is armed and verified, and a complete cost estimate is accepted.** These commands are reference material, not an automated deployment.

Official upstream: https://github.com/microsoft/TRELLIS

## Important findings
- Upstream states NVIDIA >=16GB VRAM; A5000 24GB qualifies by capacity, but has not been validated by us.
- Official tested CUDA versions: 11.8 and 12.2; default upstream setup uses PyTorch 2.4.0 / CUDA 11.8.
- RunPod's PyTorch **2.8.0** template is **not** the upstream default; do not assume binary extensions compile correctly against it.
- A **30GB container disk is not confirmed sufficient** for Conda, CUDA, source builds, model weights and outputs. Determine actual free space and required disk BEFORE deployment; a larger disk increases storage cost.
- The first build and model download may exceed 15 minutes. A 15-minute trial is **not** a realistic guaranteed end-to-end window.
- No persistent volume was selected in the quote; terminating a Pod can erase local outputs. Export GLB off-Pod before termination.

## Commands to review for an ALREADY authorized and protected GPU Pod
```bash
# Read-only checks first:
nvidia-smi
df -h
python --version
nvcc --version || true
python -c 'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())'

# Upstream installation (BILLABLE time on a running Pod; do NOT execute yet):
git clone --recurse-submodules https://github.com/microsoft/TRELLIS.git
cd TRELLIS
# Review upstream setup.sh and pin a known commit before executing.
# Requires a compatible Conda/CUDA environment.
. ./setup.sh --new-env --basic --xformers --flash-attn --diffoctreerast --spconv --mipgaussian --kaolin --nvdiffrast

# Upstream image-to-3D smoke test, after successful setup:
python example.py
# Verify sample.glb and copy it off the Pod before terminating.
```

## Launch gate (ALL must pass)
1. GPU and container disk prices, exact disk sizes, availability, any minimums and storage after termination confirmed.
2. Exact compatible base image and required CUDA compiler validated.
3. Independent RunPod-native auto-termination or other verified fallback **plus** armed Cloudflare watchdog for exact Pod, with UTC deadline and alerts.
4. Separate termination test and failure-mode checks; no automatic 'deploy when available'.
5. User approves actual quote and realistic session duration. Total budget target $2 is **not a provider-enforced hard cap**.
6. Terminate and verify Pod absence; remove unwanted persistent storage and verify charges.

**Status:** This document is safe to read; nothing has been installed, deployed, downloaded or billed by writing it.
