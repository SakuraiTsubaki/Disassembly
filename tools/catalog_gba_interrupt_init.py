#!/usr/bin/env python3
"""Disassemble Gen III interrupt initialization and callback setters."""
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
DMA3 = 0x040000D4
DMA_CONTROL = 0x84000200
INTR_VECTOR = 0x03007FFC
REG_IME = 0x04000208
REG_IE = 0x04000200
REG_DISPSTAT = 0x04000004
RS_INIT = (
    0xB530, 0x4D14, 0x4C14, 0x4B15, 0x4A15, 0x210D, 0xCB01, 0xC201,
    0x3901, 0x2900, 0xDAFA, 0x4813, 0x6005, 0x6044, 0x4912, 0x6081,
    0x6880, 0x4812, 0x6004, 0x2000, None, None, 0x2000, None, None,
    0x2000, None, None, 0x480D, 0x2201, 0x8002, 0x490D, 0x800A, 0x4B0D,
    0x2008, 0x8018, 0x8808, 0x4310, 0x8008, 0xBC30, 0xBC01, 0x4700,
)
COMMON_INIT = (
    0xB530, 0x4D12, 0x4C12, 0x4B13, 0x4A13, 0x210D, 0xCB01, 0xC201,
    0x3901, 0x2900, 0xDAFA, 0x4811, 0x6005, 0x6044, 0x4910, 0x6081,
    0x6880, 0x4810, 0x6004, 0x2000, None, None, 0x2000, None, None,
    0x2000, None, None, 0x490B, 0x2001, 0x8008, 0x2001, None, None,
    0xBC30, 0xBC01, 0x4700,
)
SETTER_STORES = {"SetVBlankCallback": 0x60C8, "SetHBlankCallback": 0x6108,
                 "SetVCountCallback": 0x6148, "SetSerialCallback": 0x6188}
SETTER_RELATIVE = {"rs": (124, 136, 148, 160),
                   "frlg": (108, 120, 132, 144),
                   "emerald": (108, 120, 132, 168)}
