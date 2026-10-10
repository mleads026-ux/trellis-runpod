"""Offline tests: real startup checks never run GPU inference or leak API keys."""
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

PATH=Path(__file__).resolve().parents[1]/"scripts"/"storage_preflight.py"
spec=importlib.util.spec_from_file_location("trellis_storage_preflight_tests",PATH)
preflight=importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class StoragePreflightTests(unittest.TestCase):
    def test_tiny_glb_is_valid_version_2(self):
        blob=preflight.create_glb()
        self.assertEqual(blob[:4],b"glTF")
        self.assertEqual(struct.unpack_from("<I",blob,4)[0],2)
        self.assertEqual(struct.unpack_from("<I",blob,8)[0],len(blob))
        self.assertIn(b'"version":"2.0"',blob)

    def test_missing_secret_never_calls_network(self):
        with mock.patch.dict(os.environ, {"TRELLIS_STORAGE_API_KEY":""}),mock.patch.object(preflight.subprocess,"run") as called:
            state=preflight.verify_backup()
        self.assertEqual(state,{"verified":False,"reason":"missing_storage_key"})
        called.assert_not_called()

    def test_failed_uploader_never_passes_even_with_secret(self):
        result=types.SimpleNamespace(returncode=1,stderr="BACKUP_FAILED: HTTP 401",stdout="")
        with mock.patch.dict(os.environ,{"TRELLIS_STORAGE_API_KEY":"synthetic-test-key"}), mock.patch.object(preflight.subprocess,"run",return_value=result):
            self.assertEqual(preflight.verify_backup()["verified"],False)

    def test_zero_exit_without_verified_download_never_passes(self):
        result=types.SimpleNamespace(returncode=0,stderr="",stdout="upload complete")
        with mock.patch.dict(os.environ,{"TRELLIS_STORAGE_API_KEY":"synthetic-test-key"}), mock.patch.object(preflight.subprocess,"run",return_value=result):
            self.assertEqual(preflight.verify_backup()["verified"],False)

    def test_verified_round_trip_allows_generation(self):
        result=types.SimpleNamespace(returncode=0,stderr="",stdout="VERIFIED_R2_BACKUP models/check.glb")
        with mock.patch.dict(os.environ,{"TRELLIS_STORAGE_API_KEY":"synthetic-test-key"}), mock.patch.object(preflight.subprocess,"run",return_value=result) as called:
            status=preflight.verify_backup()
        self.assertEqual(status,{"verified":True,"reason":"upload_download_sha256_verified"})
        args=called.call_args
        self.assertIn("save_trellis_output.py",args.args[0][1])
        self.assertTrue(args.kwargs["capture_output"])
        self.assertGreaterEqual(args.kwargs["timeout"],100)

    def test_preflight_network_timeout_fails_closed(self):
        with mock.patch.dict(os.environ,{"TRELLIS_STORAGE_API_KEY":"synthetic-test-key"}), mock.patch.object(preflight.subprocess,"run",side_effect=subprocess.TimeoutExpired("synthetic",150)):
            self.assertEqual(preflight.verify_backup(),{"verified":False,"reason":"r2_preflight_unavailable"})


if __name__=="__main__":
    unittest.main()
