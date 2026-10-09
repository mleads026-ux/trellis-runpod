#!/usr/bin/env python3
"""CPU-only TRELLIS image preflight. Run in Docker build; no GPU or token required."""
import importlib
import os
import pathlib
import sys
import traceback

os.environ.setdefault("ATTN_BACKEND", "xformers")
os.environ.setdefault("SPCONV_ALGO", "native")
os.environ.setdefault("PYTHONPATH", "/opt/TRELLIS")

MODULES = [
    "torch", "torchvision", "PIL", "numpy", "transformers",
    "huggingface_hub", "safetensors", "einops", "trimesh",
    "xformers.ops", "kaolin", "nvdiffrast.torch",
    "diffoctreerast", "diff_gaussian_rasterization",
    "trellis", "trellis.models", "trellis.pipelines",
    "trellis.utils.postprocessing_utils",
]
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
try:
    from huggingface_hub import HfApi
    info = HfApi().model_info("microsoft/TRELLIS-image-large")
    paths = [f.rfilename for f in info.siblings]
    if not paths:
        raise RuntimeError("model repository contains no files")
    print(f"PASS model repository metadata ({len(paths)} files)", flush=True)
except Exception as exc:
    failed.append(("Hugging Face model repository access", repr(exc)))
if failed:
    print(f"PREFLIGHT FAILED: {len(failed)} check(s)", file=sys.stderr)
    for name, err in failed:
        print(f" - {name}: {err}", file=sys.stderr)
    sys.exit(1)
print("PREFLIGHT PASSED: CPU dependencies and model metadata. CUDA runtime/inference still require GPU.", flush=True)
