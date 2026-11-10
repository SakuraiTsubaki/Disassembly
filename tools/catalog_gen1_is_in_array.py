#!/usr/bin/env python3
"""Reconstruct Generation I IsInArray across a release catalog."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen1_fill_memory as common


ROUTINE = bytes.fromhex("06004f7efeff2807b92806041918f4a7c937c9")
LANGUAGE_PRIORITY = {
    "Japanese": 0, "Korean": 1, "English": 2, "German": 3,
    "French": 4, "Italian": 5, "Spanish": 6,
}


def ordered(releases: list[dict]) -> list[dict]:
    return sorted(
        releases,
        key=lambda item: (
            LANGUAGE_PRIORITY.get(item["language"], 99),
            int(item["revision"]),
            item["id"],
        ),
    )


def is_in_array(data: bytes, value: int, stride: int) -> tuple[bool, int]:
    if not 0 <= value <= 0xFF:
        raise ValueError("value must fit in one byte")
    if not 1 <= stride <= 0xFFFF:
        raise ValueError("stride must be between 1 and 65535")
    index, offset = 0, 0
    while offset < len(data):
        current = data[offset]
        if current == 0xFF:
            return False, index & 0xFF
        if current == value:
            return True, index & 0xFF
        index += 1
        offset += stride
    raise ValueError("array has no reachable 0xff terminator")


def locate(data: bytes) -> list[int]:
    result, start, limit = [], 0, min(0x4000, len(data))
    while True:
        offset = data.find(ROUTINE, start, limit)
        if offset < 0:
            return result
        result.append(offset)
        start = offset + 1


def source_text() -> str:
    return """SECTION "Array Search Reconstruction", ROM0

IsInArray::
    ld b, 0
IsInRestOfArray::
    ld c, a
.loop
    ld a, [hl]
    cp -1
    jr z, .notfound
    cp c
    jr z, .found
    inc b
    add hl, de
    jr .loop
.notfound
    and a
    ret
.found
    scf
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path, releases = common.load_releases(root)
    releases = ordered(releases)
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    languages = [item["language"] for item in releases]
    if "Korean" in languages and languages.index("Korean") > languages.index("English"):
        raise ValueError("Korean release must precede English when available")
    if "English" in languages:
        global_languages = {"German", "French", "Italian", "Spanish"}
        if any(languages.index("English") > languages.index(item)
               for item in global_languages if item in languages):
            raise ValueError("English must precede other non-origin official languages")
    roms = common.rom_index(rom_dir)
    source_path = Path("src/is_in_array.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        matches = locate(roms[sha256].read_bytes())
        if len(matches) != 1:
            raise ValueError(f"expected one IsInArray in {release_id}, found {len(matches)}")
        offset = matches[0]
        function = {
            "name": "IsInArray",
            "secondary_entry": {"name": "IsInRestOfArray", "address": offset + 2},
            "rom_offset": offset,
            "bank": 0,
            "address": offset,
            "range_end_exclusive": offset + len(ROUTINE),
            "length": len(ROUTINE),
            "code_sha256": common.digest(ROUTINE),
            "raw_bytes_published": False,
        }
        evidence = {
            "schema_version": 1,
            "target": {
                "release": release_id,
                "sha256": sha256,
                "status": release.get("status", "candidate"),
            },
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": common.file_hash(root / source_path),
            "function": function,
            "semantics": {
                "input": "A search byte, HL array base and DE positive entry stride",
                "terminator": "0xff in the first byte of an entry",
                "result": "B is the entry index; carry is set only when found",
                "secondary_entry": "IsInRestOfArray preserves the caller-supplied B start index",
                "precedence": "0xff terminates before it can match a search value",
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/array2.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-is-in-array.json")
        common.write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release.get("status", "candidate"),
            "sha256": sha256,
            "origin_reference": index == 0,
            "address": f"0x{offset:04X}",
            "secondary_entry_address": f"0x{offset + 2:04X}",
            "code_sha256": function["code_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "game": game,
        "function": "IsInArray",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/is-in-array-summary.json")
    common.write_json(root / summary_path, summary)
    language_text = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/is-in-array-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} IsInArray\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({language_text}) contain exactly "
        "one ROM0 implementation with the same nineteen-byte code hash. The "
        "secondary IsInRestOfArray entry, address, release identity and candidate "
        "status are preserved without publishing ROM bytes. English precedes the "
        "remaining official non-origin languages when no Korean release exists.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_is_in_array_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    common.write_json(root / "manifests/is-in-array-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "IsInArray",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen1_is_in_array.py",
            "tool_sha256": common.file_hash(Path(__file__)),
            "dependency": {
                "tool": "tools/catalog_gen1_fill_memory.py",
                "sha256": common.file_hash(Path(common.__file__)),
            },
        },
        "outputs": [{"path": path.as_posix(), "sha256": common.file_hash(root / path)} for path in outputs],
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
