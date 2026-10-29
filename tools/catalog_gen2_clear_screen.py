#!/usr/bin/env python3
"""Catalog the Generation II ClearTilemap and ClearScreen pair."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


SCREEN_AREA = 20 * 18
GLOBAL_PAIR_LENGTH = 32
KOREAN_PAIR_LENGTH = 34
PROFILES = {
    "gold-silver": {"repository": "pret/pokegold",
                    "commit": "ef0201d8daf47e8b3ea1518eacf890f37d4cd5e8",
                    "path": "home/text.asm"},
    "crystal": {"repository": "pret/pokecrystal",
                "commit": "3bc8daa4173e96a7f4011dad3922eb6fa5dad5c6",
                "path": "home/text.asm"},
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def rom_index(directory: Path) -> dict[str, Path]:
    result = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in {".gb", ".gbc"}:
            result.setdefault(file_hash(path), path)
    return result


def load_releases(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        releases = list(csv.DictReader(handle))
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("release catalog must begin with Japanese origin")
    languages = [item["language"] for item in releases]
    if "Korean" in languages and languages.index("Korean") > languages.index("English"):
        raise ValueError("Korean release must precede English when available")
    return releases


def signed(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def decode_global_candidate(data: bytes, offset: int, byte_fill: int) -> dict | None:
    code = data[offset:offset + GLOBAL_PAIR_LENGTH]
    if len(code) != GLOBAL_PAIR_LENGTH:
        return None
    if not (code[0] == 0x21 and code[3] == 0x3E
            and code[5:8] == bytes.fromhex("016801")
            and code[8] == 0xCD and int.from_bytes(code[9:11], "little") == byte_fill
            and code[11:16] == bytes.fromhex("f040cb7fc8") and code[16] == 0xC3
            and code[19] == 0x3E and code[21] == 0x21
            and code[24:27] == bytes.fromhex("016801")
            and code[27] == 0xCD and int.from_bytes(code[28:30], "little") == byte_fill
            and code[30] == 0x18 and offset + 32 + signed(code[31]) == offset):
        return None
    tilemap = int.from_bytes(code[1:3], "little")
    wait_bg_map = int.from_bytes(code[17:19], "little")
    attrmap = int.from_bytes(code[22:24], "little")
    if not (0xC000 <= tilemap <= 0xDFFF and 0xC000 <= attrmap <= 0xDFFF
            and 0x0100 <= wait_bg_map < 0x4000):
        return None
    return {"offset": offset, "variant": "global-inline-wait",
            "pair_length": GLOBAL_PAIR_LENGTH,
            "clear_tilemap_length": 19, "clear_screen_length": 13,
            "tilemap_address": tilemap,
            "blank_tile": code[4], "wait_bg_map_address": wait_bg_map,
            "palette_value": code[20], "attrmap_address": attrmap,
            "clear_screen_offset": offset + 19}


def decode_korean_candidate(data: bytes, offset: int, byte_fill: int) -> dict | None:
    code = data[offset:offset + KOREAN_PAIR_LENGTH]
    if len(code) != KOREAN_PAIR_LENGTH:
        return None
    if not (code[0] == 0x21 and code[3] == 0x3E
            and code[5:8] == bytes.fromhex("016801")
            and code[8] == 0xCD and int.from_bytes(code[9:11], "little") == byte_fill
            and code[11:16] == bytes.fromhex("f040cb7fc9")
            and code[16] == 0x3E and code[18] == 0x21
            and code[21:24] == bytes.fromhex("016801")
            and code[24] == 0xCD and int.from_bytes(code[25:27], "little") == byte_fill
            and code[27] == 0xCD and int.from_bytes(code[28:30], "little") == offset
            and code[30] == 0xC8 and code[31] == 0xC3):
        return None
    tilemap = int.from_bytes(code[1:3], "little")
    attrmap = int.from_bytes(code[19:21], "little")
    wait_bg_map = int.from_bytes(code[32:34], "little")
    if not (0xC000 <= tilemap <= 0xDFFF and 0xC000 <= attrmap <= 0xDFFF
            and 0x0100 <= wait_bg_map < 0x4000):
        return None
    return {"offset": offset, "variant": "korean-split-wait",
            "pair_length": KOREAN_PAIR_LENGTH,
            "clear_tilemap_length": 16, "clear_screen_length": 18,
            "tilemap_address": tilemap, "blank_tile": code[4],
            "wait_bg_map_address": wait_bg_map, "palette_value": code[17],
            "attrmap_address": attrmap, "clear_screen_offset": offset + 16}


def decode_candidate(data: bytes, offset: int, byte_fill: int) -> dict | None:
    return (decode_global_candidate(data, offset, byte_fill)
            or decode_korean_candidate(data, offset, byte_fill))


def locate(data: bytes, byte_fill: int) -> list[dict]:
    return [item for offset in range(0x150, min(0x4000, len(data)) - KOREAN_PAIR_LENGTH + 1)
            if (item := decode_candidate(data, offset, byte_fill)) is not None]


def source_text(profile_name: str) -> str:
    prefix = """SECTION \"Clear Screen Reconstruction\", ROM0

ClearTilemap::
    ld hl, wTilemap
    ld a, \" \"
    ld bc, SCREEN_AREA
    call ByteFill
    ldh a, [rLCDC]
    bit B_LCDC_ENABLE, a
"""
    if profile_name == "gold-silver":
        return prefix + """IF DEF(_KOREAN)
    ret

