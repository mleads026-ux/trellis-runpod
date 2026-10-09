"""Additional no-GPU failure matrix for image inputs, GLB integrity and job lifecycle."""
import contextlib
import io
import json
import os
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import struct
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock
import zlib

from test_runtime_integration import load_module, valid_glb, valid_png


class ImagePayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stub = types.ModuleType("gpu_preflight")
        stub.check_gpu = lambda: {"ready": False, "issues": ["synthetic no GPU"]}
        with mock.patch.dict(sys.modules, {"gpu_preflight": stub}):
            cls.api = load_module("server_image_matrix", "trellis_api_server.py")

    def test_real_png_image_passes(self):
        self.api.validate_image_upload(valid_png(), "image/png")

    def test_real_jpeg_image_passes(self):
        from PIL import Image
        stream = io.BytesIO()
        Image.new("RGB", (8, 8), (50, 90, 100)).save(stream, format="JPEG")
        self.api.validate_image_upload(stream.getvalue(), "image/jpeg")

    def test_mismatched_mime_rejected(self):
        with self.assertRaises(ValueError):
            self.api.validate_image_upload(valid_png(), "image/jpeg")

    def test_bogus_png_rejected(self):
        with self.assertRaises(ValueError):
            self.api.validate_image_upload(b"not a real png", "image/png")

    def test_corrupt_png_crc_rejected(self):
        payload = bytearray(valid_png())
        payload[29] ^= 0xFF
        with self.assertRaises(ValueError):
            self.api.validate_image_upload(bytes(payload), "image/png")

    def test_fully_transparent_image_rejected(self):
        from PIL import Image
        output = io.BytesIO()
        Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(output, "PNG")
        with self.assertRaisesRegex(ValueError, "transparent"):
            self.api.validate_image_upload(output.getvalue(), "image/png")

    def test_unreasonably_large_dimensions_rejected_before_decode(self):
        png = valid_png()
        def chunk(tag, body):
            return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))
        huge_ihdr = struct.pack(">IIBBBBB", 5000, 5000, 8, 6, 0, 0, 0)
        spoof_large = png[:8] + chunk(b"IHDR", huge_ihdr) + png[33:]
        with self.assertRaises(ValueError):
            self.api.validate_image_upload(spoof_large, "image/png")


class GLBPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = load_module("storage_glb_matrix", "save_trellis_output.py")

    def test_valid_json_only_glb_passes(self):
        self.assertTrue(self.storage.validate_glb_bytes(valid_glb()))

    def test_valid_glb_with_binary_chunk_passes(self):
        data = valid_glb()
        tail = struct.pack("<I4s", 4, bytes([66,73,78,0])) + b"ABCD"
        data = data[:8] + struct.pack("<I", len(data)+len(tail)) + data[12:] + tail
        self.assertTrue(self.storage.validate_glb_bytes(data))

    def test_wrong_magic_version_declared_size_rejected(self):
        data = valid_glb()
        candidates = [b"xxxx"+data[4:], data[:4]+struct.pack("<I", 1)+data[8:],
                      data[:8]+struct.pack("<I", 999)+data[12:]]
        for payload in candidates:
            with self.subTest(payload=payload[:12]):
                with self.assertRaises(ValueError):
                    self.storage.validate_glb_bytes(payload)

    def test_corrupt_json_chunk_type_or_body_rejected(self):
        data = valid_glb()
        cases = [data[:16]+b"BIN "+data[20:],
                 data[:20]+b"x"*len(data[20:]),
                 data[:-1]]
        for payload in cases:
            with self.subTest(payload=payload[12:24]):
                with self.assertRaises(ValueError):
                    self.storage.validate_glb_bytes(payload)

    def test_invalid_local_glb_must_not_attempt_network_upload(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td)/"corrupt.glb"
            file.write_bytes(b"this is not GLB")
            with mock.patch.dict(os.environ, {"TRELLIS_STORAGE_API_KEY": "test-private"}), \
                 mock.patch.object(sys, "argv", ["save_trellis_output.py", str(file)]), \
                 mock.patch.object(self.storage.urllib.request, "urlopen") as urlopen:
                with self.assertRaises(ValueError):
                    self.storage.main()
                urlopen.assert_not_called()


