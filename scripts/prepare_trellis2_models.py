#!/usr/bin/env python3
"""Cache TRELLIS.2 and resolve every checkpoint, including cross-repository refs.

Downloads weights only when explicitly called. No CUDA or Pod lifecycle calls.
HF_TOKEN is used by huggingface_hub for gated DINOv3/RMBG model access.
"""
import json
import os
from pathlib import Path

MODEL_REPO = "microsoft/TRELLIS.2-4B"
REQUIRED_MODELS = {
    "sparse_structure_decoder", "sparse_structure_flow_model",
    "shape_slat_decoder", "shape_slat_flow_model_512", "shape_slat_flow_model_1024",
    "tex_slat_decoder", "tex_slat_flow_model_512", "tex_slat_flow_model_1024",
}


def resolve_config(config, model_dir, download):
    """Resolve paths without letting upstream mask loading errors as repo errors."""
    if config.get("name") != "Trellis2ImageTo3DPipeline":
        raise ValueError("Expected TRELLIS.2 pipeline, refusing a v1 checkpoint")
    config = json.loads(json.dumps(config))
    args = config["args"]
    if set(args["models"]) != REQUIRED_MODELS:
        raise ValueError("Incomplete TRELLIS.2 checkpoint mapping")
    for key, stem in args["models"].items():
        if stem.startswith("ckpts/"):
            local_stem = Path(model_dir) / stem
            for suffix in (".json", ".safetensors"):
                if not Path(str(local_stem) + suffix).is_file():
                    raise ValueError(f"Missing checkpoint: {stem}{suffix}")
        else:
            # e.g. microsoft/TRELLIS-image-large/ckpts/ss_dec_...
            parts = stem.split("/")
            if len(parts) < 4 or parts[2] != "ckpts" or ".." in parts:
                raise ValueError(f"Unexpected checkpoint reference: {stem}")
            repo, relative = "/".join(parts[:2]), "/".join(parts[2:])
            paths = [Path(download(repo_id=repo, filename=relative + suffix))
                     for suffix in (".json", ".safetensors")]
            local_stem = Path(str(paths[0])[:-5])
            if str(paths[1]) != str(local_stem) + ".safetensors":
                raise ValueError("Checkpoint files must resolve to the same snapshot")
        args["models"][key] = str(local_stem.resolve())
    args["low_vram"] = True
    return config


def prepare():
    from huggingface_hub import snapshot_download, hf_hub_download
    folder = Path(snapshot_download(repo_id=MODEL_REPO))
    config = resolve_config(json.loads((folder / "pipeline.json").read_text()),
                            folder, hf_hub_download)
    # Cache auxiliary models on CPU and make runtime references local too.
    from transformers import AutoModelForImageSegmentation, DINOv3ViTModel
    feature = config["args"]["image_cond_model"]["args"]
    model = DINOv3ViTModel.from_pretrained(feature["model_name"])
    del model
    background = config["args"]["rembg_model"]["args"]
    model = AutoModelForImageSegmentation.from_pretrained(
        background["model_name"], trust_remote_code=True)
    del model
    # Keep auxiliary identifiers: their HF cache is now populated.
    target = Path(os.environ.get("TRELLIS2_CONFIG_DIR", "/workspace/trellis2-cache/resolved"))
    target.mkdir(parents=True, exist_ok=True)
    destination = target / "pipeline.json"
    destination.write_text(json.dumps(config, indent=2))
    return destination.parent


if __name__ == "__main__":
    print(f"TRELLIS.2 cache prepared: {prepare()}", flush=True)
