"""Offline safety checks for TRELLIS generator; never downloads weights or starts a GPU."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_trellis_and_backup.py"
BACKUP = ROOT / "scripts" / "save_trellis_output.py"


class PipelineSafety(unittest.TestCase):
    def invoke(self, script, args, env=None):
        return subprocess.run(
            [sys.executable, str(script), *args], text=True,
            capture_output=True, timeout=15, env={**os.environ, **(env or {})},
        )

    def test_missing_image_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.invoke(SCRIPT, ["--image", f"{tmp}/missing.png", "--output", f"{tmp}/out.glb"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Input image not found", result.stderr)

    def test_missing_backup_secret_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = pathlib.Path(tmp) / "image.png"
            image.write_bytes(b"test")
            result = self.invoke(SCRIPT, ["--image", str(image), "--output", f"{tmp}/out.glb"],
                                 {"TRELLIS_STORAGE_API_KEY": ""})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TRELLIS_STORAGE_API_KEY missing", result.stderr)

    def test_bad_output_extension_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = pathlib.Path(tmp) / "image.png"
            image.write_bytes(b"test")
            result = self.invoke(SCRIPT, ["--image", str(image), "--output", f"{tmp}/out.ply"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Output must end in .glb", result.stderr)

    def test_backup_requires_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = pathlib.Path(tmp) / "model.glb"
            model.write_bytes(b"glTFtest")
            result = self.invoke(BACKUP, [str(model)], {"TRELLIS_STORAGE_API_KEY": ""})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BACKUP_FAILED", result.stderr)

    def test_backup_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.invoke(BACKUP, [f"{tmp}/missing.glb"], {"TRELLIS_STORAGE_API_KEY": "test"})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BACKUP_FAILED", result.stderr)

    def test_backup_rejects_oversize_before_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = pathlib.Path(tmp) / "huge.glb"
            with model.open("wb") as f:
                f.truncate(101 * 1024 * 1024)
            result = self.invoke(BACKUP, [str(model)], {"TRELLIS_STORAGE_API_KEY": "test"})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BACKUP_FAILED", result.stderr)


if __name__ == "__main__":
    unittest.main()
