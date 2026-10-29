#!/usr/bin/env python3
"""Locate and catalog Generation I ClearScreenArea across release sets."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen1_clear_screen as common

ROUTINE_LENGTH = 18
TAIL = bytes.fromhex("111400e5c5220d20fcc1e1190520f4c9")

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def file_hash(path: Path) -> str:
    return digest(path.read_bytes())

def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")

def decode_candidate(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + ROUTINE_LENGTH]
    if len(code) != ROUTINE_LENGTH or code[0] != 0x3E or code[2:] != TAIL:
        return None
    return {"offset": offset, "blank_tile": code[1], "row_stride": 20,
            "inner_loop_delta": -4, "outer_loop_delta": -12}

def locate(data: bytes) -> list[dict]:
    return [item for offset in range(0x150, min(0x4000, len(data)) - ROUTINE_LENGTH + 1)
            if (item := decode_candidate(data, offset)) is not None]

def source_text() -> str:
    return """SECTION \"ClearScreenArea Reconstruction\", ROM0

ClearScreenArea::
    ld a, \" \"
    ld de, SCREEN_WIDTH
.loopRows
    push hl
    push bc
.loopTiles
    ld [hli], a
    dec c
    jr nz, .loopTiles
    pop bc
    pop hl
    add hl, de
    dec b
    jr nz, .loopRows
    ret
"""

def build(root: Path, rom_dir: Path, game: str, profile_name: str) -> dict:
    profile = common.PROFILES[profile_name]
    catalog_path, releases = common.load_releases(root)
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    source_path = Path("src/clear_screen_area.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    roms = common.rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        matches = locate(data)
        if len(matches) != 1:
            raise ValueError(f"expected one ClearScreenArea in {release_id}, found {len(matches)}")
        match = matches[0]
        if match["blank_tile"] != 0x7F:
            raise ValueError(f"unexpected blank tile in {release_id}")
        offset, end = match["offset"], match["offset"] + ROUTINE_LENGTH
        clear_path = Path(f"analysis/{release_id}-clear-screen.json")
        clear = json.loads((root / clear_path).read_text(encoding="utf-8"))
        if clear["verified_behavior"]["blank_tile_value"] != match["blank_tile"]:
            raise ValueError(f"ClearScreen blank tile differs: {release_id}")
        evidence = {
            "schema_version": 1, "axis": "Disassembly", "profile": profile_name,
            "target": {"release": release_id, "sha256": sha256,
                       "status": release.get("status", "candidate")},
            "origin_reference": index == 0, "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": {"name": "ClearScreenArea", "rom_offset": offset,
                         "bank": 0, "address": offset,
                         "range_end_exclusive": end, "length": ROUTINE_LENGTH,
                         "code_sha256": digest(data[offset:end]),
                         "raw_bytes_published": False},
            "verified_behavior": {"blank_tile_value": match["blank_tile"],
                                  "row_stride": match["row_stride"],
                                  "width_input_register": "C",
                                  "height_input_register": "B",
                                  "tilemap_pointer_register": "HL",
                                  "preserves_row_start_and_dimensions": True,
                                  "inner_loop_relative_delta": -4,
                                  "outer_loop_relative_delta": -12},
            "cross_reference": {"clear_screen_map": clear_path.as_posix(),
                                "clear_screen_map_sha256": file_hash(root / clear_path)},
            "naming_basis": {"repository": profile["repository"],
                             "commit": profile["commit"], "path": profile["path"]},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-clear-screen-area.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": release_id, "language": release["language"],
                        "revision": int(release["revision"]),
                        "status": release.get("status", "candidate"),
                        "sha256": sha256, "origin_reference": index == 0,
                        "address": f"0x{offset:04X}",
                        "blank_tile_value": match["blank_tile"],
                        "code_sha256": evidence["function"]["code_sha256"],
                        "evidence": map_path.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "function": "ClearScreenArea", "profile": profile_name,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/clear-screen-area-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/clear-screen-area-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} ClearScreenArea disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) contain exactly one 18-byte ROM0 routine. "
        "It fills a B-by-C tilemap rectangle with tile 0x7F, restores the row start "
        "and dimensions for each row, and advances by the 20-tile screen width. "
        "Candidate status is retained; maps publish hashes and behavior, not ROM bytes.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_clear_screen_area_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/clear-screen-area-reconstruction.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": "ClearScreenArea", "profile": profile_name,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gen1_clear_screen_area.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)}
                    for path in outputs], "raw_rom_bytes_included": False})
    return summary

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--profile", choices=sorted(common.PROFILES), required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.game, args.profile)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

