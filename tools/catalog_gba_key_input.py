#!/usr/bin/env python3
"""Locate and catalog the InitKeys/ReadKeys Thumb pair in Gen III ROMs."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import disassemble_thumb_cfg


ROM_BASE = 0x08000000
REG_KEYINPUT = 0x04000130
KEYS_MASK = 0x000003FF
INIT_TEMPLATE = (
    0x4906, 0x2005, 0x8008, 0x4906, 0x2028, 0x8008, 0x4905,
    0x2000, 0x8588, 0x85C8, 0x8608, 0x8508, 0x8548, 0x4770,
)
READ_PREFIX = (
    0xB500, 0x480E, 0x8801, 0x4A0E, 0x1C10, 0x1C03, 0x404B, 0x490D,
    0x8D0A, 0x1C18, 0x4390, 0x8548, 0x85C8, 0x8608, 0x1C0A, 0x2B00,
    0xD014, 0x8D90, 0x4298, 0xD111, 0x8E50, 0x3801, 0x8650, 0x0400,
    0x2800, 0xD10E, 0x8613, 0x4804, 0xE009, 0x0000, 0x0130, 0x0400,
    0x03FF, 0x0000, None, None, None, None,
)
READ_DIRECT_SUFFIX = (
    0x4811, 0x8800, 0x8650, 0x8513, 0x8593, 0x4810, 0x7CC0, 0x2802,
    0xD111, 0x8DD1, 0x2380, 0x009B, 0x1C18, 0x4008, 0x2800, 0xD002,
    0x2001, 0x4308, 0x85D0, 0x8D91, 0x1C18, 0x4008, 0x2800, 0xD002,
    0x2001, 0x4308, 0x8590, 0x8DD1, 0x8ED0, 0x4008, 0x2800, 0xD001,
    0x2001, 0x8690, 0xBC01, 0x4700,
)
READ_POINTER_SUFFIX = (
    0x4812, 0x8800, 0x8650, 0x8513, 0x8593, 0x4811, 0x6800, 0x7CC0,
    0x2802, 0xD111, 0x8DD1, 0x2380, 0x009B, 0x1C18, 0x4008, 0x2800,
    0xD002, 0x2001, 0x4308, 0x85D0, 0x8D91, 0x1C18, 0x4008, 0x2800,
    0xD002, 0x2001, 0x4308, 0x8590, 0x8DD1, 0x8ED0, 0x4008, 0x2800,
    0xD001, 0x2001, 0x8690, 0xBC01, 0x4700,
)
PROFILES = {
    "rs": {"access": "direct", "repository": "pret/pokeruby",
           "commit": "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f", "path": "src/main.c"},
    "emerald": {"access": "pointer", "repository": "pret/pokeemerald",
                "commit": "fe1d8e51b265851676b65885818b1f5f62586135", "path": "src/main.c"},
    "frlg": {"access": "pointer", "repository": "pret/pokefirered",
             "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14", "path": "src/main.c"},
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
        if path.is_file() and path.suffix.lower() == ".gba":
            result.setdefault(file_hash(path), path)
    return result


def read_template(access: str) -> tuple[int | None, ...]:
    if access == "direct":
        return READ_PREFIX + READ_DIRECT_SUFFIX
    if access == "pointer":
        return READ_PREFIX + READ_POINTER_SUFFIX
    raise ValueError(f"unsupported access profile: {access}")


def matching_offsets(data: bytes, template: tuple[int | None, ...]) -> list[int]:
    size = len(template) * 2
    prefix = struct.pack("<H", template[0])
    result, start = [], 0
    while True:
        offset = data.find(prefix, start)
        if offset < 0:
            return result
        if offset % 2 == 0 and offset + size <= len(data):
            words = struct.unpack_from(f"<{len(template)}H", data, offset)
            if all(expected is None or actual == expected
                   for actual, expected in zip(words, template)):
                result.append(offset)
        start = offset + 2


def unique_offset(data: bytes, template: tuple[int | None, ...], name: str) -> int:
    matches = matching_offsets(data, template)
    if len(matches) != 1:
        raise ValueError(f"expected one {name} candidate, found {len(matches)}")
    return matches[0]


def source_text(access: str) -> str:
    save_symbol = "gSaveBlock2" if access == "direct" else "gSaveBlock2Ptr"
    pointer_load = "" if access == "direct" else "    ldr r0, [r0]\n"
    return f''' .syntax unified
.thumb

.global InitKeys
.type InitKeys, %function
InitKeys:
    ldr r1, =gKeyRepeatContinueDelay
    movs r0, #5
    strh r0, [r1]
    ldr r1, =gKeyRepeatStartDelay
    movs r0, #40
    strh r0, [r1]
    ldr r1, =gMain
    movs r0, #0
    strh r0, [r1, #44]
    strh r0, [r1, #46]
    strh r0, [r1, #48]
    strh r0, [r1, #40]
    strh r0, [r1, #42]
    bx lr
.size InitKeys, . - InitKeys

.global ReadKeys
.type ReadKeys, %function
ReadKeys:
    push {{lr}}
    ldr r0, =0x04000130
    ldrh r1, [r0]
    ldr r2, =0x000003FF
    movs r0, r2
    movs r3, r0
    eors r3, r1
    ldr r1, =gMain
    ldrh r2, [r1, #40]
    movs r0, r3
    bics r0, r2
    strh r0, [r1, #42]
    strh r0, [r1, #46]
    strh r0, [r1, #48]
    movs r2, r1
    cmp r3, #0
    beq .Lreset_repeat
    ldrh r0, [r2, #44]
    cmp r0, r3
    bne .Lreset_repeat
    ldrh r0, [r2, #50]
    subs r0, #1
    strh r0, [r2, #50]
    lsls r0, r0, #16
    cmp r0, #0
    bne .Lstore_keys
    strh r3, [r2, #48]
    ldr r0, =gKeyRepeatContinueDelay
    b .Lload_repeat
.Lreset_repeat:
    ldr r0, =gKeyRepeatStartDelay
.Lload_repeat:
    ldrh r0, [r0]
    strh r0, [r2, #50]
.Lstore_keys:
    strh r3, [r2, #40]
    strh r3, [r2, #44]
    ldr r0, ={save_symbol}
{pointer_load}    ldrb r0, [r0, #19]
    cmp r0, #2
    bne .Lwatched
    ldrh r1, [r2, #46]
    movs r3, #0x80
    lsls r3, r3, #2
    movs r0, r3
    ands r0, r1
    cmp r0, #0
    beq .Lheld_l
    movs r0, #1
    orrs r0, r1
    strh r0, [r2, #46]
.Lheld_l:
    ldrh r1, [r2, #44]
    movs r0, r3
    ands r0, r1
    cmp r0, #0
    beq .Lwatched
    movs r0, #1
    orrs r0, r1
    strh r0, [r2, #44]
.Lwatched:
    ldrh r1, [r2, #46]
    ldrh r0, [r2, #54]
    ands r0, r1
    cmp r0, #0
    beq .Lreturn
    movs r0, #1
    strh r0, [r2, #52]
.Lreturn:
    pop {{r0}}
    bx r0
.size ReadKeys, . - ReadKeys
'''.lstrip()


def literal_addresses(data: bytes, init_offset: int, read_offset: int,
                      access: str) -> dict[str, str]:
    repeat_continue, repeat_start, g_main = struct.unpack_from("<3I", data, init_offset + 28)
    reg_keyinput, keys_mask, read_g_main, read_repeat_continue = struct.unpack_from(
        "<4I", data, read_offset + 60)
    save_offset = read_offset + (152 if access == "direct" else 156)
    save_options = struct.unpack_from("<I", data, save_offset)[0]
    if (reg_keyinput, keys_mask) != (REG_KEYINPUT, KEYS_MASK):
        raise ValueError("key register or mask literal mismatch")
    if (read_g_main, read_repeat_continue) != (g_main, repeat_continue):
        raise ValueError("InitKeys and ReadKeys globals disagree")
    iwram = [g_main, repeat_continue, repeat_start]
    if access == "pointer":
        iwram.append(save_options)
    if any(not 0x03000000 <= value <= 0x03007FFF for value in iwram):
        raise ValueError("input-state literal leaves IWRAM")
    if access == "direct" and not 0x02000000 <= save_options <= 0x0203FFFF:
        raise ValueError("direct SaveBlock2 literal leaves EWRAM")
    values = {"REG_KEYINPUT": reg_keyinput, "KEYS_MASK": keys_mask,
              "gMain": g_main, "gKeyRepeatContinueDelay": repeat_continue,
              "gKeyRepeatStartDelay": repeat_start,
              ("gSaveBlock2" if access == "direct" else "gSaveBlock2Ptr"): save_options}
    return {key: f"0x{value:08X}" for key, value in values.items()}


def function_record(data: bytes, offset: int, length: int, name: str) -> dict:
    cfg = disassemble_thumb_cfg.trace(data, offset, max_span=length)
    if (cfg["range_end"] != ROM_BASE + offset + length
            or len(cfg["returns"]) != 1 or cfg["calls"]):
        raise ValueError(f"CFG boundary mismatch for {name}")
    return {"name": name, "address": f"0x{ROM_BASE + offset:08X}",
            "range_end_exclusive": f"0x{ROM_BASE + offset + length:08X}",
            "rom_code_range": {"start_offset": offset,
                               "end_offset_exclusive": offset + length,
                               "length": length, "sha256": digest(data[offset:offset + length]),
                               "raw_bytes_published": False},
            "control_flow": {"instruction_halfwords": cfg["instruction_halfwords"],
                             "edge_count": len(cfg["edges"]),
                             "return_count": len(cfg["returns"]), "call_count": 0,
                             "canonical_instruction_bytes_sha256":
                                 cfg["canonical_instruction_bytes_sha256"],
                             "raw_halfwords_omitted": True}}


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    profile = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/key_input.s")
    (root / source_path).write_text(source_text(profile["access"]), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    read_pattern = read_template(profile["access"])
    roms, maps, records = rom_index(rom_dir), [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        init_offset = unique_offset(data, INIT_TEMPLATE, "InitKeys")
        read_offset = unique_offset(data, read_pattern, "ReadKeys")
        if read_offset != init_offset + 40:
            raise ValueError(f"unexpected InitKeys/ReadKeys spacing: {release_id}")
        functions = [function_record(data, init_offset, 28, "InitKeys"),
                     function_record(data, read_offset, len(read_pattern) * 2, "ReadKeys")]
        map_path = Path(f"analysis/{release_id}-key-input-disassembly.json")
        evidence = {"schema_version": 1, "axis": "Disassembly",
                    "target": {"release": release_id, "sha256": sha256},
                    "origin_reference": index == 0, "family_profile": family,
                    "save_options_access": ("direct" if profile["access"] == "direct"
                                            else "pointer_indirect"),
                    "source": source_path.as_posix(), "source_sha256": source_sha256,
                    "functions": functions,
                    "literal_addresses": literal_addresses(data, init_offset, read_offset,
                                                           profile["access"]),
                    "verified_layout": {"init_to_read_delta": 40,
                                        "state_offsets": {"heldKeysRaw": 40,
                                                          "newKeysRaw": 42,
                                                          "heldKeys": 44, "newKeys": 46,
                                                          "newAndRepeatedKeys": 48,
                                                          "keyRepeatCounter": 50,
                                                          "watchedKeysPressed": 52,
                                                          "watchedKeysMask": 54,
                                                          "optionsButtonMode": 19},
                                        "constants": {"repeat_continue_delay": 5,
                                                      "repeat_start_delay": 40,
                                                      "keys_mask": 0x3FF,
                                                      "l_button": 0x200,
                                                      "a_button": 1}},
                    "naming_basis": {"repository": profile["repository"],
                                     "commit": profile["commit"], "path": profile["path"],
                                     "match_kind": "independent Thumb structure and literals"},
                    "raw_rom_bytes_included": False}
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": release_id, "language": release["language"],
                        "revision": release["revision"],
                        "build_kind": release["build_kind"], "sha256": sha256,
                        "origin_reference": index == 0,
                        "functions": [{"name": item["name"], "address": item["address"],
                                       "code_sha256": item["rom_code_range"]["sha256"]}
                                      for item in functions], "evidence": map_path.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "functions": ["InitKeys", "ReadKeys"], "family_profile": family,
               "save_options_access": ("direct" if profile["access"] == "direct"
                                       else "pointer_indirect"),
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/key-input-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/key-input-disassembly.md")
    (root / research_path).write_text(
        f"# {game} key input disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) contain exactly one adjacent InitKeys/ReadKeys "
        f"pair with the `{family}` family structure. ROM-side discovery independently "
        "verifies repeat delays, active-high KEYINPUT conversion, L-equals-A handling, "
        "watched-key state, literal targets and control-flow boundaries. Maps retain "
        "addresses and hashes but publish no ROM bytes or instruction halfwords.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_key_input_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/key-input-disassembly.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "functions": summary["functions"], "family_profile": family,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_key_input.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)}
                    for path in outputs], "raw_rom_bytes_included": False})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--family", choices=sorted(PROFILES), required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.family)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
