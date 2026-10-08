#!/usr/bin/env python3
"""Upload and verify a generated TRELLIS GLB before allowing the Pod to stop.

Usage:
  TRELLIS_STORAGE_API_KEY=<secret> python3 scripts/save_trellis_output.py /path/to/model.glb
Optional: TRELLIS_STORAGE_BASE_URL=https://trellis-runpod-api.mleads026.workers.dev
Requires only Python standard library. Never print the secret.
"""
import hashlib
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("TRELLIS_STORAGE_BASE_URL", "https://trellis-runpod-api.mleads026.workers.dev").rstrip("/")
LIMIT = 100 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if len(sys.argv) != 2:
        raise ValueError("Expected one .glb file path")
    source = pathlib.Path(sys.argv[1])
    if not source.is_file() or source.suffix.lower() != ".glb":
        raise ValueError("A real .glb file is required")
    if source.stat().st_size == 0 or source.stat().st_size > LIMIT:
        raise ValueError("File must be 1 to 100 MiB")
    secret = os.environ.get("TRELLIS_STORAGE_API_KEY")
    if not secret:
        raise ValueError("TRELLIS_STORAGE_API_KEY is missing; do not stop the Pod")
    data = source.read_bytes()
    # Random unique name, avoiding overwrites and collision with earlier outputs.
    import secrets
    stem = re.sub(r"[^a-zA-Z0-9_-]", "-", source.stem)[:55].strip("-") or "model"
    name = f"{stem}-{secrets.token_hex(8)}.glb"
    url = BASE + "/api/models/" + name
    headers = {"Authorization": "Bearer " + secret}
    put = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "model/gltf-binary"}, method="PUT")
    with urllib.request.urlopen(put, timeout=120) as response:
        if response.status != 201:
            raise RuntimeError("Upload not confirmed")
    get = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(get, timeout=120) as response:
        remote = response.read(LIMIT + 1)
    if len(remote) != len(data) or digest(remote) != digest(data):
        raise RuntimeError("Remote GLB checksum mismatch; do not stop the Pod")
    print(f"VERIFIED_R2_BACKUP models/{name} size={len(data)} sha256={digest(data)}")
    print("Pod may now be stopped manually, after any other required outputs are backed up.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, urllib.error.URLError) as exc:
        print(f"BACKUP_FAILED: {type(exc).__name__}; do not stop the Pod", file=sys.stderr)
        sys.exit(1)
