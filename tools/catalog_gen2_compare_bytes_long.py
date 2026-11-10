#!/usr/bin/env python3
"""Reconstruct Generation II CompareBytesLong across a release catalog."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen2_compare_bytes as short


ROUTINE = bytes.fromhex("1abe200913230b78b120f537c9a7c9")


def compare_bytes_long(left: bytes, right: bytes, count: int) -> tuple[bool, int, int]:
    if not 1 <= count <= 0xFFFF:
        raise ValueError("count must be between 1 and 65535")
    if len(left) < count or len(right) < count:
        raise ValueError("both inputs must contain count bytes")
    for index in range(count):
        if left[index] != right[index]:
            return False, index, index
    return True, count, count


def locate(data: bytes) -> list[int]:
    result, start, limit = [], 0, min(0x4000, len(data))
    while True:
        offset = data.find(ROUTINE, start, limit)
        if offset < 0:
            return result
        result.append(offset)
        start = offset + 1


def source_text() -> str:
    return """SECTION "Long Byte Comparison Reconstruction", ROM0

CompareBytesLong::
.loop
    ld a, [de]
    cp [hl]
    jr nz, .diff
    inc de
    inc hl
    dec bc
    ld a, b
    or c
    jr nz, .loop
    scf
    ret
.diff
    and a
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path = Path("research/releases.csv")
    releases = short.load_releases(root / catalog_path)
    roms = short.rom_index(rom_dir)
    source_path = Path("src/compare_bytes_long.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        matches = locate(roms[sha256].read_bytes())
        if len(matches) != 1:
            raise ValueError(f"expected one CompareBytesLong in {release_id}, found {len(matches)}")
        offset = matches[0]
        function = {
            "name": "CompareBytesLong",
            "rom_offset": offset,
            "bank": 0,
            "address": offset,
            "range_end_exclusive": offset + len(ROUTINE),
            "length": len(ROUTINE),
            "code_sha256": short.digest(ROUTINE),
            "raw_bytes_published": False,
        }
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256, "status": release["status"]},
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": short.file_hash(root / source_path),
            "function": function,
            "semantics": {
                "input": "BC bytes at DE and HL; BC must be between 1 and 65535",
                "operation": "compare in order and stop at the first mismatch",
                "result": "carry set only when all BC bytes match; carry clear on mismatch",
                "pointer_progress": "DE and HL advance only after each matching byte",
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/compare.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-compare-bytes-long.json")
        short.write_json(root / map_path, evidence)
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
        "function": "CompareBytesLong",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/compare-bytes-long-summary.json")
    short.write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/compare-bytes-long-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} CompareBytesLong\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) contain exactly one "
        "ROM0 implementation with the same fifteen-byte code hash. The routine "
        "uses a 16-bit BC count and reports equality through carry. Evidence records "
        "release identity and address without ROM bytes. Korean precedes English "
        "where available; release status is unchanged.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_compare_bytes_long_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    short.write_json(root / "manifests/compare-bytes-long-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "CompareBytesLong",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen2_compare_bytes_long.py",
            "tool_sha256": short.file_hash(Path(__file__)),
            "dependency": {
                "tool": "tools/catalog_gen2_compare_bytes.py",
                "sha256": short.file_hash(Path(short.__file__)),
            },
        },
        "outputs": [{"path": path.as_posix(), "sha256": short.file_hash(root / path)} for path in outputs],
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
