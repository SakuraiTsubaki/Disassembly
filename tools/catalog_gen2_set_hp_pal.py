#!/usr/bin/env python3
"""Reconstruct Generation II SetHPPal across a release catalog."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen2_get_hp_pal as hp


LENGTH = 5


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def load_releases(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        releases = list(csv.DictReader(handle))
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("release catalog must begin with Japanese origin")
    languages = [item["language"] for item in releases]
    if "Korean" in languages and languages.index("Korean") > languages.index("English"):
        raise ValueError("Korean release must precede English when available")
    return releases


def rom_index(directory: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in {".gb", ".gbc"}:
            result.setdefault(file_hash(path), path)
    return result


def locate(data: bytes) -> list[dict]:
    result = []
    for target in hp.locate(data):
        code = bytes((0xCD, target & 0xFF, target >> 8, 0x72, 0xC9))
        start, limit = 0, min(0x4000, len(data))
        matches = []
        while True:
            offset = data.find(code, start, limit)
            if offset < 0:
                break
            matches.append(offset)
            start = offset + 1
        for offset in matches:
            if offset + LENGTH == target:
                result.append({
                    "rom_offset": offset,
                    "bank": 0,
                    "address": offset,
                    "range_end_exclusive": offset + LENGTH,
                    "length": LENGTH,
                    "get_hp_pal_target": target,
                    "destination": "HL",
                    "palette_register": "D",
                    "code_sha256": digest(code),
                })
    return result


def source_text() -> str:
    return """SECTION "Set HP Palette Reconstruction", ROM0

SetHPPal::
    call GetHPPal
    ld [hl], d
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path = Path("research/releases.csv")
    releases = load_releases(root / catalog_path)
    roms = rom_index(rom_dir)
    source_path = Path("src/set_hp_pal.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        matches = locate(data)
        if len(matches) != 1:
            raise ValueError(f"expected one SetHPPal in {release_id}, found {len(matches)}")
        function = matches[0]
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256, "status": release["status"]},
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": {**function, "name": "SetHPPal", "raw_bytes_published": False},
            "semantics": {
                "operation": "classify E through GetHPPal, write palette D to [HL], return",
                "adjacency": "SetHPPal ends exactly where the release-specific GetHPPal begins",
                "destination_register": "HL",
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/tilemap.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-set-hp-pal.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release["status"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "address": f"0x{function['address']:04X}",
            "get_hp_pal_target": f"0x{function['get_hp_pal_target']:04X}",
            "code_sha256": function["code_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "game": game,
        "function": "SetHPPal",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/set-hp-pal-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/set-hp-pal-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} SetHPPal\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) contain exactly one "
        "five-byte wrapper directly before their verified `GetHPPal`. It calls the "
        "release-specific target, writes D to [HL], and returns. Evidence records both "
        "addresses and the wrapper hash without ROM bytes. Korean precedes English "
        "where available; release status is unchanged.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_set_hp_pal_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/set-hp-pal-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "SetHPPal",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen2_set_hp_pal.py",
            "tool_sha256": file_hash(Path(__file__)),
            "dependency": {
                "tool": "tools/catalog_gen2_get_hp_pal.py",
                "sha256": file_hash(Path(hp.__file__)),
            },
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.game, args.reference_repository,
              args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
