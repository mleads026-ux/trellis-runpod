#!/usr/bin/env python3
"""Fast, non-generating readiness check executed when the Pod container starts.

No model weights, inference, paid API calls or storage writes are performed.
"""
import importlib
import os

def check_gpu():
    issues = []
    info = {"ready": False, "issues": issues}
    try:
        import torch
        info["torch_version"] = str(torch.__version__)
        info["torch_cuda"] = str(torch.version.cuda)
        if not torch.cuda.is_available():
            issues.append("CUDA is not available inside the container; check RunPod GPU attachment and driver.")
            return info
        dev = torch.cuda.current_device()
        prop = torch.cuda.get_device_properties(dev)
        info["gpu"] = prop.name
        info["vram_gb"] = round(prop.total_memory / 1024**3, 1)
        info["compute_capability"] = f"{prop.major}.{prop.minor}"
        minimum = float(os.getenv("TRELLIS_MIN_VRAM_GB", "16"))
        if info["vram_gb"] < minimum:
            issues.append(f"VRAM {info['vram_gb']}GB < required {minimum}GB for original Microsoft TRELLIS.")
        if prop.major >= 12 and (torch.version.cuda or "").startswith("11."):
            issues.append("Blackwell GPU detected; CUDA 11.8/PyTorch 2.4 Docker image does not support sm120.")
        # Run a tiny kernel to detect 'no kernel image is available' before loading GBs of weights.
        try:
            result = (torch.ones(1, device="cuda") * 2).item()
            if result != 2:
                issues.append("CUDA kernel sanity check returned an unexpected result.")
        except Exception as exc:
            issues.append(f"CUDA kernel failed: {type(exc).__name__}: {str(exc)[:220]}")
        for name in ("spconv.pytorch", "xformers.ops", "kaolin", "nvdiffrast.torch",
                     "diffoctreerast", "diff_gaussian_rasterization",
                     "trellis.pipelines"):
            try:
                importlib.import_module(name)
            except Exception as exc:
                issues.append(f"Missing/broken {name}: {type(exc).__name__}: {str(exc)[:180]}")
    except Exception as exc:
        issues.append(f"GPU preflight could not run: {type(exc).__name__}: {str(exc)[:220]}")
    info["ready"] = not issues
    return info

if __name__ == "__main__":
    import json
    status = check_gpu()
    print(json.dumps(status, indent=2))
    raise SystemExit(0 if status["ready"] else 1)
