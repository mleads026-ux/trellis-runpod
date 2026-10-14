#!/usr/bin/env python3
"""Real no-GPU R2 round-trip preflight before TRELLIS accepts any image jobs.

Writes a minimal GLB 2.0 file to a temporary directory, then invokes the
same uploader used by actual TRELLIS generations, requiring both upload and
SHA-256-verified download. Never prints or writes credentials.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

UPLOADER = Path(__file__).resolve().with_name("save_trellis_output.py")


def create_glb():
    payload = b'{"asset":{"version":"2.0"}}'
    payload += b" " * (-len(payload) % 4)
    return struct.pack("<4sII", b"glTF", 2, 20 + len(payload)) + struct.pack(
        "<I4s", len(payload), b"JSON"
    ) + payload


def verify_backup():
    """Return a non-secret status dictionary, and fail closed on all errors."""
    if not os.environ.get("TRELLIS_STORAGE_API_KEY"):
        return {"verified": False, "reason": "missing_storage_key"}
    if not UPLOADER.is_file():
        return {"verified": False, "reason": "uploader_missing"}
    try:
        with tempfile.TemporaryDirectory(prefix="trellis-r2-preflight-") as directory:
            model = Path(directory) / "startup-preflight.glb"
            model.write_bytes(create_glb())
            result = subprocess.run(
                [sys.executable, str(UPLOADER), str(model)],
                capture_output=True, text=True, timeout=150, check=False,
            )
        if result.returncode or "VERIFIED_R2_BACKUP" not in result.stdout:
            return {"verified": False, "reason": "r2_roundtrip_failed"}
        return {"verified": True, "reason": "upload_download_sha256_verified"}
    except (OSError, subprocess.TimeoutExpired):
        return {"verified": False, "reason": "r2_preflight_unavailable"}


if __name__ == "__main__":
    state = verify_backup()
    print("TRELLIS_STORAGE_PREFLIGHT: " + state["reason"], flush=True)
    sys.exit(0 if state["verified"] else 1)