RESTORE_RELATIVE = 144
RESTORE_CODE = (0x4802, 0x4903, 0x6041, 0x4903, 0x6081, 0x4770)
PROFILES = {
    "rs": {"repository": "pret/pokeruby",
           "commit": "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f", "path": "src/main.c"},
    "emerald": {"repository": "pret/pokeemerald",
                "commit": "fe1d8e51b265851676b65885818b1f5f62586135", "path": "src/main.c"},
    "frlg": {"repository": "pret/pokefirered",
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


def is_bl(first: int, second: int) -> bool:
    return first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def init_template(profile: str) -> tuple[int | None, ...]:
    return RS_INIT if profile == "rs" else COMMON_INIT


def matching_init_offsets(data: bytes, profile: str) -> list[int]:
    template = init_template(profile)
    size, prefix = len(template) * 2, struct.pack("<H", template[0])
    result, start = [], 0
    while True:
        offset = data.find(prefix, start)
        if offset < 0:
            return result
        if offset % 2 == 0 and offset + size <= len(data):
            words = struct.unpack_from(f"<{len(template)}H", data, offset)
            fixed = all(expected is None or actual == expected
                        for actual, expected in zip(words, template))
            masked = [index for index, expected in enumerate(template) if expected is None]
            calls = all(is_bl(words[masked[index]], words[masked[index + 1]])
                        for index in range(0, len(masked), 2))
            if fixed and calls:
                result.append(offset)
        start = offset + 2


def unique_init_offset(data: bytes, profile: str) -> int:
    matches = matching_init_offsets(data, profile)
    if len(matches) != 1:
        raise ValueError(f"expected one InitIntrHandlers candidate, found {len(matches)}")
    return matches[0]


def validate_setter(data: bytes, offset: int, store: int,
                    g_main: int, name: str) -> None:
    words = struct.unpack_from("<4H", data, offset)
    literal = struct.unpack_from("<I", data, offset + 8)[0]
    if words != (0x4901, store, 0x4770, 0x0000) or literal != g_main:
        raise ValueError(f"{name} setter validation failed")


def source_text(profile: str) -> str:
    if profile not in PROFILES:
        raise ValueError(f"unsupported profile: {profile}")
    enable = ('''    ldr r0, =0x04000200
    movs r2, #1
    strh r2, [r0]
    ldr r1, =0x04000004
    movs r2, #8
    strh r2, [r1]
    ldrh r0, [r0]
    movs r1, #1
    orrs r0, r1
    ldr r1, =0x04000200
    strh r0, [r1]
''' if profile == "rs" else '''    movs r0, #1
    bl EnableInterrupts
''')
    restore = ('''.global RestoreSerialTimer3IntrHandlers
.type RestoreSerialTimer3IntrHandlers, %function
RestoreSerialTimer3IntrHandlers:
    ldr r0, =gIntrTable
    ldr r1, =SerialIntr
    str r1, [r0, #4]
    ldr r1, =Timer3Intr
    str r1, [r0, #8]
    bx lr
.size RestoreSerialTimer3IntrHandlers, . - RestoreSerialTimer3IntrHandlers

''' if profile == "emerald" else "")
    return f'''.syntax unified
.thumb

.global InitIntrHandlers
.type InitIntrHandlers, %function
InitIntrHandlers:
    push {{r4, r5, lr}}
    ldr r5, =IntrMain
    ldr r4, =IntrMain_Buffer
    ldr r3, =gIntrTableTemplate
    ldr r2, =gIntrTable
    movs r1, #13
.LCopyTable:
    ldm r3!, {{r0}}
    stm r2!, {{r0}}
    subs r1, #1
    cmp r1, #0
    bge .LCopyTable
    ldr r0, =0x040000D4
    str r5, [r0]
    str r4, [r0, #4]
    ldr r1, =0x84000200
    str r1, [r0, #8]
    ldr r0, [r0, #8]
    ldr r0, =0x03007FFC
    str r4, [r0]
    movs r0, #0
    bl SetVBlankCallback
    movs r0, #0
    bl SetHBlankCallback
    movs r0, #0
    bl SetSerialCallback
    ldr r0, =0x04000208
    movs r1, #1
    strh r1, [r0]
{enable}    pop {{r4, r5}}
    pop {{r0}}
    bx r0
.size InitIntrHandlers, . - InitIntrHandlers

.global SetVBlankCallback
SetVBlankCallback:
    ldr r1, =gMain
    str r0, [r1, #12]
    bx lr

.global SetHBlankCallback
SetHBlankCallback:
    ldr r1, =gMain
    str r0, [r1, #16]
    bx lr

.global SetVCountCallback
SetVCountCallback:
    ldr r1, =gMain
    str r0, [r1, #20]
    bx lr

{restore}.global SetSerialCallback
SetSerialCallback:
    ldr r1, =gMain
    str r0, [r1, #24]
    bx lr
'''


def init_literals(data: bytes, offset: int, profile: str) -> dict[str, int]:
    if profile == "rs":
        names = ("IntrMain", "IntrMain_Buffer", "gIntrTableTemplate", "gIntrTable",
                 "DMA3", "DMA_CONTROL", "INTR_VECTOR", "REG_IME", "REG_IE",
                 "REG_DISPSTAT")
        values = struct.unpack_from("<10I", data, offset + 84)
        fixed = {"DMA3": DMA3, "DMA_CONTROL": DMA_CONTROL,
                 "INTR_VECTOR": INTR_VECTOR, "REG_IME": REG_IME,
                 "REG_IE": REG_IE, "REG_DISPSTAT": REG_DISPSTAT}
    else:
        names = ("IntrMain", "IntrMain_Buffer", "gIntrTableTemplate", "gIntrTable",
                 "DMA3", "DMA_CONTROL", "INTR_VECTOR", "REG_IME")
        values = struct.unpack_from("<8I", data, offset + 76)
        fixed = {"DMA3": DMA3, "DMA_CONTROL": DMA_CONTROL,
                 "INTR_VECTOR": INTR_VECTOR, "REG_IME": REG_IME}
    result = dict(zip(names, values))
    if any(result[key] != value for key, value in fixed.items()):
        raise ValueError("fixed interrupt literals differ")
    if any(not ROM_BASE <= result[key] < 0x0A000000
           for key in ("IntrMain", "gIntrTableTemplate")):
        raise ValueError("ROM pointer leaves cartridge space")
    if any(not 0x03000000 <= result[key] <= 0x03007FFF
           for key in ("gIntrTable", "IntrMain_Buffer")):
        raise ValueError("interrupt buffer leaves IWRAM")
    return result


def code_record(data: bytes, offset: int, length: int, name: str,
                call_names: tuple[str, ...] = ()) -> dict[str, object]:
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
    source_path = Path("src/interrupt_init.s")
    (root / source_path).write_text(source_text(profile), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    roms, maps, records = rom_index(rom_dir), [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        init_offset = unique_init_offset(data, profile)
        values = init_literals(data, init_offset, profile)
        names = tuple(SETTER_STORES)
        setters = dict(zip(names, (init_offset + delta for delta in SETTER_RELATIVE[profile])))
        g_main = struct.unpack_from("<I", data, setters["SetVBlankCallback"] + 8)[0]
        if not 0x03000000 <= g_main <= 0x03007FFF:
            raise ValueError("gMain setter literal leaves IWRAM")
        for name in names:
            validate_setter(data, setters[name], SETTER_STORES[name], g_main, name)
        call_names = (("SetVBlankCallback", "SetHBlankCallback", "SetSerialCallback")
                      if profile == "rs" else
                      ("SetVBlankCallback", "SetHBlankCallback", "SetSerialCallback",
                       "EnableInterrupts"))
        functions = [code_record(data, init_offset, len(init_template(profile)) * 2,
                                 "InitIntrHandlers", call_names)]
        functions.extend(code_record(data, setters[name], 6, name) for name in names[:3])
        restore_literals = None
        if profile == "emerald":
            restore = init_offset + RESTORE_RELATIVE
            if struct.unpack_from("<6H", data, restore) != RESTORE_CODE:
                raise ValueError("restore handler code differs")
            restored = struct.unpack_from("<3I", data, restore + 12)
            if restored[0] != values["gIntrTable"]:
                raise ValueError("restore gIntrTable differs")
            restore_literals = {"SerialIntr": restored[1], "Timer3Intr": restored[2]}
            functions.append(code_record(data, restore, 12,
                                         "RestoreSerialTimer3IntrHandlers"))
        functions.append(code_record(data, setters["SetSerialCallback"], 6,
                                     "SetSerialCallback"))
        literals = {key: f"0x{value:08X}" for key, value in values.items()
                    if key != "DMA_CONTROL"}
        literals["gMain"] = f"0x{g_main:08X}"
        if restore_literals:
            literals.update({key: f"0x{value:08X}"
                             for key, value in restore_literals.items()})
        map_path = Path(f"analysis/{release_id}-interrupt-init-disassembly.json")
        evidence = {"schema_version": 1, "axis": "Disassembly",
                    "target": {"release": release_id, "sha256": sha256},
                    "profile": profile, "origin_reference": index == 0,
                    "source": source_path.as_posix(), "source_sha256": source_sha256,
                    "functions": functions,
                    "dma": {"channel": 3, "byte_count": 2048,
                            "control": "0x84000200"},
                    "literal_addresses": literals,
                    "verified_layout": {"interrupt_table_entries": 14,
                                        "callback_offsets": {"vblank": 12,
                                                             "hblank": 16,
                                                             "vcount": 20,
                                                             "serial": 24},
                                        "vblank_enable":
                                            ("direct IE and DISPSTAT writes"
                                             if profile == "rs" else
                                             "EnableInterrupts call"),
                                        "serial_timer3_restore": profile == "emerald"},
                    "naming_basis": {**naming,
                                     "match_kind": "independent Thumb CFG, table loop, DMA constants, literals, calls and callback stores"},
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
               "profile": profile, "origin_reference": releases[0]["id"],
               "release_count": len(records), "source": source_path.as_posix(),
               "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/interrupt-init-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    note = {"rs": "VBlank uses direct IE and DISPSTAT writes.",
            "frlg": "VBlank is enabled through EnableInterrupts.",
            "emerald": "VBlank uses EnableInterrupts and Serial/Timer3 handlers have a restore function."}[profile]
    research_path = Path("research/interrupt-init-disassembly.md")
    (root / research_path).write_text(
        f"# {game} interrupt initialization disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) contain one InitIntrHandlers suite matching "
        f"the `{profile}` profile. {note} The routine copies 14 table entries, DMA-copies "
        "the 0x800-byte dispatcher with DMA3 control 0x84000200, installs the IWRAM "
        "vector, clears callbacks and enables VBlank. Evidence omits ROM bytes and "
        "instruction halfwords.\n", encoding="utf-8", newline="\n")
    test_path = Path("tests/test_interrupt_init_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/interrupt-init-disassembly.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "profile": profile, "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_interrupt_init.py",
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
