#!/usr/bin/env python3
"""Read-only Hugging Face checkpoint audit. Downloads ONLY pipeline.json (~2 KB).

Do not download multi-GB weights, create Pods or run CUDA in this preflight.
"""
import json
import sys

REPO = "microsoft/TRELLIS-image-large"


def validate_manifest(config, filenames):
    if config.get("name") != "TrellisImageTo3DPipeline":
        raise ValueError("Unexpected pipeline type")
    args = config.get("args", {})
    models = args.get("models", {})
    required_keys = {
        "sparse_structure_decoder", "sparse_structure_flow_model",
        "slat_decoder_gs", "slat_decoder_rf", "slat_decoder_mesh",
        "slat_flow_model",
    }
    if set(models) != required_keys:
        raise ValueError(f"Checkpoint mappings differ: {set(models) ^ required_keys}")
    if not args.get("image_cond_model", "").startswith("dinov2_"):
        raise ValueError("Missing or unexpected DINOv2 conditioning model")
    missing = []
    for stem in models.values():
        if not isinstance(stem, str) or not stem.startswith("ckpts/"):
            raise ValueError(f"Unexpected model checkpoint path: {stem!r}")
        for suffix in (".json", ".safetensors"):
            filename = stem + suffix
            if filename not in filenames:
                missing.append(filename)
    if missing:
        raise ValueError("Missing Hugging Face checkpoints: " + ", ".join(missing))
    return models


def main():
    from huggingface_hub import HfApi, hf_hub_download
    info = HfApi().model_info(REPO, files_metadata=True)
    entries = {item.rfilename: item for item in info.siblings}
    if "pipeline.json" not in entries:
        raise ValueError("pipeline.json missing from model repository")
    config_file = hf_hub_download(repo_id=REPO, filename="pipeline.json")
    with open(config_file, encoding="utf-8") as f:
        config = json.load(f)
    models = validate_manifest(config, set(entries))
    # File sizes are metadata. No weight or model objects are downloaded.
    sized = [int(e.size) for e in entries.values()
             if e.rfilename.endswith(".safetensors") and e.size is not None]
    if any(size <= 0 for size in sized):
        raise ValueError("Zero-length checkpoint in model metadata")
    print(f"MODEL MANIFEST PASS: {len(models)} checkpoint pairs, "
          f"DINOv2={config['args']['image_cond_model']}, "
          f"total listed safetensors={sum(sized)/1024**3:.2f} GiB")
    print("NOT TESTED: actual weight download, DINOv2/U2Net binaries, CUDA inference, GLB baking.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"MODEL MANIFEST FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
