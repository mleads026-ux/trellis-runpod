import json
import pathlib
import subprocess
import sys
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "check_gpu_budget.py"


class BudgetTests(unittest.TestCase):
    def check(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=10)

    def test_within_budget(self):
        p = self.check("--gpu-hourly-usd", "0.50", "--expected-setup-minutes", "60",
                       "--expected-generation-minutes", "30")
        self.assertEqual(p.returncode, 0)
        self.assertTrue(json.loads(p.stdout)["within_budget"])

    def test_over_budget_rejected(self):
        p = self.check("--gpu-hourly-usd", "1.00", "--expected-setup-minutes", "100",
                       "--expected-generation-minutes", "30")
        self.assertEqual(p.returncode, 2)
        self.assertFalse(json.loads(p.stdout)["within_budget"])

    def test_zero_price_rejected(self):
        p = self.check("--gpu-hourly-usd", "0", "--expected-setup-minutes", "1",
                       "--expected-generation-minutes", "1")
        self.assertNotEqual(p.returncode, 0)

    def test_negative_storage_rejected(self):
        p = self.check("--gpu-hourly-usd", "0.5", "--storage-hourly-usd", "-1",
                       "--expected-setup-minutes", "1", "--expected-generation-minutes", "1")
        self.assertNotEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
