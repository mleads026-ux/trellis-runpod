#!/usr/bin/env python3
"""Generate a TRELLIS.2 PBR GLB and verify the existing private R2 backup."""
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
    parser.add_argument("--texture-size", type=int,
                        default=int(os.getenv("TRELLIS2_TEXTURE_SIZE", "2048")),
                        choices=(1024, 2048, 4096))
    parser.add_argument("--pipeline-type", default=os.getenv("TRELLIS2_PIPELINE_TYPE", "1024_cascade"),
                        choices=("512", "1024", "1024_cascade", "1536_cascade"))
    parser.add_argument("--target-faces", type=int, default=500000)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error("Input image not found")
    if args.output.suffix.lower() != ".glb":
        parser.error("Output must end in .glb")
    if not 10000 <= args.target_faces <= 1000000:
        parser.error("--target-faces must be between 10000 and 1000000")
    if not os.getenv("TRELLIS_STORAGE_API_KEY"):
        parser.error("TRELLIS_STORAGE_API_KEY missing: refuse to generate without backup destination")
    os.environ.setdefault("ATTN_BACKEND", "xformers")
    os.environ.setdefault("SPARSE_ATTN_BACKEND", "xformers")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
    from gpu_preflight_trellis2 import check_gpu
    status = check_gpu()
    if not status["ready"]:
        parser.error("TRELLIS.2 GPU preflight failed: " + "; ".join(status["issues"]))
    from PIL import Image
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    import o_voxel
    from prepare_trellis2_models import prepare
    config_dir = prepare()
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained(str(config_dir))
    pipeline.low_vram = True
    pipeline.cuda()
    with Image.open(args.image) as img:
        image = img.convert("RGBA")
    mesh = pipeline.run(image, seed=args.seed, pipeline_type=args.pipeline_type)[0]
    mesh.simplify(16777216)  # Official nvdiffrast face-index limit.
    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices, faces=mesh.faces,
        attr_volume=mesh.attrs, coords=mesh.coords, attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=args.target_faces, texture_size=args.texture_size,
        remesh=True, remesh_band=1, remesh_project=0, verbose=True,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Standard PNG textures for Blender/Unity compatibility.
    glb.export(str(args.output))
    if not args.output.is_file() or args.output.stat().st_size < 20:
        raise RuntimeError("No valid GLB exported")
    subprocess.run([sys.executable, str(Path(__file__).with_name("save_trellis_output.py")),
                    str(args.output)], check=True)
    print("TRELLIS2_GENERATION_AND_BACKUP_VERIFIED", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"GENERATION_OR_BACKUP_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
