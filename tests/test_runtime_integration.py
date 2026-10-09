"""Deterministic CPU-only integration tests; no GPU, network, cloud keys or downloads."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import sys
import struct
import zlib
import tempfile
import threading
import time
import types
import unittest
from unittest import mock
from http.server import ThreadingHTTPServer
from http.client import HTTPConnection

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def valid_glb():
    document = b'{"asset":{"version":"2.0"}}'
    document += b" " * ((-len(document)) % 4)
    return struct.pack("<4sII", b"glTF", 2, 20 + len(document)) + struct.pack("<I4s", len(document), b"JSON") + document


def valid_png():
    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))
    return (bytes([137, 80, 78, 71, 13, 10, 26, 10])
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes([0, 255, 0, 0, 255])))
            + chunk(b"IEND", b""))



def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManifestTests(unittest.TestCase):
    def test_all_checkpoint_pairs_are_required(self):
        m = load_module("manifest_for_test", "verify_model_manifest.py")
        models = {
            "sparse_structure_decoder": "ckpts/a",
            "sparse_structure_flow_model": "ckpts/b",
            "slat_decoder_gs": "ckpts/c",
            "slat_decoder_rf": "ckpts/d",
            "slat_decoder_mesh": "ckpts/e",
            "slat_flow_model": "ckpts/f",
        }
        config = {"name": "TrellisImageTo3DPipeline",
                  "args": {"models": models, "image_cond_model": "dinov2_vitl14_reg"}}
        files = {"pipeline.json"} | {
            stem + suffix for stem in models.values()
            for suffix in (".json", ".safetensors")
        }
        self.assertEqual(m.validate_manifest(config, files), models)
        files.remove("ckpts/c.safetensors")
        with self.assertRaisesRegex(ValueError, "ckpts/c.safetensors"):
            m.validate_manifest(config, files)


class RuntimeGpuTests(unittest.TestCase):
    def test_missing_cuda_fails_closed(self):
        m = load_module("gpu_preflight_for_test", "gpu_preflight.py")
        fake_torch = types.SimpleNamespace(
            __version__="2.4.0+cu118", version=types.SimpleNamespace(cuda="11.8"),
            cuda=types.SimpleNamespace(is_available=lambda: False),
        )
        with mock.patch.dict(sys.modules, {"torch": fake_torch}):
            result = m.check_gpu()
        self.assertFalse(result["ready"])
        self.assertTrue(any("CUDA" in issue for issue in result["issues"]))

    def test_low_vram_and_blackwell_fail_closed(self):
        m = load_module("gpu_preflight_other_test", "gpu_preflight.py")
        prop = types.SimpleNamespace(name="Synthetic GPU", total_memory=8*1024**3, major=12, minor=0)
        cuda = types.SimpleNamespace(
            is_available=lambda: True, current_device=lambda: 0,
            get_device_properties=lambda n: prop,
        )
        fake_torch = types.SimpleNamespace(
            __version__="2.4.0+cu118", version=types.SimpleNamespace(cuda="11.8"),
            cuda=cuda, ones=lambda *a, **kw: types.SimpleNamespace(__mul__=lambda _, n: None),
        )
        # The artificial one-element kernel deliberately fails. No GPU is touched.
        with mock.patch.dict(sys.modules, {"torch": fake_torch}), mock.patch.object(
                m.importlib, "import_module", return_value=object()):
            result = m.check_gpu()
        self.assertFalse(result["ready"])
        self.assertTrue(any("VRAM" in issue for issue in result["issues"]))
        self.assertTrue(any("Blackwell" in issue for issue in result["issues"]))


class CacheDryRunTests(unittest.TestCase):
    def test_model_cache_pipeline_uses_dinov2_and_u2net(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            (path / "pipeline.json").write_text(
                json.dumps({"args": {"image_cond_model": "dinov2_vitl14_reg"}}),
                encoding="utf-8",
            )
            hf_download = mock.Mock(return_value=str(path))
            hub = types.SimpleNamespace(load=mock.Mock(return_value=object()))
            rembg = types.SimpleNamespace(new_session=mock.Mock(return_value=object()))
            cache_file = SCRIPTS / "prepare_trellis_models.py"
            with mock.patch.dict(os.environ, {"TRELLIS_CACHE_DIR": str(path)}), mock.patch.dict(
                sys.modules, {"huggingface_hub": types.SimpleNamespace(snapshot_download=hf_download),
                              "torch": types.SimpleNamespace(hub=hub), "rembg": rembg}
            ), contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(cache_file), run_name="__main__")
            hf_download.assert_called_once_with(repo_id="microsoft/TRELLIS-image-large")
            hub.load.assert_called_once_with(
                "facebookresearch/dinov2", "dinov2_vitl14_reg",
                pretrained=True, trust_repo=True,
            )
            rembg.new_session.assert_called_once_with("u2net")


class BackupDryRunTests(unittest.TestCase):
    def test_verified_copy_and_corrupted_copy_detection(self):
        m = load_module("save_trellis_for_test", "save_trellis_output.py")
        with tempfile.TemporaryDirectory() as td:
            glb = Path(td) / "test.glb"
            raw = valid_glb()
            glb.write_bytes(raw)
            seen = []

            class Response(io.BytesIO):
                def __init__(self, payload=b"", status=200):
                    super().__init__(payload)
                    self.status = status

            def fake_request(req, timeout=120):
                seen.append((req.get_method(), req.full_url))
                if req.get_method() == "PUT":
                    self.assertEqual(req.data, raw)
                    return Response(status=201)
                return Response(raw)

            with mock.patch.dict(os.environ, {"TRELLIS_STORAGE_API_KEY": "offline-test-token"}), \
                 mock.patch.object(sys, "argv", ["save_trellis_output.py", str(glb)]), \
                 mock.patch.object(m.urllib.request, "urlopen", side_effect=fake_request), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                m.main()
                self.assertIn("VERIFIED_R2_BACKUP", output.getvalue())
            self.assertEqual([x[0] for x in seen], ["PUT", "GET"])

            def corrupted(req, timeout=120):
                return Response(status=201) if req.get_method() == "PUT" else Response(b"CORRUPT")
            with mock.patch.dict(os.environ, {"TRELLIS_STORAGE_API_KEY": "offline-test-token"}), \
                 mock.patch.object(sys, "argv", ["save_trellis_output.py", str(glb)]), \
                 mock.patch.object(m.urllib.request, "urlopen", side_effect=corrupted), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                    m.main()


class ServerDryRunTests(unittest.TestCase):
    def test_http_boot_auth_gpu_gate_and_job_failure(self):
        stub = types.ModuleType("gpu_preflight")
        stub.check_gpu = lambda: {"ready": False, "issues": ["synthetic no CUDA"]}
        with mock.patch.dict(sys.modules, {"gpu_preflight": stub}):
            app = load_module("trellis_api_server_for_test", "trellis_api_server.py")
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ, {"TRELLIS_API_KEY": "offline-test-key",
                         "TRELLIS_STORAGE_API_KEY": "offline-test-storage"}
        ):
            app.root = Path(td)
            app.jobs = {}
            app.busy = threading.Lock()
            server = ThreadingHTTPServer(("127.0.0.1", 0), app.API)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(method, path, body=None, authenticated=False, content_type=None):
                con = HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
                headers = {}
                if authenticated:
                    headers["Authorization"] = "Bearer offline-test-key"
                if content_type:
                    headers["Content-Type"] = content_type
                try:
                    con.request(method, path, body=body, headers=headers)
                    response = con.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    con.close()

            try:
                code, data = request("GET", "/health")
                self.assertEqual(code, 503)
                self.assertEqual(data["status"], "not_ready")
                self.assertFalse(data["gpu"]["ready"])
                self.assertEqual(request("GET", "/jobs/fake")[0], 401)
                self.assertEqual(request("POST", "/generate", authenticated=True)[0], 503)
                app.gpu_status = {"ready": True, "issues": []}
                self.assertEqual(request("GET", "/health")[0], 200)
                self.assertEqual(request("POST", "/generate", authenticated=True,
                                         body=b"invalid", content_type="text/plain")[0], 400)
                with mock.patch.object(app.subprocess, "run", return_value=types.SimpleNamespace(
                        returncode=1, stderr="offline test failure", stdout="")):
                    code, data = request("POST", "/generate", authenticated=True,
                                         body=valid_png(), content_type="image/png")
                    self.assertEqual(code, 202)
                    job_id = data["job_id"]
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        status, job = request("GET", "/jobs/" + job_id, authenticated=True)
                        if job["status"] == "failed":
                            break
                        time.sleep(0.02)
                    self.assertEqual(status, 200)
                    self.assertEqual(job["status"], "failed")
                    self.assertIn("offline test failure", job["error"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
