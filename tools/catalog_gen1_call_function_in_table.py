#!/usr/bin/env python3
"""Reconstruct Generation I CallFunctionInTable across release catalogs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen1_is_in_array as base


PREFIX = bytes.fromhex("e5d5c58716005f192a666f11")
SUFFIX = bytes.fromhex("d5e9c1d1e1c9")
LENGTH = len(PREFIX) + 2 + len(SUFFIX)
RETURN_OFFSET = len(PREFIX) + 2 + 2


def table_target(table: bytes, index: int) -> int:
    if not 0 <= index < 0x80:
        raise ValueError("index must be between 0 and 127")
    offset = index * 2
    if offset + 2 > len(table):
        raise ValueError("jump table does not contain the requested entry")
    return int.from_bytes(table[offset:offset + 2], "little")


def locate(data: bytes) -> list[dict]:
    result, start, limit = [], 0, min(0x4000, len(data))
    while True:
        offset = data.find(PREFIX, start, limit)
        if offset < 0:
            return result
        end = offset + LENGTH
        if end <= limit and data[end - len(SUFFIX):end] == SUFFIX:
            embedded = int.from_bytes(data[offset + len(PREFIX):offset + len(PREFIX) + 2], "little")
            expected = offset + RETURN_OFFSET
            if embedded == expected:
                result.append({
                    "rom_offset": offset,
                    "bank": 0,
                    "address": offset,
                    "range_end_exclusive": end,
                    "length": LENGTH,
                    "return_address": embedded,
                    "return_offset": RETURN_OFFSET,
                    "code_sha256": base.common.digest(data[offset:end]),
                })
        start = offset + 1


def source_text() -> str:
    return """SECTION "Jump Table Call Reconstruction", ROM0

CallFunctionInTable::
    push hl
    push de
    push bc
    add a
    ld d, 0
    ld e, a
    add hl, de
    ld a, [hli]
    ld h, [hl]
    ld l, a
    ld de, .returnAddress
    push de
    jp hl
.returnAddress
    pop bc
    pop de
    pop hl
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path, releases = base.common.load_releases(root)
    releases = base.ordered(releases)
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    roms = base.common.rom_index(rom_dir)
    source_path = Path("src/call_function_in_table.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        matches = locate(roms[sha256].read_bytes())
        if len(matches) != 1:
            raise ValueError(f"expected one CallFunctionInTable in {release_id}, found {len(matches)}")
        function = {**matches[0], "name": "CallFunctionInTable", "raw_bytes_published": False}
        evidence = {
            "schema_version": 1,
            "target": {
                "release": release_id, "sha256": sha256,
                "status": release.get("status", "candidate"),
            },
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": base.common.file_hash(root / source_path),
            "function": function,
            "semantics": {
                "input": "A is a zero-based index below 128; HL points to little-endian ROM0 addresses",
                "operation": "load table[A], synthesize a return address, and jump to the target",
                "return_mechanism": "the target returns to the embedded local address pushed before jp hl",
                "preserves_after_target_return": ["HL", "DE", "BC"],
                "clobbers": ["A", "flags"],
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/array2.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-call-function-in-table.json")
        base.common.write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release.get("status", "candidate"),
            "sha256": sha256,
            "origin_reference": index == 0,
            "address": f"0x{function['address']:04X}",
            "return_address": f"0x{function['return_address']:04X}",
            "code_sha256": function["code_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "game": game,
        "function": "CallFunctionInTable",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/call-function-in-table-summary.json")
    base.common.write_json(root / summary_path, summary)
    language_text = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/call-function-in-table-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} CallFunctionInTable\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({language_text}) contain exactly "
        "one ROM0 implementation. Each embedded return address equals function "
        f"start + {RETURN_OFFSET}, proving the local return trampoline rather than "
        "matching only a wildcard byte pattern. Release identity, address, full "
        "routine hash and candidate status are retained without ROM bytes.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_call_function_in_table_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    base.common.write_json(root / "manifests/call-function-in-table-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "CallFunctionInTable",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen1_call_function_in_table.py",
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
