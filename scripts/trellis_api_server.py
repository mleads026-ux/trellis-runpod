"""Authenticated TRELLIS image-to-GLB HTTP API for a running GPU Pod."""
import io
import json
import os
import warnings
import secrets
import subprocess
import sys
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from gpu_preflight import check_gpu

jobs = {}
busy = threading.Lock()
root = Path("/workspace/trellis-jobs")

MAX_IMAGE_PIXELS = 16_777_216


def validate_image_upload(payload, content_type):
    """Reject corrupt, incorrectly typed, huge and fully transparent images."""
    from PIL import Image
    expected = {"image/png": "PNG", "image/jpeg": "JPEG"}[content_type]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as img:
                if img.format != expected:
                    raise ValueError("Image content does not match Content-Type")
                if not (0 < img.width * img.height <= MAX_IMAGE_PIXELS):
                    raise ValueError("Image dimensions out of bounds")
                img.verify()
            with Image.open(io.BytesIO(payload)) as img:
                if "A" in img.getbands() and img.getchannel("A").getextrema()[1] == 0:
                    raise ValueError("Image is entirely transparent")
    except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError(f"Invalid image data: {exc}") from exc

# Check once at boot; /health will NOT claim success when CUDA or imports are broken.
gpu_status = check_gpu()

# Fail closed until this Pod has uploaded a test GLB to R2, downloaded it,
# and verified its SHA-256. A configured key alone is NOT proof of access.
storage_verified = False
storage_status = "not_checked"

class API(BaseHTTPRequestHandler):
    def reply(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def auth(self):
        key = os.getenv("TRELLIS_API_KEY", "")
        return bool(key) and secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + key)

    def do_GET(self):
        if self.path == "/health":
            backup_configured = bool(os.getenv("TRELLIS_STORAGE_API_KEY"))
            ready = gpu_status["ready"] and backup_configured and storage_verified
            return self.reply(200 if ready else 503, {
                "status": "ready" if ready else "not_ready",
                "gpu": gpu_status,
                "backup_ready": ready,
                "backup_configured": backup_configured,
                "backup_verified": storage_verified,
                "backup_preflight": storage_status,
                "message": None if ready else "No paid generation: verify GPU and live R2 GLB upload/download before continuing.",
            })
        if not self.auth():
            return self.reply(401, {"error": "unauthorized"})
        if self.path.startswith("/jobs/"):
            job = jobs.get(self.path[6:])
            return self.reply(200 if job else 404, job or {"error": "not found"})
        self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/generate":
            return self.reply(404, {"error": "not found"})
        if not self.auth():
            return self.reply(401, {"error": "unauthorized"})
        if not gpu_status["ready"]:
            return self.reply(503, {"error": "GPU preflight failed", "issues": gpu_status["issues"]})
        if not os.getenv("TRELLIS_STORAGE_API_KEY"):
            return self.reply(503, {"error": "backup key missing"})
        if not storage_verified:
            return self.reply(503, {"error": "R2 backup roundtrip not verified", "preflight": storage_status})
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.reply(400, {"error": "invalid length"})
        kind = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if kind not in ("image/png", "image/jpeg") or not 0 < n <= 15 * 1024 * 1024:
            return self.reply(400, {"error": "PNG/JPEG required, maximum 15 MiB"})
        if not busy.acquire(blocking=False):
            return self.reply(409, {"error": "GPU busy"})
        try:
            data = self.rfile.read(n)
            if len(data) != n:
                raise ValueError("incomplete image")
            validate_image_upload(data, kind)
            job_id = secrets.token_hex(12)
            root.mkdir(parents=True, exist_ok=True)
            image = root / (job_id + (".png" if kind == "image/png" else ".jpg"))
            image.write_bytes(data)
            jobs[job_id] = {"status": "running", "id": job_id}
            threading.Thread(target=run, args=(job_id, image), daemon=True).start()
            self.reply(202, {"job_id": job_id})
        except Exception:
            busy.release()
            self.reply(400, {"error": "invalid upload"})

def run(job_id, image):
    try:
        output = root / (job_id + ".glb")
        result = subprocess.run(
            [sys.executable, "/opt/trellis-runpod/scripts/generate_trellis_and_backup.py",
             "--image", str(image), "--output", str(output)],
            capture_output=True, text=True, timeout=3600,
        )
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout)[-800:])
        if not output.is_file() or output.stat().st_size < 20:
            raise RuntimeError("Generator reported success without a valid-sized GLB output")
        jobs[job_id] = {"status": "completed", "id": job_id, "backup": "verified", "output": str(output)}
    except Exception as exc:
        jobs[job_id] = {"status": "failed", "id": job_id, "error": str(exc)[-800:]}
    finally:
        busy.release()

if __name__ == "__main__":
    if not os.getenv("TRELLIS_API_KEY"):
        sys.exit("TRELLIS_API_KEY required")
    from storage_preflight import verify_backup

    verification = verify_backup()
    storage_verified = verification["verified"]
    storage_status = verification["reason"]
    print(f"TRELLIS storage preflight: {storage_status}", flush=True)
    print(f"TRELLIS runtime readiness: {json.dumps(gpu_status)}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8000), API).serve_forever()
