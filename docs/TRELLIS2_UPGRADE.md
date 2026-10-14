# TRELLIS.2 RunPod configuration

This is a separate CUDA 12.4 / PyTorch 2.6 image. The original CUDA 11.8 image and
its tags are preserved. Build `Dockerfile.trellis2`, not `Dockerfile`.

The GitHub workflow publishes `ghcr.io/mleads026-ux/trellis-runpod:trellis2-cu124-<commit>`
only after offline tests, Docker build, `pip check`, and CPU import checks succeed.
Use the exact published commit tag in the RunPod template; do not use an unbuilt tag.

## Runtime settings

- NVIDIA Ampere/Ada/Hopper with nominal **24GB VRAM or more**. Blackwell is not
  supported by this image. High resolutions and complex hair may require more VRAM.
- HTTP port: `8000`; default container command already starts the API.
- Keep existing `TRELLIS_API_KEY`, `TRELLIS_STORAGE_API_KEY`, and storage URL settings.
- `TRELLIS_BACKEND=trellis2` is already set in the image.
- Default generation: `1024_cascade`, low-VRAM mode, 2048px PNG PBR textures,
  500,000 target faces. Optional `TRELLIS2_PIPELINE_TYPE=512` for a lighter first
  runtime test; `TRELLIS2_TEXTURE_SIZE=4096` for higher texture resolution.
- Mount persistent `/workspace` storage or retain the existing verified R2 backup
  process. Do not stop/recreate a Pod with unbacked-up files.
- Model/auxiliary cache: `/workspace/trellis2-cache`. Large weights are not baked
  into the image; the first preparation needs network access and several GB.

## Hugging Face model access

The official pipeline uses `microsoft/TRELLIS.2-4B`, an external structure decoder
from `microsoft/TRELLIS-image-large`, `facebook/dinov3-vitl16-pretrain-lvd1689m`, and
`briaai/RMBG-2.0`. DINOv3 and RMBG may require accepting their model terms and a
read-only `HF_TOKEN` for the authorized account. Supply it as a **RunPod secret**,
never in code, GitHub files, or logs. Their licenses are separate from TRELLIS.2's.

Optional CPU preparation (inside the new environment, no GPU calls):

```bash
python /opt/trellis-runpod/scripts/prepare_trellis2_models.py
```

Preparation resolves cross-repository checkpoint paths before loading and preserves
the official auxiliary models. A v1 checkpoint is rejected. No fallback generates
a substitute model or reports a broken download as success.

## Validate before claiming deployment complete

1. Confirm image tag/digest in RunPod and backup all existing artifacts before changing it.
2. `GET /health` must identify `backend=trellis2`, `model=microsoft/TRELLIS.2-4B`.
   Health checks CUDA, imports and backup access; `model_loaded=false` explicitly
   means it has not proven weight loading or inference.
3. Use the existing authenticated `POST /generate` PNG/JPEG endpoint and poll
   `GET /jobs/<id>`. Completion requires a valid GLB and verified R2 roundtrip.
4. Inspect the actual GLB in Blender from front/side/back. A successful build does
   not establish better face quality, animation readiness, or an automatic rig.

No workflow in this upgrade creates, starts, stops, or terminates a paid Pod.
