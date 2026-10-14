"""Check TRELLIS.2 runtime without downloading weights or generating a model."""
import importlib

MODULES = ("xformers.ops", "flex_gemm", "cumesh", "o_voxel",
           "nvdiffrast.torch", "trellis2.pipelines")


def check_gpu():
    issues = []
    info = {"ready": False, "issues": issues, "model": "microsoft/TRELLIS.2-4B"}
    try:
        import torch
        info.update(torch_version=str(torch.__version__), torch_cuda=str(torch.version.cuda))
        if not torch.cuda.is_available():
            issues.append("CUDA unavailable")
            return info
        prop = torch.cuda.get_device_properties(torch.cuda.current_device())
        info.update(gpu=prop.name, vram_gb=round(prop.total_memory / 1024**3, 1),
                    compute_capability=f"{prop.major}.{prop.minor}")
        # Nominal 24GB devices can expose slightly less usable memory.
        if prop.total_memory < 23 * 1024**3:
            issues.append("TRELLIS.2 requires a nominal 24GB or larger GPU")
        if prop.major not in (8, 9):
            issues.append("This CUDA 12.4 image supports Ampere/Ada/Hopper sm80-sm90 only")
        if torch.version.cuda != "12.4":
            issues.append("Expected PyTorch CUDA 12.4 ABI")
        if (torch.ones(1, device="cuda") * 2).item() != 2:
            issues.append("CUDA kernel sanity check failed")
        for name in MODULES:
            try:
                importlib.import_module(name)
            except Exception as exc:
                issues.append(f"Broken {name}: {type(exc).__name__}: {str(exc)[:180]}")
    except Exception as exc:
        issues.append(f"GPU check failed: {type(exc).__name__}: {str(exc)[:220]}")
    info["ready"] = not issues
    return info
