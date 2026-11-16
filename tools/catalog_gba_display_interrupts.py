#!/usr/bin/env python3
"""Disassemble HBlank, VCount and Serial interrupt handlers in Gen III ROMs."""
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
INTR_CHECK = 0x03007FF8
REG_VCOUNT = 0x04000006
PROFILES = {
    "rs": {"repository": "pret/pokeruby",
           "commit": "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f", "path": "src/main.c"},
    "emerald": {"repository": "pret/pokeemerald",
                "commit": "fe1d8e51b265851676b65885818b1f5f62586135", "path": "src/main.c"},
    "frlg": {"repository": "pret/pokefirered",
             "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14", "path": "src/main.c"},
}
COMMON_HBLANK = (
    0xB510, 0x4C09, 0x6920, 0x2800, 0xD001, None, None, 0x4A07, 0x8810,
    0x2102, 0x4308, 0x8010, 0x8BA0, 0x8BA2, 0x4301, 0x83A1, 0xBC10, 0xBC01, 0x4700,
)
COMMON_SERIAL = (
    0xB510, 0x4C09, 0x69A0, 0x2800, 0xD001, None, None, 0x4A07, 0x8810,
    0x2180, 0x4308, 0x8010, 0x8BA0, 0x8BA2, 0x4301, 0x83A1, 0xBC10, 0xBC01, 0x4700,
)
RS_VCOUNT = (
    0xB510, 0x4C09, 0x6960, 0x2800, 0xD001, None, None, 0x4A07, 0x8810,
    0x2104, 0x4308, 0x8010, 0x8BA0, 0x8BA2, 0x4301, 0x83A1, 0xBC10, 0xBC01, 0x4700,
)
EMERALD_VCOUNT = (
    0xB510, 0x4C0A, 0x6960, 0x2800, 0xD001, None, None, None, None, 0x4A07,
    0x8810, 0x2104, 0x4308, 0x8010, 0x8BA0, 0x8BA2, 0x4301, 0x83A1, 0xBC10, 0xBC01, 0x4700,
)
FRLG_VCOUNT = (
    0xB500, 0x4909, 0x4809, 0x8800, 0x7008, None, None, 0x4A08, 0x8810,
    0x2104, 0x4308, 0x8010, 0x4806, 0x8B82, 0x8B83, 0x4311, 0x8381, 0xBC01, 0x4700,
)


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


def is_bl(first: int, second: int) -> bool:
    return first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def matches_template(words: tuple[int, ...], template: tuple[int | None, ...]) -> bool:
    if len(words) != len(template):
        return False
    if any(expected is not None and words[index] != expected
           for index, expected in enumerate(template)):
        return False
    masked = [index for index, expected in enumerate(template) if expected is None]
    return len(masked) % 2 == 0 and all(
        masked[index + 1] == masked[index] + 1
        and is_bl(words[masked[index]], words[masked[index + 1]])
        for index in range(0, len(masked), 2))


def matching_offsets(data: bytes, template: tuple[int | None, ...]) -> list[int]:
    size, prefix = len(template) * 2, struct.pack("<H", template[0])
    matches, start = [], 0
    while True:
        offset = data.find(prefix, start)
        if offset < 0:
            return matches
        if offset % 2 == 0 and offset + size <= len(data):
            words = struct.unpack_from(f"<{len(template)}H", data, offset)
            if matches_template(words, template):
                matches.append(offset)
        start = offset + 2


def unique_offset(data: bytes, template: tuple[int | None, ...], name: str) -> int:
    matches = matching_offsets(data, template)
    if len(matches) != 1:
        raise ValueError(f"expected one {name} candidate, found {len(matches)}")
    return matches[0]


def profile_templates(profile: str) -> tuple[tuple[int | None, ...], ...]:
    if profile == "rs":
        return COMMON_HBLANK, RS_VCOUNT, COMMON_SERIAL
    if profile == "emerald":
        return COMMON_HBLANK, EMERALD_VCOUNT, COMMON_SERIAL
    if profile == "frlg":
        return COMMON_HBLANK, FRLG_VCOUNT, COMMON_SERIAL
    raise ValueError(f"unsupported profile: {profile}")


