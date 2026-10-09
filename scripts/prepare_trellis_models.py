#!/usr/bin/env python3
"""Prepare Microsoft TRELLIS image-to-3D model caches without needing a GPU.

Run this with persistent /workspace storage BEFORE any paid GPU generation.
Downloads model weights; expect several gigabytes of disk usage. No CUDA calls.
This is intentionally not part of the Docker build.
"""
import json
import os
from pathlib import Path

CACHE = Path(os.environ.get("TRELLIS_CACHE_DIR", "/workspace/trellis-cache"))
os.environ.setdefault("HF_HOME", str(CACHE / "huggingface"))
os.environ.setdefault("TORCH_HOME", str(CACHE / "torch"))
os.environ.setdefault("U2NET_HOME", str(CACHE / "u2net"))
os.environ.setdefault("ATTN_BACKEND", "xformers")
os.environ.setdefault("SPCONV_ALGO", "native")

def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download
    print("STEP 1/3: caching Microsoft TRELLIS model checkpoints...", flush=True)
    folder = Path(snapshot_download(repo_id="microsoft/TRELLIS-image-large"))
    pipeline_file = folder / "pipeline.json"
    with pipeline_file.open(encoding="utf-8") as fh:
        config = json.load(fh)
    backbone = config["args"]["image_cond_model"]
    print(f"PASS TRELLIS checkpoint snapshot: {folder}", flush=True)

    # Microsoft TRELLIS calls this torch.hub backbone in its image pipeline.
    # Fetch it on CPU to avoid waiting for downloads after renting a GPU.
    print(f"STEP 2/3: caching DINOv2 backbone {backbone}...", flush=True)
    import torch
    model = torch.hub.load("facebookresearch/dinov2", backbone, pretrained=True, trust_repo=True)
    del model
    print("PASS DINOv2 backbone cached", flush=True)

    # TRELLIS image preprocessing creates rembg's U2Net session for opaque images.
    print("STEP 3/3: caching rembg U2Net background-removal model...", flush=True)
    import rembg
    session = rembg.new_session("u2net")
    del session
    print("PASS rembg U2Net cached", flush=True)
    print(f"MODEL CACHE READY: {CACHE}. Use the SAME persistent storage for generation.", flush=True)

if __name__ == "__main__":
    main()
