"""Offline test for preflight; should never require a GPU or storage key."""
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PreflightTests(unittest.TestCase):
    def test_preflight_runs_without_gpu_or_network(self):
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "trellis_preflight.py")],
            capture_output=True, text=True, timeout=12,
        )
        self.assertIn(p.returncode, (0, 2))
        self.assertIn('"ready_for_install_review"', p.stdout)
        self.assertIn('"free_disk_gib"', p.stdout)
        self.assertNotIn("TRELLIS_STORAGE_API_KEY", p.stdout)


if __name__ == "__main__":
    unittest.main()
