from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sync_gba_release_baseline", ROOT / "tools" / "sync_gba_release_baseline.py"
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def observed(release_id, language, revision, sha, build_kind="retail"):
    code = {"Japanese": "J", "English": "E", "German": "D"}[language]
    return {
        "id": release_id,
        "market": language,
        "language": language,
        "revision": revision,
        "build_kind": build_kind,
        "size": 16,
        "sha1": sha[:40],
        "sha256": sha,
        "observed_filenames": [release_id + ".gba"],
        "header": {"title": "GAME", "game_code": "ABC" + code, "header_checksum": 1},
        "validation": {"header_checksum_valid": True},
    }


class SyncGbaReleaseBaselineTests(unittest.TestCase):
    def test_materializes_retail_and_preserves_existing_metadata(self):
        jp = observed("j", "Japanese", 0, "1" * 64)
        en = observed("e", "English", 0, "2" * 64)
        debug = observed("d-debug", "German", 0, "3" * 64, "debug")
        project = {"releases": [{"id": "game-jp-rev0", "region": "Japan", "language": "Japanese", "revision": "0", "status": "candidate", "size": 16, "sha1": "1" * 40, "sha256": "1" * 64}]}
        report = {"schema_version": 1, "generator": {"name": "test"}}
        updated_project, updated_report = module.materialize(
            {"releases": [jp, en, debug]}, project, report, "game", "2026-10-13"
        )
        self.assertEqual([x["id"] for x in updated_project["releases"]], ["game-jp-rev0", "game-en-rev0"])
        self.assertEqual(updated_project["releases"][0]["region"], "Japan")
        self.assertEqual(updated_report["unique_identities"], 2)
        self.assertEqual(updated_report["observed_files"], 2)

    def test_rejects_changed_existing_identity_and_unknown_language(self):
        release = observed("j", "Japanese", 0, "1" * 64)
        project = {"releases": [{"id": "game-jp-rev0", "sha256": "0" * 64}]}
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            module.materialize({"releases": [release]}, project, {"generator": {}}, "game", "date")
        release["language"] = "Klingon"
        with self.assertRaisesRegex(ValueError, "unsupported language"):
            module.materialize({"releases": [release]}, {"releases": []}, {"generator": {}}, "game", "date")


if __name__ == "__main__":
    unittest.main()

