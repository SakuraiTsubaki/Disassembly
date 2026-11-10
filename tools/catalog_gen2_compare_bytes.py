#!/usr/bin/env python3
"""Reconstruct Generation II CompareBytes across a release catalog."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROUTINE = bytes.fromhex("1abec013230d20f8c9")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def compare_bytes(left: bytes, right: bytes, count: int) -> tuple[bool, int, int]:
    if not 1 <= count <= 0xFF:
        raise ValueError("count must be between 1 and 255")
    if len(left) < count or len(right) < count:
        raise ValueError("both inputs must contain count bytes")
    for index in range(count):
        if left[index] != right[index]:
            return False, index, index
    return True, count, count


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


def locate(data: bytes) -> list[int]:
    result, start, limit = [], 0, min(0x4000, len(data))
    while True:
        offset = data.find(ROUTINE, start, limit)
        if offset < 0:
            return result
        result.append(offset)
        start = offset + 1


def source_text() -> str:
    return """SECTION "Byte Comparison Reconstruction", ROM0

CompareBytes::
.loop
    ld a, [de]
    cp [hl]
    ret nz
    inc de
    inc hl
    dec c
    jr nz, .loop
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path = Path("research/releases.csv")
    releases = load_releases(root / catalog_path)
    roms = rom_index(rom_dir)
    source_path = Path("src/compare_bytes.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        matches = locate(roms[sha256].read_bytes())
        if len(matches) != 1:
            raise ValueError(f"expected one CompareBytes in {release_id}, found {len(matches)}")
        offset = matches[0]
        function = {
            "name": "CompareBytes",
            "rom_offset": offset,
            "bank": 0,
            "address": offset,
            "range_end_exclusive": offset + len(ROUTINE),
            "length": len(ROUTINE),
            "code_sha256": digest(ROUTINE),
            "raw_bytes_published": False,
        }
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256, "status": release["status"]},
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": function,
            "semantics": {
                "input": "C bytes at DE and HL; C must be between 1 and 255",
                "operation": "compare in order and stop at the first mismatch",
                "result": "zero flag set only when all C bytes match",
                "pointer_progress": "DE and HL advance only after each matching byte",
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/compare.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-compare-bytes.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release["status"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "address": f"0x{offset:04X}",
            "code_sha256": function["code_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "game": game,
        "function": "CompareBytes",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/compare-bytes-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/compare-bytes-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} CompareBytes\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) contain exactly one "
        "ROM0 implementation with the same nine-byte code hash. Evidence records "
        "release identity and address without ROM bytes. Korean precedes English "
        "where available; release status is unchanged.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_compare_bytes_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/compare-bytes-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "CompareBytes",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen2_compare_bytes.py",
            "tool_sha256": file_hash(Path(__file__)),
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
