#!/usr/bin/env python3
"""Reconstruct adjacent Generation I fixed-name skip and AddNTimes routines."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen1_is_in_array as base


SKIP_PREFIX = bytes.fromhex("a7c801")
LOOP = bytes.fromhex("093d20fcc9")
ADD = bytes.fromhex("a7c8093d20fcc9")
SKIP_LENGTH = len(SKIP_PREFIX) + 2 + len(LOOP)
ADD_LENGTH = len(ADD)
PAIR_LENGTH = SKIP_LENGTH + ADD_LENGTH


def add_n_times(pointer: int, count: int, stride: int) -> int:
    if not 0 <= pointer <= 0xFFFF or not 0 <= stride <= 0xFFFF:
        raise ValueError("pointer and stride must fit in 16 bits")
    if not 0 <= count <= 0xFF:
        raise ValueError("count must fit in one byte")
    return (pointer + count * stride) & 0xFFFF


def locate(data: bytes) -> list[dict]:
    result, limit = [], min(0x4000, len(data))
    for offset in range(max(0, limit - PAIR_LENGTH + 1)):
        if data[offset:offset + len(SKIP_PREFIX)] != SKIP_PREFIX:
            continue
        imm = offset + len(SKIP_PREFIX)
        if data[imm + 2:offset + SKIP_LENGTH] != LOOP:
            continue
        if data[offset + SKIP_LENGTH:offset + PAIR_LENGTH] != ADD:
            continue
        pair = data[offset:offset + PAIR_LENGTH]
        result.append({
            "skip_address": offset,
            "add_address": offset + SKIP_LENGTH,
            "name_length": int.from_bytes(data[imm:imm + 2], "little"),
            "pair_sha256": base.common.digest(pair),
        })
    return result


def source_text() -> str:
    return """SECTION "Array Stride Reconstruction", ROM0

SkipFixedLengthTextEntries::
    and a
    ret z
    ld bc, NAME_LENGTH
.skipLoop
    add hl, bc
    dec a
    jr nz, .skipLoop
    ret

AddNTimes::
    and a
    ret z
.loop
    add hl, bc
    dec a
    jr nz, .loop
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path, releases = base.common.load_releases(root)
    releases = base.ordered(releases)
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    roms = base.common.rom_index(rom_dir)
    source_path = Path("src/skip_fixed_length_text_entries_add_n_times.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        matches = locate(roms[sha256].read_bytes())
        if len(matches) != 1:
            raise ValueError(f"expected one routine pair in {release_id}, found {len(matches)}")
        match = matches[0]
        skip_address, add_address = match["skip_address"], match["add_address"]
        functions = {
            "SkipFixedLengthTextEntries": {
                "rom_offset": skip_address,
                "bank": 0,
                "address": skip_address,
                "range_end_exclusive": add_address,
                "length": SKIP_LENGTH,
                "name_length": match["name_length"],
                "raw_bytes_published": False,
            },
            "AddNTimes": {
                "rom_offset": add_address,
                "bank": 0,
                "address": add_address,
                "range_end_exclusive": add_address + ADD_LENGTH,
                "length": ADD_LENGTH,
                "raw_bytes_published": False,
            },
            "adjacent_pair_sha256": match["pair_sha256"],
        }
        evidence = {
            "schema_version": 1,
            "target": {
                "release": release_id, "sha256": sha256,
                "status": release.get("status", "candidate"),
            },
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": base.common.file_hash(root / source_path),
            "functions": functions,
            "semantics": {
                "SkipFixedLengthTextEntries": "advance HL by A times release-specific NAME_LENGTH",
                "AddNTimes": "advance HL by A times BC",
                "zero_count": "return without changing HL",
                "adjacency": "the fixed-name helper ends exactly where AddNTimes begins",
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/array.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-skip-fixed-add-n-times.json")
        base.common.write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release.get("status", "candidate"),
            "sha256": sha256,
            "origin_reference": index == 0,
            "skip_address": f"0x{skip_address:04X}",
            "add_n_times_address": f"0x{add_address:04X}",
            "name_length": match["name_length"],
            "pair_sha256": match["pair_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "game": game,
        "functions": ["SkipFixedLengthTextEntries", "AddNTimes"],
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/skip-fixed-add-n-times-summary.json")
    base.common.write_json(root / summary_path, summary)
    language_text = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/skip-fixed-add-n-times-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} fixed-name skip and AddNTimes\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({language_text}) contain exactly "
        "one adjacent pair. Japanese builds use NAME_LENGTH 6; the official "
        "non-origin localizations use 11. Both addresses, the immediate length, "
        "candidate status and pair hash are retained without publishing ROM bytes.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_skip_fixed_add_n_times_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    base.common.write_json(root / "manifests/skip-fixed-add-n-times-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "functions": ["SkipFixedLengthTextEntries", "AddNTimes"],
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen1_skip_fixed_add_n_times.py",
            "tool_sha256": base.common.file_hash(Path(__file__)),
            "dependency": {
                "tool": "tools/catalog_gen1_is_in_array.py",
                "sha256": base.common.file_hash(Path(base.__file__)),
            },
        },
        "outputs": [{"path": path.as_posix(), "sha256": base.common.file_hash(root / path)} for path in outputs],
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
