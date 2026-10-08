# TRELLIS output persistence — Cloudflare R2

R2 bucket `trellis-3d-outputs` is connected to the deployed Cloudflare Worker at `https://trellis-runpod-api.mleads026.workers.dev`. A GitHub Actions integration test has stored a small sample GLB through the authenticated Worker endpoint and retrieved it. The real TRELLIS generator has NOT been deployed or tested.

The current stopped RunPod Pod has no persistent volume. **Never rely on files only on the Pod. Never start GPU without owner approval. Never Terminate the Pod.**

## Save generated GLB (only during an explicitly approved future GPU run)

The file `scripts/save_trellis_output.py` uses only Python standard library. It uploads the generated GLB to the private R2 bucket through the authenticated Worker, downloads it, verifies exact size and SHA-256, and exits nonzero on any failure. It does NOT stop the Pod itself.

Supply the same API key used by Cloudflare Worker `ACTION_API_KEY` as the Pod's secret environment variable `TRELLIS_STORAGE_API_KEY` via RunPod's secure settings. Do not commit it, paste it into chat, or print it in logs. **Do not assume the Pod currently has this secret.**

Example once TRELLIS actually produces a model:

```bash
python3 scripts/save_trellis_output.py /path/to/generated-model.glb
```

The upload endpoint currently limits each GLB to 100 MiB. Larger outputs require a separate multipart/direct R2 upload design. A nonzero exit means backup is unverified and the Pod must not be stopped until the problem is fixed or the output is otherwise safely copied. Other required outputs (original image, metadata, etc.) are not automatically backed up by this script.

The repository currently contains no TRELLIS generator/handler. **This is an export helper, not automatic generation integration.** No GPU startup, auto-stop, or automatic model upload is enabled.
