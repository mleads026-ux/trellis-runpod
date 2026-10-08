# TRELLIS original (microsoft/TRELLIS) on NVIDIA RTX A5000

## Assessment (2026-10-08)

**Provisionally compatible for image-to-3D inference; not hardware-verified.**

- Official source: https://github.com/microsoft/TRELLIS
- Official prerequisite: Linux; NVIDIA GPU with **at least 16 GB VRAM**; tested by upstream on **A100 and A6000**, **not explicitly on A5000**.
- Selected GPU: NVIDIA RTX A5000, **24 GB VRAM**. It clears the stated 16 GB minimum by 8 GB, but this alone does not guarantee no CUDA OOM for every input or export.
- Upstream tested CUDA toolkit versions: **11.8 and 12.2**; default setup uses **PyTorch 2.4.0 with CUDA 11.8**.
- Upstream recommends Conda, Linux, and installation of compiled extensions. Compilation and model download may take substantial billable time on a fresh Pod.
- Do **not** confuse this with microsoft/TRELLIS.2 (different model and hardware requirements).

## Safe first test (only AFTER price, storage, and termination verification + user approval)

1. Prefer a prebuilt, trusted, compatible image or a prepared environment to avoid expensive on-GPU compilation; validate its provenance and exact dependency versions.
2. Use **one image-to-3D request at a time**; no concurrent jobs, no training, no batch generation.
3. Verify `nvidia-smi`, CUDA availability, GPU free memory, and model load; record peak allocated/reserved GPU memory during the test.
4. Test the official `example.py` image-conditioned path with a small sample, then verify mesh export usable in the game.
5. If OOM occurs, terminate the trial; do not automatically retry with more GPU resources.
6. Verify output format and game compatibility (mesh export, material/texture, coordinate scale, polygon budget) before integrating with the game.
7. Explicit user authorization required immediately before any paid resource creation.

## Safety blockers

- RunPod A5000 availability, live hourly price, storage prices and minimum volumes: **not verified**.
- TRELLIS v1 runtime and peak memory on this specific A5000: **not tested**.
- Independent native auto-termination + Cloudflare watchdog with real Pod ID: **not tested**.
- No GPU Pod created; no jobs submitted; paid operations remain locked.
