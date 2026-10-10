#!/usr/bin/env python3
"""GPU-free dependency audit of Microsoft's TRELLIS image -> GLB path.

This deliberately checks installed libraries without downloading weights or running
CUDA kernels. Those checks must happen separately before paid GPU inference.
"""
import importlib
import os
import sys

os.environ.setdefault("ATTN_BACKEND", "xformers")
os.environ.setdefault("SPCONV_ALGO", "native")

# Cover the *actual* inference and GLB post-processing path, not just torch.
MODULES = (
    "torch", "torchvision", "PIL", "numpy", "transformers",
    "huggingface_hub", "safetensors", "einops", "imageio",
    "rembg", "onnxruntime", "cv2", "scipy", "trimesh", "open3d",
    "pyvista", "pymeshfix", "xatlas", "igraph",
    "spconv.pytorch", "xformers.ops", "kaolin", "nvdiffrast.torch",
    "diffoctreerast", "diff_gaussian_rasterization",
    "utils3d", "utils3d.torch", "utils3d.io",
    "trellis", "trellis.models", "trellis.pipelines",
    "trellis.renderers", "trellis.representations",
    "trellis.utils.render_utils", "trellis.utils.postprocessing_utils",
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
    import torch
    from trellis.pipelines import TrellisImageTo3DPipeline
    from trellis.utils import postprocessing_utils
    assert callable(TrellisImageTo3DPipeline.from_pretrained)
    assert callable(postprocessing_utils.to_glb)
    assert torch.version.cuda == "11.8", f"Unexpected torch CUDA: {torch.version.cuda}"
    print("PASS official TRELLIS pipeline / GLB API and pinned CUDA ABI", flush=True)
except Exception as exc:
    failed.append(("TRELLIS pipeline / GLB / CUDA ABI", repr(exc)))

# Remote model metadata is opt-in; never make a network request mandatory in
# Docker build. Runtime weights (TRELLIS, DINOv2 and U2Net) are separate.
if os.getenv("TRELLIS_CHECK_HF") == "1":
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info("microsoft/TRELLIS-image-large")
        names = {f.rfilename for f in info.siblings}
        assert "pipeline.json" in names, "model pipeline.json missing"
        assert any(n.endswith(".safetensors") for n in names), "checkpoints missing"
        print(f"PASS HF model metadata ({len(names)} files)", flush=True)
    except Exception as exc:
        failed.append(("HF model metadata", repr(exc)))
else:
    print("SKIP model downloads and online metadata (TRELLIS_CHECK_HF=1)", flush=True)

if failed:
    print(f"PREFLIGHT FAILED: {len(failed)} check(s)", file=sys.stderr)
    for name, err in failed:
        print(f" - {name}: {err}", file=sys.stderr)
    sys.exit(1)

print("PREFLIGHT PASSED: CPU imports. GPU kernels, cached model weights and generation NOT verified.", flush=True)
