"""Docker CPU dependency audit; GPU extensions are checked when a Pod boots."""
import importlib


def main():
    # flex_gemm/cumesh initialize Triton's active backend at import time. A Docker
    # build runner has no GPU, so importing them here fails even though their CUDA
    # extensions compiled successfully. gpu_preflight_trellis2 checks them at Pod boot.
    modules = ("torch", "torchvision", "xformers.ops", "transformers",
               "PIL", "numpy", "safetensors", "utils3d", "huggingface_hub")
    for name in modules:
        importlib.import_module(name)
        print(f"PASS import {name}", flush=True)
    import torch
    from transformers import DINOv3ViTModel
    assert torch.version.cuda == "12.4", torch.version.cuda
    assert callable(DINOv3ViTModel.from_pretrained)
    print("TRELLIS.2 CPU-SAFE IMPORTS PASS; GPU extensions are verified on Pod boot")


if __name__ == "__main__":
    main()