class ServerLifecycleTests(unittest.TestCase):
    def setUp(self):
        stub = types.ModuleType("gpu_preflight")
        stub.check_gpu = lambda: {"ready": True, "issues": []}
        self.patch_gpu = mock.patch.dict(sys.modules, {"gpu_preflight": stub})
        self.patch_gpu.start()
        self.api = load_module("api_lifecycle_matrix", "trellis_api_server.py")
        self.tmp = tempfile.TemporaryDirectory()
        self.api.root = Path(self.tmp.name)
        self.api.jobs = {}
        self.api.busy = threading.Lock()
        self.env = mock.patch.dict(os.environ, {"TRELLIS_API_KEY": "test-local-key",
                                               "TRELLIS_STORAGE_API_KEY": "test-local-storage"})
        self.env.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.api.API)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.env.stop()
        self.patch_gpu.stop()
        self.tmp.cleanup()

    def request(self, method, path, *, image=None, authorized=True, kind="image/png"):
        con = HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=4)
        headers = {"Content-Type": kind}
        if authorized:
            headers["Authorization"] = "Bearer test-local-key"
        try:
            con.request(method, path, body=image, headers=headers)
            response = con.getresponse()
            return response.status, json.loads(response.read())
        finally:
            con.close()

    def wait_job(self, job_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            code, data = self.request("GET", "/jobs/"+job_id)
            if data.get("status") in ("completed", "failed"):
                return code, data
            time.sleep(0.02)
        self.fail("job did not complete in 5 seconds")

    def test_authentication_blocks_submission_and_job_lookup(self):
        self.assertEqual(self.request("POST", "/generate", authorized=False, image=valid_png())[0], 401)
        self.assertEqual(self.request("GET", "/jobs/nonexistent", authorized=False)[0], 401)
        self.assertEqual(list(self.api.root.iterdir()), [])

    def test_invalid_image_is_rejected_and_lock_released(self):
        self.assertEqual(self.request("POST", "/generate", image=b"fake")[0], 400)
        self.assertFalse(self.api.busy.locked())
        self.assertEqual(list(self.api.root.iterdir()), [])

    def test_same_image_wrong_mime_rejected(self):
        self.assertEqual(self.request("POST", "/generate", image=valid_png(), kind="image/jpeg")[0], 400)
        self.assertFalse(self.api.busy.locked())

    def test_zero_exit_without_glb_is_failed_not_completed(self):
        fake_result = types.SimpleNamespace(returncode=0, stderr="", stdout="")
        with mock.patch.object(self.api.subprocess, "run", return_value=fake_result):
            code, data = self.request("POST", "/generate", image=valid_png())
            self.assertEqual(code, 202)
            _, job = self.wait_job(data["job_id"])
            self.assertEqual(job["status"], "failed")
            self.assertIn("without a valid-sized GLB", job["error"])
        self.assertFalse(self.api.busy.locked())

    def test_busy_job_rejects_second_job_then_completes_first(self):
        executing = threading.Event()
        release = threading.Event()
        def fake_generation(command, **kwargs):
            executing.set()
            if not release.wait(4):
                raise TimeoutError("offline test release was not signalled")
            output = Path(command[command.index("--output")+1])
            output.write_bytes(valid_glb())
            return types.SimpleNamespace(returncode=0, stderr="", stdout="")
        with mock.patch.object(self.api.subprocess, "run", side_effect=fake_generation):
            code, result = self.request("POST", "/generate", image=valid_png())
            self.assertEqual(code, 202)
            try:
                self.assertTrue(executing.wait(2), "generation subprocess not started")
                self.assertEqual(self.request("POST", "/generate", image=valid_png())[0], 409)
                self.assertEqual(self.request("GET", "/jobs/"+result["job_id"])[1]["status"], "running")
            finally:
                release.set()
            _, job = self.wait_job(result["job_id"])
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["backup"], "verified")
            self.assertTrue(Path(job["output"]).is_file())
        self.assertFalse(self.api.busy.locked())


if __name__ == "__main__":
    unittest.main()
