#!/usr/bin/env python3
"""GPU-free TRELLIS dependency preflight used during Docker image build.

Model weights and GPU runtime are checked separately before any paid generation.
"""
import importlib
import os
import sys

os.environ.setdefault("ATTN_BACKEND", "xformers")
os.environ.setdefault("SPCONV_ALGO", "native")

MODULES = (
    "torch", "torchvision", "PIL", "numpy", "transformers",
    "huggingface_hub", "safetensors", "einops", "trimesh",
    "spconv.pytorch", "xformers.ops", "kaolin", "nvdiffrast.torch",
    "diffoctreerast", "diff_gaussian_rasterization", "utils3d",
    "trellis", "trellis.models", "trellis.pipelines",
    "trellis.utils.postprocessing_utils",
)
failed = []
for name in MODULES:
    try:
        importlib.import_module(name)
        print(f"PASS import {name}", flush=True)
    except Exception as exc:
        failed.append((name, f"{type(exc).__name__}: {exc}"))
        print(f"FAIL import {name}: {type(exc).__name__}: {exc}", flush=True)
try:
    from trellis.pipelines import TrellisImageTo3DPipeline
    assert callable(TrellisImageTo3DPipeline.from_pretrained)
    print("PASS TRELLIS pipeline entrypoint", flush=True)
except Exception as exc:
    failed.append(("TRELLIS pipeline", repr(exc)))
try:
    from trellis.utils import postprocessing_utils
    assert callable(postprocessing_utils.to_glb)
    print("PASS GLB export entrypoint", flush=True)
except Exception as exc:
    failed.append(("GLB export", repr(exc)))

# Optional: perform model metadata check on a CPU machine before renting GPU.
# Do not make an unreliable external network call mandatory during Docker build.
if os.getenv("TRELLIS_CHECK_HF") == "1":
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info("microsoft/TRELLIS-image-large")
        names = {file.rfilename for file in info.siblings}
        if not any(name.endswith(".safetensors") for name in names):
            raise RuntimeError("model repository has no safetensors checkpoints")
        print(f"PASS Hugging Face checkpoint metadata ({len(names)} files)", flush=True)
    except Exception as exc:
        failed.append(("Hugging Face model repository", repr(exc)))
else:
    print("SKIP remote model metadata (use TRELLIS_CHECK_HF=1 to enable)", flush=True)

if failed:
    print(f"PREFLIGHT FAILED: {len(failed)} check(s)", file=sys.stderr)
    for name, err in failed:
        print(f" - {name}: {err}", file=sys.stderr)
    sys.exit(1)
print("PREFLIGHT PASSED: CPU imports. GPU inference NOT yet verified.", flush=True)
