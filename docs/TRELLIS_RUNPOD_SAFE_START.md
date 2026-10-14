# TRELLIS / RunPod: safe image preparation (no paid GPU required)

## What this repository contains
- `Dockerfile`: builds the **original Microsoft TRELLIS** Python stack and compiled CUDA dependencies; does **not** run inside Secret Mission/Vercel.
- `scripts/trellis_api_server.py`: port 8000 HTTP upload/status API **for an active RunPod GPU Pod**.
- `api/runpod.js`: separate authenticated Vercel bridge for RunPod Pod inventory/control and **Serverless** status. This bridge does not automatically deploy the Docker image or route files into an ordinary Pod.
- `scripts/generate_trellis_and_backup.py`: image -> GLB -> required authenticated R2 upload/verification.
- No model checkpoint files are committed. TRELLIS fetches `microsoft/TRELLIS-image-large` from Hugging Face; they are large external model assets, not missing GitHub source files.

## Supported target of this Dockerfile
- Linux Docker GPU container; NVIDIA Ampere/Ada architecture (sm80, sm86, sm89).
- PyTorch 2.4.0 with CUDA 11.8; original upstream baseline.
- At least **16GB VRAM**, matching Microsoft's official minimum. The user's local RTX 5060 **8GB Blackwell** needs a distinct implementation/runtime and is **not supported by this image**.
- **Do not** point a RunPod Pod at an unrelated stock PyTorch image and expect it to include this repository's scripts.
- A Dockerfile committed to GitHub is **not automatically the RunPod container**. You must separately build/publish the image and select that exact image in the Pod template.

## No-GPU validation order (before any RunPod rental)
1. GitHub Actions `TRELLIS no-GPU preflight` runs `python -m unittest discover -s tests -v` (syntax/static checks only).
2. Build the Dockerfile on a non-GPU Docker builder (requires significant disk/memory): `docker build -t secret-mission-trellis:preflight .`
3. A **successful full Docker build** must include successful `pip check` and `preflight_trellis.py` imports. It does **not** prove GPU inference.
4. Confirm the published image digest and RunPod template image match. Do not start the Pod if it still uses an old image.
5. Confirm Hugging Face model reachability and sufficient image/model-cache disk. The image does not bundle model weights.
6. Only when ready, deliberately use a compatible >=16GB GPU (and budget/safe termination controls).

## First runtime check: before generation
In an actual GPU Pod, `GET http://<POD-ENDPOINT>:8000/health` returns:
- HTTP 200 + `status: ready` only when GPU dependency/kernel checks pass **and** `TRELLIS_STORAGE_API_KEY` is provided.
- HTTP 503 + `status: not_ready` and an `issues` list otherwise. **Do not submit generation**.
The container remains running for diagnostics; **an unhealthy Pod can still accumulate rental charges. Stop it promptly**.
This preflight checks GPU availability and imported libraries, but **not full inference, checkpoint download, or GLB export**.

## Runtime secrets (configure only in Pod / Vercel secret settings)
- In the GPU Pod: `TRELLIS_API_KEY` authenticates HTTP /generate and /jobs/{id}; `TRELLIS_STORAGE_API_KEY` authenticates backup to R2; optionally `TRELLIS_STORAGE_BASE_URL`.
- In Vercel bridge: `RUNPOD_API_KEY`, `ACTION_API_KEY` and the relevant Pod/Serverless IDs.
- Never commit API keys to GitHub or expose them in Vite client code.

## Failure interpretation
- `transformers requires PyTorch >=2.5 ... found 2.4.0`: likely a **different, unpinned live environment** from this image. The Dockerfile now pins Transformers 4.44.2.
- `ModuleNotFoundError: spconv`: CUDA-specific dependencies were skipped during a CPU-only Docker build; now explicitly installed.
- `CUDA not available` or `no kernel image`: Pod image / NVIDIA GPU or GPU architecture incompatible.
- `out of memory`: use a >=16GB GPU; do not mistake missing VRAM for missing files.
- `backup key missing` or upload error: storage configuration; generation is intentionally blocked/marked failed to protect outputs.

## Scope and verification honesty
This PR makes a *safer, reproducible configuration*, not a claim that the complete GPU image has been built or that real TRELLIS inference has passed. No paid RunPod machine was started. Do not merge/deploy until the full CPU Docker build passes and the correct GPU/Pod image is confirmed.
