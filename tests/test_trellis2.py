"""Offline migration tests: no model downloads, paid compute or external writes."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Trellis2Tests(unittest.TestCase):
    def test_cross_repo_decoder_and_local_checkpoints_resolve(self):
        m = load("prepare_trellis2_models")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            models = {k: "ckpts/" + k for k in m.REQUIRED_MODELS}
            for stem in models.values():
                for suffix in (".json", ".safetensors"):
                    path = root / (stem + suffix)
                    path.parent.mkdir(exist_ok=True)
                    path.write_text("test")
            models["sparse_structure_decoder"] = "microsoft/TRELLIS-image-large/ckpts/decoder"
            config = {"name": "Trellis2ImageTo3DPipeline", "args": {"models": models}}
            download = mock.Mock(side_effect=lambda **kw: str(root / kw["filename"]))
            result = m.resolve_config(config, root, download)
            self.assertEqual(download.call_count, 2)
            self.assertTrue(all(Path(v).is_absolute() for v in result["args"]["models"].values()))
            self.assertEqual(models["sparse_structure_decoder"],
                             "microsoft/TRELLIS-image-large/ckpts/decoder")
            (root / "ckpts/tex_slat_decoder.safetensors").unlink()
            with self.assertRaisesRegex(ValueError, "Missing checkpoint"):
                m.resolve_config(config, root, download)

    def test_v1_checkpoint_rejected(self):
        m = load("prepare_trellis2_models")
        with self.assertRaisesRegex(ValueError, "v1 checkpoint"):
            m.resolve_config({"name": "TrellisImageTo3DPipeline"}, Path("/tmp"), mock.Mock())

    def test_no_cuda_blocks_before_download(self):
        m = load("gpu_preflight_trellis2")
        fake = types.SimpleNamespace(__version__="2.6.0", version=types.SimpleNamespace(cuda="12.4"),
                                     cuda=types.SimpleNamespace(is_available=lambda: False))
        with mock.patch.dict(sys.modules, {"torch": fake}):
            status = m.check_gpu()
        self.assertFalse(status["ready"])
        self.assertIn("CUDA unavailable", status["issues"])

    def test_generation_uses_v2_pbr_export_and_requires_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "in.png"
            source.write_bytes(b"image")
            target = root / "out.glb"
            mesh = types.SimpleNamespace(vertices="vertices", faces="faces", attrs="attrs",
                                         coords="coords", layout="layout", voxel_size=1,
                                         simplify=mock.Mock())
            pipeline = mock.Mock()
            pipeline.run.return_value = [mesh]
            factory = mock.Mock(return_value=pipeline)
            export = mock.Mock(side_effect=lambda p: Path(p).write_bytes(b"glTF" + b"0" * 32))
            to_glb = mock.Mock(return_value=types.SimpleNamespace(export=export))
            modules = {
                "gpu_preflight_trellis2": types.SimpleNamespace(check_gpu=lambda: {"ready": True}),
                "prepare_trellis2_models": types.SimpleNamespace(prepare=lambda: root),
                "PIL": types.SimpleNamespace(Image=types.SimpleNamespace(open=mock.MagicMock())),
                "trellis2": types.ModuleType("trellis2"),
                "trellis2.pipelines": types.SimpleNamespace(Trellis2ImageTo3DPipeline=
                    types.SimpleNamespace(from_pretrained=factory)),
                "o_voxel": types.SimpleNamespace(postprocess=types.SimpleNamespace(to_glb=to_glb)),
            }
            argv = ["generate", "--image", str(source), "--output", str(target)]
            with mock.patch.dict(sys.modules, modules), mock.patch.dict(
                os.environ, {"TRELLIS_STORAGE_API_KEY": "test"}), mock.patch.object(
                sys, "argv", argv), mock.patch("subprocess.run") as backup, contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(SCRIPTS / "generate_trellis2_and_backup.py"), run_name="__main__")
                self.assertEqual(to_glb.call_args.kwargs["attr_volume"], "attrs")
                self.assertEqual(to_glb.call_args.kwargs["texture_size"], 2048)
                self.assertEqual(pipeline.run.call_args.kwargs["pipeline_type"], "1024_cascade")
                self.assertTrue(pipeline.low_vram)
                backup.assert_called_once()
                self.assertTrue(backup.call_args.kwargs["check"])
                backup.side_effect = RuntimeError("backup failed")
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                    runpy.run_path(str(SCRIPTS / "generate_trellis2_and_backup.py"), run_name="__main__")
                self.assertEqual(exc.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