ClearScreen::
    ld a, PAL_BG_TEXT
    ld hl, wAttrmap
    ld bc, SCREEN_AREA
    call ByteFill
    call ClearTilemap
    ret z
    jp WaitBGMap
ELSE
    ret z
    jp WaitBGMap

ClearScreen::
    ld a, PAL_BG_TEXT
    ld hl, wAttrmap
    ld bc, SCREEN_AREA
    call ByteFill
    jr ClearTilemap
ENDC
"""
    return prefix + """    ret z
    jp WaitBGMap

ClearScreen::
    ld a, PAL_BG_TEXT
    ld hl, wAttrmap
    ld bc, SCREEN_AREA
    call ByteFill
    jr ClearTilemap
"""


def build(root: Path, rom_dir: Path, game: str, profile_name: str) -> dict:
    profile = PROFILES[profile_name]
    catalog_path = Path("research/releases.csv")
    releases = load_releases(root / catalog_path)
    source_path = Path("src/clear_screen.asm")
    (root / source_path).write_text(source_text(profile_name), encoding="utf-8", newline="\n")
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        byte_fill_path = Path(f"analysis/{release_id}-byte-fill.json")
        byte_fill_map = json.loads((root / byte_fill_path).read_text(encoding="utf-8"))
        if byte_fill_map["target"]["sha256"] != sha256:
            raise ValueError(f"ByteFill identity differs: {release_id}")
        byte_fill = byte_fill_map["function"]["address"]
        data = roms[sha256].read_bytes()
        matches = locate(data, byte_fill)
        if len(matches) != 1:
            raise ValueError(f"expected one clear-screen pair in {release_id}, found {len(matches)}")
        match = matches[0]
        start, end = match["offset"], match["offset"] + match["pair_length"]
        clear_start = match["clear_screen_offset"]
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256,
                       "status": release["status"]},
            "origin_reference": index == 0,
            "axis": "Disassembly", "profile": profile_name,
            "source": source_path.as_posix(), "source_sha256": file_hash(root / source_path),
            "functions": {
                "ClearTilemap": {"rom_offset": start, "bank": 0, "address": start,
                                 "range_end_exclusive": clear_start,
                                 "length": match["clear_tilemap_length"],
                                 "code_sha256": digest(data[start:clear_start]),
                                 "calls": [{"name": "ByteFill", "address": byte_fill}],
                                 "wait_behavior": ("returns LCD-enable Z state to ClearScreen"
                                                   if match["variant"] == "korean-split-wait"
                                                   else "returns if LCD is off, otherwise tail-jumps"),
                                 "wait_bg_map_address": match["wait_bg_map_address"]},
                "ClearScreen": {"rom_offset": clear_start, "bank": 0,
                                "address": clear_start, "range_end_exclusive": end,
                                "length": match["clear_screen_length"],
                                "code_sha256": digest(data[clear_start:end]),
                                "calls": [{"name": "ByteFill", "address": byte_fill}],
                                "clear_tilemap_transfer": {
                                    "name": "ClearTilemap", "address": start,
                                    "kind": ("call" if match["variant"] == "korean-split-wait"
                                             else "tail-branch")},
                                "wait_bg_map_transfer": (
                                    {"kind": "conditional-tail-jump",
                                     "address": match["wait_bg_map_address"]}
                                    if match["variant"] == "korean-split-wait" else None)},
            },
            "verified_behavior": {
                "variant": match["variant"],
                "tilemap_address": match["tilemap_address"],
                "attrmap_address": match["attrmap_address"],
                "blank_tile_value": match["blank_tile"],
                "background_palette_value": match["palette_value"],
                "filled_byte_count_each": SCREEN_AREA,
                "lcd_enable_register": "rLCDC", "lcd_enable_bit": 7,
            },
            "cross_reference": {"byte_fill_map": byte_fill_path.as_posix(),
                                "byte_fill_map_sha256": file_hash(root / byte_fill_path)},
            "naming_basis": {"repository": profile["repository"],
                             "commit": profile["commit"], "path": profile["path"]},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-clear-screen.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": release_id, "language": release["language"],
                        "revision": int(release["revision"]), "status": release["status"],
                        "sha256": sha256, "origin_reference": index == 0,
                        "variant": match["variant"],
                        "clear_tilemap_address": f"0x{start:04X}",
                        "clear_screen_address": f"0x{clear_start:04X}",
                        "tilemap_address": f"0x{match['tilemap_address']:04X}",
                        "attrmap_address": f"0x{match['attrmap_address']:04X}",
                        "blank_tile_value": match["blank_tile"],
                        "evidence": map_path.as_posix()})

    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "functions": ["ClearTilemap", "ClearScreen"], "profile": profile_name,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/clear-screen-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/clear-screen-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} ClearTilemap and ClearScreen disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) contain exactly one ROM0 pair that calls "
        "the independently mapped ByteFill routine. ClearScreen clears the 20x18 "
        "attribute map and transfers to ClearTilemap; ClearTilemap clears the tilemap. "
        "Global builds keep the conditional WaitBGMap tail in ClearTilemap, while the "
        "Korean Gold/Silver builds return the LCD state and perform that wait in "
        "ClearScreen. Maps publish operands, "
        "control-flow targets and hashes, never ROM bytes. Candidate status is retained.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_clear_screen_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/clear-screen-reconstruction.json", {
        "schema_version": 1, "game": game, "axis": "Disassembly",
        "functions": ["ClearTilemap", "ClearScreen"], "profile": profile_name,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gen2_clear_screen.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)}
                    for path in outputs], "raw_rom_bytes_included": False})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.game, args.profile)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
