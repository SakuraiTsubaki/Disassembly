from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("validator", ROOT / "tools/validate_repository.py")
hasher = load_module("hasher", ROOT / "tools/hash_input.py")
artifacts = load_module("artifacts", ROOT / "tools/verify_artifacts.py")


class FoundationTests(unittest.TestCase):
    def test_repository_contract(self):
        self.assertEqual(validator.validate(ROOT), [])
        self.assertEqual(artifacts.validate(ROOT), [])

    def test_catalog_has_unique_twelve_projects(self):
        catalog = json.loads((ROOT / "projects/catalog.json").read_text())
        projects = catalog["projects"]
        self.assertEqual(len(projects), 12)
        self.assertEqual(len({item["id"] for item in projects}), 12)
        self.assertEqual(len({item["repository"] for item in projects}), 12)

    def test_hash_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.bin"
            path.write_bytes(b"abc")
            result = hasher.hash_file(path, chunk_size=1)
        self.assertEqual(result["size"], 3)
        self.assertEqual(
            result["sha256"],
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_non_rom_binary_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "derived.bin").write_bytes(b"derived data")
            self.assertEqual(artifacts.validate(root), [])

    def test_rom_extensions_and_archived_roms_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "rebuilt.gbc").write_bytes(b"rom")
            with zipfile.ZipFile(root / "bundle.zip", "w") as archive:
                archive.writestr("modified.gba", b"rom")
            errors = artifacts.validate(root)
        self.assertEqual(len(errors), 2)

    def test_encoded_graphics_require_png(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graphics = root / "graphics"
            graphics.mkdir()
            (graphics / "sprite.4bpp").write_bytes(b"pixels")
            self.assertEqual(len(artifacts.validate(root)), 1)
            (graphics / "sprite.png").write_bytes(b"preview")
            self.assertEqual(artifacts.validate(root), [])


if __name__ == "__main__":
    unittest.main()
