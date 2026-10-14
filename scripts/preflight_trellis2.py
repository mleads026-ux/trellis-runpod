"""Docker CPU dependency audit; does not download weights or claim GPU readiness."""
import importlib


def main():
    from gpu_preflight_trellis2 import MODULES
    for name in (*MODULES, "transformers", "PIL", "safetensors", "utils3d"):
        importlib.import_module(name)
        print(f"PASS import {name}", flush=True)
    import torch
    from transformers import DINOv3ViTModel
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    from o_voxel.postprocess import to_glb
    assert torch.version.cuda == "12.4", torch.version.cuda
    assert callable(Trellis2ImageTo3DPipeline.from_pretrained)
    assert callable(to_glb)
    print("TRELLIS.2 CPU IMPORTS PASS; GPU kernels, gated model access and generation NOT tested")


if __name__ == "__main__":
    main()
