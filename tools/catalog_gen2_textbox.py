#!/usr/bin/env python3
"""Locate and catalog Generation II Textbox, border, and palette routines."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen2_clear_screen as common
from catalog_gen2_clear_box import banked_offset


WRAPPER_LENGTH = 9
BORDER_LENGTH = 45
PLACE_CHARS_LENGTH = 6
PALETTE_LENGTH = 26
KOREAN_ROM0_WRAPPER_LENGTH = 23
KOREAN_CORE_LENGTH = 20
PLACE_CHARS = bytes.fromhex("51221520fcc9")
KOREAN_TEXTBOX_HISTORY = {
    "repository": "SakuraiTsubaki/pokegold-kr",
    "commit": "ad83f6ad664f9bc7fcfc8bab63b0f015be9ca0e9",
    "path": "home/text.asm",
    "symbol": "Textbox",
    "target_symbol": "Function1fc0b8",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def signed(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def decode_border(data: bytes, offset: int, address_base: int = 0) -> dict | None:
    code = data[offset:offset + BORDER_LENGTH + PLACE_CHARS_LENGTH]
    if len(code) != BORDER_LENGTH + PLACE_CHARS_LENGTH:
        return None
    helper_offset = offset + BORDER_LENGTH
    helper_address = address_base + BORDER_LENGTH
    expected = (bytes.fromhex("e53e79223ccd") + helper_address.to_bytes(2, "little")
                + bytes.fromhex("3c77e111140019e53e7c223e7fcd")
                + helper_address.to_bytes(2, "little")
                + bytes.fromhex("367ce1111400190520ed3e7d223e7acd")
                + helper_address.to_bytes(2, "little")
                + bytes.fromhex("367ec9") + PLACE_CHARS)
    if code != expected:
        return None
    return {
        "border_offset": offset, "border_length": BORDER_LENGTH,
        "place_chars_offset": helper_offset, "place_chars_length": PLACE_CHARS_LENGTH,
        "place_chars_address": helper_address,
        "tiles": {"top_left": 0x79, "horizontal": 0x7A, "top_right": 0x7B,
                  "vertical": 0x7C, "blank": 0x7F, "bottom_left": 0x7D,
                  "bottom_right": 0x7E},
    }


def decode_palette(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + PALETTE_LENGTH]
    if len(code) != PALETTE_LENGTH:
        return None
    if not (code[0] == 0x11 and code[3:] == bytes.fromhex(
            "1904040c0c3e07c5e5220d20fce111140019c10520f1c9")):
        return None
    delta = int.from_bytes(code[1:3], "little")
    if not 0x0800 <= delta <= 0x0A00:
        return None
    return {"offset": offset, "length": PALETTE_LENGTH,
            "attribute_plane_delta": delta, "palette_value": 7,
            "expands_width_by": 2, "expands_height_by": 2, "row_stride": 20}


def decode_standard(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + WRAPPER_LENGTH]
    if len(code) != WRAPPER_LENGTH:
        return None
    if not (code[:3] == bytes.fromhex("c5e5cd") and code[5:8] == bytes.fromhex("e1c118")):
        return None
    border = int.from_bytes(code[3:5], "little")
    palette = offset + WRAPPER_LENGTH + signed(code[8])
    if border != offset + WRAPPER_LENGTH or palette != border + BORDER_LENGTH + PLACE_CHARS_LENGTH:
        return None
    border_info = decode_border(data, border, border)
    palette_info = decode_palette(data, palette)
    if border_info is None or palette_info is None:
        return None
    return {"offset": offset, "length": WRAPPER_LENGTH,
            "variant": "inline-border-and-palette", "border": border_info,
            "palette": palette_info}


def locate_standard(data: bytes) -> list[dict]:
    return [item for offset in range(0x150, min(0x4000, len(data)) - WRAPPER_LENGTH + 1)
            if (item := decode_standard(data, offset)) is not None]


def decode_farcall_wrapper(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + KOREAN_ROM0_WRAPPER_LENGTH]
    if len(code) != KOREAN_ROM0_WRAPPER_LENGTH:
        return None
    if not (code[:7] == bytes.fromhex("3be5f5e5f80636")
            and code[8:10] == bytes.fromhex("2b36")
            and code[11:13] == bytes.fromhex("2b36")
            and code[14:17] == bytes.fromhex("e1f1cd")
            and code[19:] == bytes.fromhex("333333c9")):
        return None
    bank, address = code[7], (code[10] << 8) | code[13]
    target = banked_offset(bank, address)
    if target is None:
        return None
    return {"offset": offset, "length": KOREAN_ROM0_WRAPPER_LENGTH,
            "target_bank": bank, "target_address": address, "target_offset": target,
            "farcall_helper_address": int.from_bytes(code[17:19], "little")}


def decode_korean_core(data: bytes, offset: int, bank: int, address: int) -> dict | None:
    code = data[offset:offset + KOREAN_CORE_LENGTH]
    if len(code) != KOREAN_CORE_LENGTH:
        return None
    if not (code[:9] == bytes.fromhex("f0d6f5afe0d6c5e5cd")
            and code[11:14] == bytes.fromhex("e1c1cd")
            and code[16:] == bytes.fromhex("f1e0d6c9")):
        return None
    border_address = int.from_bytes(code[9:11], "little")
    palette_address = int.from_bytes(code[14:16], "little")
    border_offset = banked_offset(bank, border_address)
    palette_offset = banked_offset(bank, palette_address)
    if border_offset is None or palette_offset is None:
        return None
    border = decode_border(data, border_offset, border_address)
    palette = decode_palette(data, palette_offset)
    if border is None or palette is None:
        return None
    if palette_offset != border_offset + BORDER_LENGTH + PLACE_CHARS_LENGTH:
        return None
    return {"offset": offset, "address": address, "bank": bank,
            "length": KOREAN_CORE_LENGTH, "state_hram_address": 0xFFD6,
            "border": border, "palette": palette}


def locate_korean(data: bytes) -> list[dict]:
    found = []
    for offset in range(0x150, min(0x4000, len(data)) - KOREAN_ROM0_WRAPPER_LENGTH + 1):
        wrapper = decode_farcall_wrapper(data, offset)
        if wrapper is None:
            continue
        core = decode_korean_core(data, wrapper["target_offset"],
                                  wrapper["target_bank"], wrapper["target_address"])
        if core is not None:
            found.append({"offset": offset, "length": wrapper["length"],
                          "variant": "korean-farcall-suite", "wrapper": wrapper,
                          "core": core, "border": core["border"],
                          "palette": core["palette"]})
    return found


def source_text(profile_name: str) -> str:
    conditional = profile_name == "gold-silver"
    prefix = '''SECTION "Textbox Reconstruction", ROM0

'''
    if conditional:
        prefix += '''IF DEF(_KOREAN)
Textbox::
    farcall_reg KoreanTextbox
    ret

SECTION "Korean Textbox Reconstruction", ROMX[$40B8], BANK[$7F]

KoreanTextbox::
    ldh a, [$d6]
    push af
    xor a
    ldh [$d6], a
    push bc
    push hl
    call TextboxBorder
    pop hl
    pop bc
    call TextboxPalette
    pop af
    ldh [$d6], a
    ret
ELSE
'''
    prefix += '''Textbox::
    push bc
    push hl
    call TextboxBorder
    pop hl
    pop bc
    jr TextboxPalette
'''
    if conditional:
        prefix += "ENDC\n"
    return prefix + '''
TextboxBorder::
    push hl
    ld a, $79
    ld [hli], a
    inc a
    call .PlaceChars
    inc a
    ld [hl], a
    pop hl
    ld de, SCREEN_WIDTH
    add hl, de
.row
    push hl
    ld a, $7c
    ld [hli], a
    ld a, " "
    call .PlaceChars
    ld [hl], $7c
    pop hl
    ld de, SCREEN_WIDTH
    add hl, de
    dec b
    jr nz, .row
    ld a, $7d
    ld [hli], a
    ld a, $7a
    call .PlaceChars
    ld [hl], $7e
    ret
.PlaceChars
    ld d, c
.loop
    ld [hli], a
    dec d
    jr nz, .loop
    ret

TextboxPalette::
    ld de, wAttrmap - wTilemap
    add hl, de
    inc b
    inc b
    inc c
    inc c
    ld a, PAL_BG_TEXT
.col
    push bc
    push hl
.row
    ld [hli], a
    dec c
    jr nz, .row
    pop hl
    ld de, SCREEN_WIDTH
    add hl, de
    pop bc
    dec b
    jr nz, .col
    ret
'''


def build(root: Path, rom_dir: Path, game: str, profile_name: str) -> dict:
    profile = common.PROFILES[profile_name]
    catalog_path = Path("research/releases.csv")
    releases = common.load_releases(root / catalog_path)
    source_path = Path("src/textbox.asm")
    (root / source_path).write_text(source_text(profile_name), encoding="utf-8", newline="\n")
    roms = common.rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        rid, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {rid}")
        data = roms[sha256].read_bytes()
        korean = release["language"] == "Korean"
        matches = locate_korean(data) if korean else locate_standard(data)
        if len(matches) != 1:
            raise ValueError(f"expected one Textbox suite in {rid}, found {len(matches)}")
        match = matches[0]
        border, palette = match["border"], match["palette"]
        functions = {
            "Textbox": {"rom_offset": match["offset"], "bank": 0,
                        "address": match["offset"], "length": match["length"],
                        "code_sha256": digest(data[match["offset"]:match["offset"] + match["length"]])},
            "TextboxBorder": {"rom_offset": border["border_offset"],
                              "length": border["border_length"],
                              "code_sha256": digest(data[border["border_offset"]:border["border_offset"] + border["border_length"]])},
            "PlaceChars": {"rom_offset": border["place_chars_offset"],
                           "length": border["place_chars_length"],
                           "code_sha256": digest(data[border["place_chars_offset"]:border["place_chars_offset"] + border["place_chars_length"]])},
            "TextboxPalette": {"rom_offset": palette["offset"], "length": palette["length"],
                               "code_sha256": digest(data[palette["offset"]:palette["offset"] + palette["length"]])},
        }
        if korean:
            core = match["core"]
            functions["Textbox"]["farcall"] = match["wrapper"]
            functions["KoreanTextbox"] = {"rom_offset": core["offset"], "bank": core["bank"],
                                           "address": core["address"], "length": core["length"],
                                           "code_sha256": digest(data[core["offset"]:core["offset"] + core["length"]]),
                                           "state_hram_address": core["state_hram_address"]}
        clear_box_path = Path(f"analysis/{rid}-clear-box.json")
        clear_box = json.loads((root / clear_box_path).read_text(encoding="utf-8"))
        if clear_box["target"]["sha256"] != sha256:
            raise ValueError(f"ClearBox identity differs: {rid}")
        evidence = {
            "schema_version": 1, "axis": "Disassembly", "profile": profile_name,
            "target": {"release": rid, "sha256": sha256,
                       "status": release.get("status", "candidate")},
            "origin_reference": index == 0, "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path), "variant": match["variant"],
            "functions": functions,
            "verified_behavior": {"border_tiles": border["tiles"],
                                  "attribute_plane_delta": palette["attribute_plane_delta"],
                                  "palette_value": palette["palette_value"],
                                  "palette_width_expansion": 2,
                                  "palette_height_expansion": 2,
                                  "row_stride": 20,
                                  "width_input_register": "C",
                                  "height_input_register": "B",
                                  "tilemap_pointer_register": "HL"},
            "cross_reference": {"clear_box_map": clear_box_path.as_posix(),
                                "clear_box_map_sha256": file_hash(root / clear_box_path)},
            "naming_basis": {"primary": {"repository": profile["repository"],
                                           "commit": profile["commit"], "path": profile["path"]},
                             "korean_history": KOREAN_TEXTBOX_HISTORY if korean else None},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{rid}-textbox.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": rid, "language": release["language"],
                        "revision": int(release["revision"]),
                        "status": release.get("status", "candidate"), "sha256": sha256,
                        "origin_reference": index == 0, "variant": match["variant"],
                        "address": f"0x{match['offset']:04X}",
                        "attribute_plane_delta": f"0x{palette['attribute_plane_delta']:04X}",
                        "evidence": map_path.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "functions": ["Textbox", "TextboxBorder", "PlaceChars", "TextboxPalette"],
               "profile": profile_name, "origin_reference": releases[0]["id"],
               "release_count": len(records), "source": source_path.as_posix(),
               "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/textbox-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/textbox-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} Textbox disassembly\n\n`{releases[0]['id']}` is the Japanese origin "
        f"reference. All {len(records)} cataloged releases ({languages}) verify the box "
        "border, repeated-character helper, and expanded palette rectangle. Korean "
        "Gold/Silver use a ROM0 farcall wrapper and bank 0x7F orchestration core; their "
        "border and palette bodies remain independently hashed. Candidate status is "
        "retained and no ROM bytes are published.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_textbox_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/textbox-reconstruction.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "functions": summary["functions"], "profile": profile_name,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gen2_textbox.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": p.as_posix(), "sha256": file_hash(root / p)} for p in outputs],
        "raw_rom_bytes_included": False})
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