def source_text(profile: str) -> str:
    if profile not in PROFILES:
        raise ValueError(f"unsupported profile: {profile}")
    common = '''.syntax unified
.thumb

.macro SET_INTR_FLAG flag
    ldr r2, =0x03007FF8
    ldrh r0, [r2]
    movs r1, #\\flag
    orrs r0, r1
    strh r0, [r2]
.endm

.macro SET_MAIN_INTR_FLAG base
    ldrh r0, [\\base, #28]
    ldrh r2, [\\base, #28]
    orrs r1, r0
    strh r1, [\\base, #28]
.endm

.global HBlankIntr
.type HBlankIntr, %function
HBlankIntr:
    push {r4, lr}
    ldr r4, =gMain
    ldr r0, [r4, #16]
    cmp r0, #0
    beq .LHBlankNoCallback
    bl CallHBlankCallback
.LHBlankNoCallback:
    SET_INTR_FLAG 2
    SET_MAIN_INTR_FLAG r4
    pop {r4}
    pop {r0}
    bx r0
.size HBlankIntr, . - HBlankIntr

'''
    if profile == "rs":
        vcount = '''.global VCountIntr
.type VCountIntr, %function
VCountIntr:
    push {r4, lr}
    ldr r4, =gMain
    ldr r0, [r4, #20]
    cmp r0, #0
    beq .LVCountNoCallback
    bl CallVCountCallback
.LVCountNoCallback:
    SET_INTR_FLAG 4
    SET_MAIN_INTR_FLAG r4
    pop {r4}
    pop {r0}
    bx r0
.size VCountIntr, . - VCountIntr

'''
    elif profile == "emerald":
        vcount = '''.global VCountIntr
.type VCountIntr, %function
VCountIntr:
    push {r4, lr}
    ldr r4, =gMain
    ldr r0, [r4, #20]
    cmp r0, #0
    beq .LVCountNoCallback
    bl CallVCountCallback
.LVCountNoCallback:
    bl m4aSoundVSync
    SET_INTR_FLAG 4
    SET_MAIN_INTR_FLAG r4
    pop {r4}
    pop {r0}
    bx r0
.size VCountIntr, . - VCountIntr

'''
    else:
        vcount = '''.global VCountIntr
.type VCountIntr, %function
VCountIntr:
    push {lr}
    ldr r1, =sVcountAtIntr
    ldr r0, =0x04000006
    ldrh r0, [r0]
    strb r0, [r1]
    bl m4aSoundVSync
    SET_INTR_FLAG 4
    ldr r0, =gMain
    ldrh r2, [r0, #28]
    ldrh r3, [r0, #28]
    orrs r1, r2
    strh r1, [r0, #28]
    pop {r0}
    bx r0
.size VCountIntr, . - VCountIntr

'''
    serial = '''.global SerialIntr
.type SerialIntr, %function
SerialIntr:
    push {r4, lr}
    ldr r4, =gMain
    ldr r0, [r4, #24]
    cmp r0, #0
    beq .LSerialNoCallback
    bl CallSerialCallback
.LSerialNoCallback:
    SET_INTR_FLAG 0x80
    SET_MAIN_INTR_FLAG r4
    pop {r4}
    pop {r0}
    bx r0
.size SerialIntr, . - SerialIntr
'''
    return common + vcount + serial


def literal_values(data: bytes, offsets: dict[str, int], profile: str) -> dict[str, str]:
    common = struct.unpack_from("<2I", data, offsets["HBlankIntr"] + 40)
    serial = struct.unpack_from("<2I", data, offsets["SerialIntr"] + 40)
    if common[1] != INTR_CHECK or serial != common:
        raise ValueError("HBlank/Serial literal validation failed")
    values = {"gMain": common[0], "INTR_CHECK": common[1]}
    if profile == "rs":
        if struct.unpack_from("<2I", data, offsets["VCountIntr"] + 40) != common:
            raise ValueError("Ruby/Sapphire VCount literals differ")
    elif profile == "emerald":
        if struct.unpack_from("<2I", data, offsets["VCountIntr"] + 44) != common:
            raise ValueError("Emerald VCount literals differ")
    else:
        saved, reg, intr, main = struct.unpack_from("<4I", data, offsets["VCountIntr"] + 40)
        if (reg, intr, main) != (REG_VCOUNT, INTR_CHECK, common[0]):
            raise ValueError("FireRed/LeafGreen VCount literals differ")
        values.update({"sVcountAtIntr": saved, "REG_VCOUNT": reg})
    for key in ("gMain", "sVcountAtIntr"):
        if key in values and not 0x03000000 <= values[key] <= 0x03007FFF:
            raise ValueError(f"{key} leaves IWRAM")
    return {key: f"0x{value:08X}" for key, value in values.items()}


