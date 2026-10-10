"""Fast, offline safety checks. Does not download models or use GPU."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class TrellisBuildChecks(unittest.TestCase):
    def test_scripts_parse(self):
        for p in (ROOT / "scripts").glob("*.py"):
            with self.subTest(file=p.name):
                ast.parse(p.read_text(encoding="utf-8"), filename=str(p))

    def test_docker_declares_critical_dependencies(self):
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        for expected in (
            "spconv-cu118==2.3.8", "xformers==0.0.27.post2",
            "kaolin==0.16.0", "nvdiffrast", "diffoctreerast",
            "diff-gaussian-rasterization", "git -C /opt/TRELLIS checkout",
            "PIP_CONSTRAINT=", "python -m pip check",
            "preflight_trellis.py",
        ):
            with self.subTest(dependency=expected):
                self.assertIn(expected, docker)

    def test_versions_are_locked(self):
        constraints = (ROOT / "constraints-trellis.txt").read_text(encoding="utf-8")
        for version in (
            "numpy==1.26.4", "torch==2.4.0", "torchvision==0.19.0",
            "transformers==4.44.2", "opencv-python-headless==4.10.0.84",
        ):
            with self.subTest(version=version):
                self.assertIn(version, constraints)

    def test_runtime_blocks_unready_generation(self):
        server = (ROOT / "scripts/trellis_api_server.py").read_text(encoding="utf-8")
        self.assertIn("gpu_status = check_gpu()", server)
        self.assertIn('if not gpu_status["ready"]:', server)
        self.assertIn("200 if ready else 503", server)

if __name__ == "__main__":
    unittest.main()
