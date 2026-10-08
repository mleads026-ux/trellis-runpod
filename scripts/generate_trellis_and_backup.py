#!/usr/bin/env python3
"""Run original Microsoft TRELLIS image-to-3D and verify private R2 backup.

Requires TRELLIS installed separately in this Python environment and a compatible GPU.
Does not start, stop, create, or terminate RunPod resources.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--texture-size", type=int, default=1024)
    parser.add_argument("--simplify", type=float, default=0.95)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error("Input image not found")
    if args.output.suffix.lower() != ".glb":
        parser.error("Output must end in .glb")
    if not 0 <= args.simplify <= 1:
        parser.error("--simplify must be between 0 and 1")
    if args.texture_size not in (256, 512, 1024, 2048):
        parser.error("Unsupported --texture-size")
    if not os.environ.get("TRELLIS_STORAGE_API_KEY"):
        parser.error("TRELLIS_STORAGE_API_KEY missing: refuse to generate without backup destination")
    try:
        import torch
        from PIL import Image
        from trellis.pipelines import TrellisImageTo3DPipeline
        from trellis.utils import postprocessing_utils
    except ImportError as exc:
        parser.error(f"Original Microsoft TRELLIS dependencies not installed: {exc}")
    if not torch.cuda.is_available():
        parser.error("CUDA unavailable; do not attempt generation on CPU")
    os.environ.setdefault("SPCONV_ALGO", "native")
    print("Loading Microsoft TRELLIS-image-large...", flush=True)
    pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
    pipeline.cuda()
    with Image.open(args.image) as img:
        image = img.convert("RGBA")
    outputs = pipeline.run(image, seed=args.seed)
    glb = postprocessing_utils.to_glb(
        outputs["gaussian"][0], outputs["mesh"][0],
        simplify=args.simplify, texture_size=args.texture_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    glb.export(str(args.output))
    if not args.output.is_file() or args.output.stat().st_size == 0:
        raise RuntimeError("No valid output file exported")
    helper = Path(__file__).resolve().parent / "save_trellis_output.py"
    print("Verifying remote R2 copy before reporting success...", flush=True)
    subprocess.run([sys.executable, str(helper), str(args.output)], check=True)
    print("TRELLIS_GENERATION_AND_BACKUP_VERIFIED", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"GENERATION_OR_BACKUP_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