def handler_record(data: bytes, offset: int, name: str,
                   call_names: tuple[str, ...]) -> dict[str, object]:
    length = 42 if name == "VCountIntr" and len(call_names) == 2 else 38
    cfg = disassemble_thumb_cfg.trace(data, offset, max_span=length)
    calls = sorted(cfg["calls"], key=lambda item: item["source"])
    if (cfg["range_end"] != ROM_BASE + offset + length
            or len(cfg["returns"]) != 1 or len(calls) != len(call_names)):
        raise ValueError(f"CFG boundary mismatch for {name}")
    return {"name": name, "address": f"0x{ROM_BASE + offset:08X}",
            "range_end_exclusive": f"0x{ROM_BASE + offset + length:08X}",
            "rom_code_range": {"start_offset": offset,
                               "end_offset_exclusive": offset + length,
                               "length": length, "sha256": digest(data[offset:offset + length]),
                               "raw_bytes_published": False},
            "calls": [{"name": call_name, "source": f"0x{call['source']:08X}",
                       "target": f"0x{call['target']:08X}"}
                      for call_name, call in zip(call_names, calls)],
            "control_flow": {"instruction_halfwords": cfg["instruction_halfwords"],
                             "edge_count": len(cfg["edges"]),
                             "return_count": len(cfg["returns"]),
                             "call_count": len(calls),
                             "canonical_instruction_bytes_sha256":
                                 cfg["canonical_instruction_bytes_sha256"],
                             "raw_halfwords_omitted": True}}


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          profile: str) -> dict:
    naming = PROFILES[profile]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/display_serial_interrupts.s")
    (root / source_path).write_text(source_text(profile), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    templates, roms, maps, records = profile_templates(profile), rom_index(rom_dir), [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        offsets = {name: unique_offset(data, template, name)
                   for name, template in zip(("HBlankIntr", "VCountIntr", "SerialIntr"),
                                             templates)}
        call_names = {
            "HBlankIntr": ("indirect hblank callback trampoline",),
            "VCountIntr": (("indirect vcount callback trampoline", "m4aSoundVSync")
                           if profile == "emerald" else ("m4aSoundVSync",)
                           if profile == "frlg" else
                           ("indirect vcount callback trampoline",)),
            "SerialIntr": ("indirect serial callback trampoline",),
        }
        functions = [handler_record(data, offsets[name], name, call_names[name])
                     for name in offsets]
        map_path = Path(f"analysis/{release_id}-display-serial-interrupt-disassembly.json")
        evidence = {"schema_version": 1, "axis": "Disassembly",
                    "target": {"release": release_id, "sha256": sha256},
                    "profile": profile, "origin_reference": index == 0,
                    "source": source_path.as_posix(), "source_sha256": source_sha256,
                    "functions": functions,
                    "literal_addresses": literal_values(data, offsets, profile),
                    "verified_layout": {"callback_offsets": {"hblankCallback": 16,
                                                               "vcountCallback": 20,
                                                               "serialCallback": 24,
                                                               "intrCheck": 28},
                                        "interrupt_flags": {"HBLANK": "0x0002",
                                                            "VCOUNT": "0x0004",
                                                            "SERIAL": "0x0080"}},
                    "naming_basis": {**naming,
                                     "match_kind": "independent Thumb structure, flags, literals and call order"},
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
               "functions": ["HBlankIntr", "VCountIntr", "SerialIntr"],
               "profile": profile, "origin_reference": releases[0]["id"],
               "release_count": len(records), "source": source_path.as_posix(),
               "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/display-serial-interrupt-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    note = {"rs": "VCount invokes the optional callback.",
            "emerald": "VCount invokes the optional callback and m4aSoundVSync.",
            "frlg": "VCount records REG_VCOUNT and invokes m4aSoundVSync."}[profile]
    research_path = Path("research/display-serial-interrupt-disassembly.md")
    (root / research_path).write_text(
        f"# {game} display and serial interrupt disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) contain exactly one HBlank, VCount and Serial "
        f"handler matching the `{profile}` profile. {note} Each handler sets both "
        "INTR_CHECK and gMain.intrCheck. Per-release evidence preserves ranges, hashes, "
        "validated literals and call order without ROM bytes or instruction halfwords.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_display_serial_interrupts_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/display-serial-interrupt-disassembly.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "functions": summary["functions"], "profile": profile,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_display_interrupts.py",
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
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.profile)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
