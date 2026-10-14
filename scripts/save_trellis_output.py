#!/usr/bin/env python3
"""Upload and verify a generated TRELLIS GLB before allowing the Pod to stop.

Usage:
  TRELLIS_STORAGE_API_KEY=<secret> python3 scripts/save_trellis_output.py /path/to/model.glb
Optional: TRELLIS_STORAGE_BASE_URL=https://trellis-runpod-api.mleads026.workers.dev
Requires only Python standard library. Never print the secret.
"""
import hashlib
import json
import os
import struct
import pathlib
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("TRELLIS_STORAGE_BASE_URL", "https://trellis-runpod-api.mleads026.workers.dev").rstrip("/")
LIMIT = 100 * 1024 * 1024
# Cloudflare Browser Integrity Check can reject Python-urllib default (1010).
USER_AGENT = "TRELLIS-RunPod-Backup/1.0 (+https://github.com/mleads026-ux/trellis-runpod)"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_glb_bytes(data):
    """Validate GLB 2.0 header and JSON chunk before any cloud upload."""
    if len(data) < 20:
        raise ValueError("GLB header is incomplete")
    magic, version, declared_length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or declared_length != len(data):
        raise ValueError("Invalid GLB magic, version or declared file length")
    chunk_len, chunk_type = struct.unpack_from("<I4s", data, 12)
    if chunk_type != b"JSON" or chunk_len < 4 or chunk_len % 4 or 20 + chunk_len > len(data):
        raise ValueError("Invalid GLB JSON chunk")
    try:
        config = json.loads(data[20:20 + chunk_len].decode("utf-8").rstrip(" "))
        if config.get("asset", {}).get("version") != "2.0":
            raise ValueError("GLB asset.version must be 2.0")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f"Invalid GLB JSON: {exc}") from exc
    cursor = 20 + chunk_len
    if cursor < len(data):
        if cursor + 8 > len(data):
            raise ValueError("Incomplete GLB binary chunk header")
        binary_len, binary_type = struct.unpack_from("<I4s", data, cursor)
        if binary_type != bytes([66, 73, 78, 0]) or binary_len % 4 or cursor + 8 + binary_len != len(data):
            raise ValueError("Invalid GLB binary chunk")
    return True


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
    validate_glb_bytes(data)
    # Random unique name, avoiding overwrites and collision with earlier outputs.
    import secrets
    stem = re.sub(r"[^a-zA-Z0-9_-]", "-", source.stem)[:55].strip("-") or "model"
    name = f"{stem}-{secrets.token_hex(8)}.glb"
    url = BASE + "/api/models/" + name
    headers = {"Authorization": "Bearer " + secret, "User-Agent": USER_AGENT}
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
    except urllib.error.HTTPError as exc:
        hints = {401: "backup key rejected: verify Pod TRELLIS_STORAGE_API_KEY matches Worker ACTION_API_KEY",
                 403: "Cloudflare access denied: check User-Agent / error code 1010",
                 413: "upload too large: 100 MiB maximum"}
        print(f"BACKUP_FAILED: HTTP {exc.code}; {hints.get(exc.code, 'inspect Cloudflare upload service')}; do not stop the Pod", file=sys.stderr)
        sys.exit(1)
    except (ValueError, RuntimeError, OSError, urllib.error.URLError) as exc:
        print(f"BACKUP_FAILED: {type(exc).__name__}: {str(exc)[:180] if isinstance(exc, ValueError) else 'check storage and network'}; do not stop the Pod", file=sys.stderr)
        sys.exit(1)
