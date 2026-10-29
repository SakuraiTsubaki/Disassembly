#!/usr/bin/env python3
"""Locate and catalog Generation II ClearBox implementations."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen2_clear_screen as common


ROUTINE_LENGTH = 18
KOREAN_WRAPPER_LENGTH = 23
KOREAN_CORE_LENGTH = 43
GS_SIGNATURE = bytes.fromhex("3e7f111400e5c5220d20fcc1e1190520f4c9")
CRYSTAL_SIGNATURE = bytes.fromhex("3e7fc5e5220d20fce101140009c10520f1c9")
KOREAN_PREFIX = bytes.fromhex(
    "e5c511400919111400e5c5cb9e230d20fac1e1190520f2c1e1")
KOREAN_HISTORY = {
    "repository": "SakuraiTsubaki/pokegold-kr",
    "commit": "ad83f6ad664f9bc7fcfc8bab63b0f015be9ca0e9",
    "path": "home/text.asm",
    "symbol": "ClearBox",
    "target_symbol": "Function1fc08d",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def decode_standard_candidate(data: bytes, offset: int, variant: str) -> dict | None:
    signature = GS_SIGNATURE if variant == "gold-silver" else CRYSTAL_SIGNATURE
    if data[offset:offset + ROUTINE_LENGTH] != signature:
        return None
    return {
        "offset": offset,
        "length": ROUTINE_LENGTH,
        "variant": "gold-silver-inline" if variant == "gold-silver" else "crystal-fallthrough",
        "blank_tile": 0x7F,
        "row_stride": 20,
        "width_register": "C",
        "height_register": "B",
        "pointer_register": "HL",
        "fill_entry_offset": offset if variant == "gold-silver" else offset + 2,
    }


def locate_standard(data: bytes, variant: str) -> list[dict]:
    return [item for offset in range(0x150, len(data) - ROUTINE_LENGTH + 1)
            if (item := decode_standard_candidate(data, offset, variant)) is not None]


def decode_korean_core(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + KOREAN_CORE_LENGTH]
    if len(code) != KOREAN_CORE_LENGTH:
        return None
    if code[:len(KOREAN_PREFIX)] != KOREAN_PREFIX or code[len(KOREAN_PREFIX):] != GS_SIGNATURE:
        return None
    return {
        "offset": offset,
        "length": KOREAN_CORE_LENGTH,
        "variant": "korean-attribute-and-tile-fill",
        "blank_tile": 0x7F,
        "row_stride": 20,
        "attribute_plane_delta": 0x0940,
        "attribute_bit_cleared": 3,
        "width_register": "C",
        "height_register": "B",
        "pointer_register": "HL",
        "tile_fill_offset": offset + len(KOREAN_PREFIX),
    }


def banked_offset(bank: int, address: int) -> int | None:
    if bank == 0 and 0 <= address < 0x4000:
        return address
    if bank > 0 and 0x4000 <= address < 0x8000:
        return bank * 0x4000 + address - 0x4000
    return None


def decode_korean_wrapper(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + KOREAN_WRAPPER_LENGTH]
    if len(code) != KOREAN_WRAPPER_LENGTH:
        return None
    if not (code[:7] == bytes.fromhex("3be5f5e5f80636")
            and code[8:10] == bytes.fromhex("2b36")
            and code[11:13] == bytes.fromhex("2b36")
            and code[14:17] == bytes.fromhex("e1f1cd")
            and code[19:] == bytes.fromhex("333333c9")):
        return None
    bank = code[7]
    address = (code[10] << 8) | code[13]
    target_offset = banked_offset(bank, address)
    if target_offset is None or decode_korean_core(data, target_offset) is None:
        return None
    return {
        "offset": offset,
        "length": KOREAN_WRAPPER_LENGTH,
        "variant": "korean-farcall-wrapper",
        "target_bank": bank,
        "target_address": address,
        "target_offset": target_offset,
        "farcall_helper_address": int.from_bytes(code[17:19], "little"),
    }


def locate_korean(data: bytes) -> list[dict]:
    return [item for offset in range(0x150, min(0x4000, len(data)) - KOREAN_WRAPPER_LENGTH + 1)
            if (item := decode_korean_wrapper(data, offset)) is not None]


def source_text(profile_name: str) -> str:
    if profile_name == "crystal":
        return '''SECTION "ClearBox Reconstruction", ROM0

ClearBox::
    ld a, " "
    ; fallthrough
FillBoxWithByte::
.row
    push bc
    push hl
.col
    ld [hli], a
    dec c
    jr nz, .col
    pop hl
    ld bc, SCREEN_WIDTH
    add hl, bc
    pop bc
    dec b
    jr nz, .row
    ret
'''
    return '''SECTION "ClearBox Reconstruction", ROM0

IF DEF(_KOREAN)
ClearBox::
    farcall_reg KoreanClearBox
    ret

SECTION "Korean ClearBox Reconstruction", ROMX[$408D], BANK[$7F]

KoreanClearBox::
    push hl
    push bc
    ld de, $0940
    add hl, de
    ld de, SCREEN_WIDTH
.attributeRow
    push hl
    push bc
.attributeTile
    res 3, [hl]
    inc hl
    dec c
    jr nz, .attributeTile
    pop bc
    pop hl
    add hl, de
    dec b
    jr nz, .attributeRow
    pop bc
    pop hl
    ld a, " "
    ld de, SCREEN_WIDTH
.tileRow
    push hl
    push bc
.tile
    ld [hli], a
    dec c
    jr nz, .tile
    pop bc
    pop hl
    add hl, de
    dec b
    jr nz, .tileRow
    ret
ELSE
ClearBox::
    ld a, " "
    ld de, SCREEN_WIDTH
.row
    push hl
    push bc
.col
    ld [hli], a
    dec c
    jr nz, .col
    pop bc
    pop hl
    add hl, de
    dec b
    jr nz, .row
    ret
ENDC
'''


def build(root: Path, rom_dir: Path, game: str, profile_name: str) -> dict:
    profile = common.PROFILES[profile_name]
    catalog_path = Path("research/releases.csv")
    releases = common.load_releases(root / catalog_path)
    source_path = Path("src/clear_box.asm")
    (root / source_path).write_text(source_text(profile_name), encoding="utf-8", newline="\n")
    roms = common.rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        is_korean = release["language"] == "Korean"
        if is_korean:
            if profile_name != "gold-silver":
                raise ValueError(f"unexpected Korean ClearBox profile: {release_id}")
            matches = locate_korean(data)
        else:
            matches = locate_standard(data, profile_name)
        if len(matches) != 1:
            raise ValueError(f"expected one ClearBox in {release_id}, found {len(matches)}")
        match = matches[0]
        start, end = match["offset"], match["offset"] + match["length"]
        clear_path = Path(f"analysis/{release_id}-clear-screen.json")
        clear_map = json.loads((root / clear_path).read_text(encoding="utf-8"))
        if clear_map["target"]["sha256"] != sha256:
            raise ValueError(f"ClearScreen identity differs: {release_id}")
        if clear_map["verified_behavior"]["blank_tile_value"] != 0x7F:
            raise ValueError(f"ClearScreen blank tile differs: {release_id}")
        function = {
            "name": "ClearBox", "rom_offset": start, "bank": 0,
            "address": start, "range_end_exclusive": end,
            "length": match["length"], "code_sha256": digest(data[start:end]),
            "raw_bytes_published": False,
        }
        behavior = {
            "variant": match["variant"], "blank_tile_value": 0x7F,
            "row_stride": 20, "width_input_register": "C",
            "height_input_register": "B", "tilemap_pointer_register": "HL",
            "preserves_row_start_and_dimensions": True,
        }
        extra_functions = {}
        if is_korean:
            core_start = match["target_offset"]
            core = decode_korean_core(data, core_start)
            assert core is not None
            core_end = core_start + core["length"]
            function["farcall"] = {
                "helper_address": match["farcall_helper_address"],
                "target_bank": match["target_bank"],
                "target_address": match["target_address"],
                "target_rom_offset": core_start,
            }
            extra_functions["KoreanClearBox"] = {
                "rom_offset": core_start, "bank": match["target_bank"],
                "address": match["target_address"],
                "range_end_exclusive": core_end, "length": core["length"],
                "code_sha256": digest(data[core_start:core_end]),
                "tile_fill_offset": core["tile_fill_offset"],
                "raw_bytes_published": False,
            }
            behavior.update({
                "attribute_plane_delta": core["attribute_plane_delta"],
                "attribute_bit_cleared": core["attribute_bit_cleared"],
                "attribute_rectangle_matches_tile_rectangle": True,
            })
        elif profile_name == "crystal":
            extra_functions["FillBoxWithByte"] = {
                "rom_offset": match["fill_entry_offset"], "bank": 0,
                "address": match["fill_entry_offset"],
                "entry_kind": "ClearBox fallthrough after loading blank tile",
                "caller_supplies_fill_byte_in": "A",
            }
        evidence = {
            "schema_version": 1, "axis": "Disassembly", "profile": profile_name,
            "target": {"release": release_id, "sha256": sha256,
                       "status": release.get("status", "candidate")},
            "origin_reference": index == 0, "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path), "function": function,
            "related_functions": extra_functions, "verified_behavior": behavior,
            "cross_reference": {"clear_screen_map": clear_path.as_posix(),
                                "clear_screen_map_sha256": file_hash(root / clear_path)},
            "naming_basis": {"primary": {"repository": profile["repository"],
                                           "commit": profile["commit"],
                                           "path": profile["path"]},
                             "korean_history": KOREAN_HISTORY if is_korean else None},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-clear-box.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id, "language": release["language"],
            "revision": int(release["revision"]),
            "status": release.get("status", "candidate"), "sha256": sha256,
            "origin_reference": index == 0, "variant": match["variant"],
            "address": f"0x{start:04X}", "code_sha256": function["code_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": "ClearBox", "profile": profile_name,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "source": source_path.as_posix(), "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/clear-box-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/clear-box-reconstruction.md")
    korean_note = (
        " Korean Gold/Silver use a ROM0 farcall wrapper and a bank 0x7F core that "
        "first clears attribute bit 3 at HL+0x0940 over the same B-by-C rectangle."
        if any(item["language"] == "Korean" for item in records) else "")
    crystal_note = (
        " Crystal loads the blank tile and falls through to FillBoxWithByte."
        if profile_name == "crystal" else "")
    (root / research_path).write_text(
        f"# {game} ClearBox disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) have one verified ClearBox path. The routine "
        "fills a B-by-C rectangle at HL, preserving the row start and dimensions while "
        "advancing by the 20-tile screen width."
        f"{korean_note}{crystal_note} Candidate status is retained; maps publish "
        "control-flow, operands, provenance and hashes, never ROM bytes.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_clear_box_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/clear-box-reconstruction.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": "ClearBox", "profile": profile_name,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gen2_clear_box.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)}
                    for path in outputs], "raw_rom_bytes_included": False,
    })
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

