from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("catalog_gba_releases", ROOT / "tools" / "catalog_gba_releases.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def identity(filename: str, sha256: str, code: str, revision: int = 0) -> dict:
    return {
        "filename": filename, "size": 16, "sha1": "1" * 40, "sha256": sha256,
        "header": {"game_code": code, "software_version": revision},
        "validation": {key: True for key in (
            "nintendo_logo_valid", "fixed_value_valid", "reserved_area_valid", "header_checksum_valid"
        )},
    }


class CatalogGbaReleasesTests(unittest.TestCase):
    def test_deduplicates_and_sorts_origin_first(self):
        values = [
            identity("English A.gba", "a" * 64, "AXVE"),
            identity("Japanese.gba", "b" * 64, "AXVJ"),
            identity("English B.gba", "a" * 64, "AXVE"),
        ]
        with mock.patch.object(module._inspect, "inspect_file", side_effect=values):
            result = module.build_catalog([Path(str(i)) for i in range(3)], "AXV")
        self.assertEqual(result["observed_files"], 3)
        self.assertEqual(result["unique_identities"], 2)
        self.assertEqual([item["language"] for item in result["releases"]], ["Japanese", "English"])
        self.assertEqual(len(result["releases"][1]["observed_filenames"]), 2)

    def test_rejects_wrong_game_and_invalid_header(self):
        with mock.patch.object(module._inspect, "inspect_file", return_value=identity("wrong.gba", "a" * 64, "AXPE")):
            with self.assertRaisesRegex(ValueError, "prefix mismatch"):
                module.build_catalog([Path("wrong")], "AXV")
        bad = identity("bad.gba", "a" * 64, "AXVJ")
        bad["validation"]["header_checksum_valid"] = False
        with mock.patch.object(module._inspect, "inspect_file", return_value=bad):
            with self.assertRaisesRegex(ValueError, "invalid GBA header"):
                module.build_catalog([Path("bad")], "AXV")


if __name__ == "__main__":
    unittest.main()
