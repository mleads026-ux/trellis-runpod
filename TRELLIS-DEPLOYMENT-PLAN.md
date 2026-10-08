# TRELLIS original-model deployment plan (no GPU started)

**Status:** The official Microsoft TRELLIS image-to-3D Python pipeline is wired to verified R2 backup in `scripts/generate_trellis_and_backup.py`, but TRELLIS itself has not been installed or executed on RunPod. This is not yet a working end-user service.

## Prerequisites to confirm before paid runtime

- Explicit owner approval for **Start**, including a maximum spend and stopping deadline. **Never Terminate**.
- Confirm the stopped Pod still exists, its hourly GPU rate, storage costs, image, CUDA toolkit, disk space and network. The prior Pod has no persistent volume; installed packages and generated files cannot be assumed to survive a Stop.
- Confirm the selected GPU has at least 16 GB VRAM. The original TRELLIS README reports verified A100/A6000 and Linux/CUDA 11.8/12.2; RTX A5000 compatibility is not guaranteed.
- Install from official `https://github.com/microsoft/TRELLIS` with submodules, then use the official setup script and an appropriate CUDA environment. Dependencies and model weights can be large; installation time is **not** known and may exceed the $2 total budget. Do not start until this risk is accepted.
- Inject `TRELLIS_STORAGE_API_KEY` securely, matching Cloudflare Worker's `ACTION_API_KEY`. Never log or commit it. Confirm the R2 object size limit of 100 MiB is sufficient for real outputs.
- Arrange an independent manual Stop fallback. Automatic Stop is **not** armed. The export helper does not stop the Pod.

## Intended invocation only after prerequisites and approval

From a Python environment with original TRELLIS installed, with an input image available:

```bash
python3 scripts/generate_trellis_and_backup.py --image /path/to/input.png --output /path/to/output.glb
```

A successful command means GLB export **and** byte-for-byte download verification succeeded. On failure, do not Stop until files are backed up another way. The input image, weights, and metadata are not backed up automatically.

## Free offline checks

GitHub Actions workflow: `.github/workflows/check-trellis-pipeline.yml` validates Python syntax and six fail-closed cases without GPU, cloud secrets, or model downloads. These tests are not a substitute for real GPU integration testing.
