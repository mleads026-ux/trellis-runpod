#!/usr/bin/env python3
"""Read-only TRELLIS host preflight. No downloads, GPU startup, or writes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def probe():
    info = {
        "python": sys.version.split()[0],
        "linux": sys.platform.startswith("linux"),
        "cuda_toolkit_nvcc": shutil.which("nvcc") is not None,
        "nvidia_smi": shutil.which("nvidia-smi") is not None,
        "trellis_importable": importlib.util.find_spec("trellis") is not None,
        "torch_importable": importlib.util.find_spec("torch") is not None,
        "pillow_importable": importlib.util.find_spec("PIL") is not None,
        "storage_secret_present": bool(os.environ.get("TRELLIS_STORAGE_API_KEY")),
        "free_disk_gib": round(shutil.disk_usage(Path.cwd()).free / 1024**3, 2),
    }
    if info["nvidia_smi"]:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=8, check=True,
            )
            info["gpus"] = []
            for line in result.stdout.splitlines():
                name, memory = line.rsplit(",", 1)
                info["gpus"].append({"name": name.strip(), "vram_mib": int(memory.strip())})
        except (subprocess.SubprocessError, ValueError):
            info["gpus"] = []
    else:
        info["gpus"] = []
    info["gpu_minimum_16gib"] = any(g["vram_mib"] >= 16384 for g in info["gpus"])
    info["ready_for_install_review"] = all([
        info["linux"], info["cuda_toolkit_nvcc"], info["gpu_minimum_16gib"],
        info["storage_secret_present"],
    ])
    return info


if __name__ == "__main__":
    result = probe()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["ready_for_install_review"]:
        print("PREFLIGHT_INCOMPLETE: no installation or generation performed", file=sys.stderr)
        sys.exit(2)
