# TRELLIS output persistence

The current stopped RunPod Pod has no persistent volume. Files saved only on the Pod can disappear after Stop. Do not restart it merely to set up storage.

## Proposed export workflow

1. Configure an external storage destination with a verified total price within the user's $2 budget.
2. Generate a time-limited HTTPS upload URL on the storage provider, restricted to one output object. Never commit or paste the signed URL into GitHub.
3. After a future authorized GPU run produces a `.glb` model, upload it directly from the Pod to that HTTPS destination.
4. Download the uploaded file from external storage and verify its size and SHA-256 digest against the source before stopping the Pod.
5. Preserve the original input image, generated GLB, and metadata together when possible.

No storage provider is connected or verified yet. This plan does not claim that backup is already working. Do not enable automatic Stop until export and restoration have been verified.
