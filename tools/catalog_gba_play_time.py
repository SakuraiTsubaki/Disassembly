#!/usr/bin/env python3
"""Disassemble the complete Gen III play-time counter function cluster."""
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
DIRECT_RESET = (0x4905, 0x2000, 0x7008, 0x4905, 0x2200, 0x2000,
                0x81C8, 0x740A, 0x744A, 0x748A, 0x4770)
POINTER_RESET = (0x4906, 0x2000, 0x7008, 0x4A06, 0x6813, 0x2100, 0x2000,
                 0x81D8, 0x7419, 0x6810, 0x7441, 0x6810, 0x7481, 0x4770)
LAYOUTS = {
    "direct": {
        "functions": (("PlayTimeCounter_Reset", 0, 22, 0),
                      ("PlayTimeCounter_Start", 32, 26, 1),
                      ("PlayTimeCounter_Stop", 72, 8, 0),
                      ("PlayTimeCounter_Update", 84, 84, 1),
                      ("PlayTimeCounter_SetToMax", 180, 22, 0)),
        "literals": {"reset": (24, 28), "start": (60, 64, 68), "stop": (80,),
                     "update": (168, 172, 176), "max": (204, 208, 212)},
        "cluster_length": 216,
    },
    "pointer": {
        "functions": (("PlayTimeCounter_Reset", 0, 28, 0),
                      ("PlayTimeCounter_Start", 36, 28, 1),
                      ("PlayTimeCounter_Stop", 76, 8, 0),
                      ("PlayTimeCounter_Update", 88, 92, 1),
                      ("PlayTimeCounter_SetToMax", 192, 28, 0)),
        "literals": {"reset": (28, 32), "start": (64, 68, 72), "stop": (84,),
                     "update": (180, 184, 188), "max": (220, 224, 228)},
        "cluster_length": 232,
    },
}
PROFILES = {
    "rs": {"storage": "direct", "repository": "pret/pokeruby",
           "commit": "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f",
           "path": "src/play_time.c"},
    "emerald": {"storage": "pointer", "repository": "pret/pokeemerald",
                "commit": "fe1d8e51b265851676b65885818b1f5f62586135",
                "path": "src/play_time.c"},
    "frlg": {"storage": "pointer", "repository": "pret/pokefirered",
             "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14",
             "path": "src/play_time.c"},
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


def reset_template(storage: str) -> tuple[int, ...]:
    if storage == "direct":
        return DIRECT_RESET
    if storage == "pointer":
        return POINTER_RESET
    raise ValueError(f"unsupported storage profile: {storage}")


def matching_cluster_offsets(data: bytes, storage: str) -> list[int]:
    template = reset_template(storage)
    needle = struct.pack(f"<{len(template)}H", *template)
    result, start = [], 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return result
        if offset % 2 == 0:
            result.append(offset)
        start = offset + 2


def unique_cluster_offset(data: bytes, storage: str) -> int:
    matches = matching_cluster_offsets(data, storage)
    if len(matches) != 1:
        raise ValueError(f"expected one play-time counter cluster, found {len(matches)}")
    return matches[0]


def source_text(storage: str) -> str:
    if storage not in LAYOUTS:
        raise ValueError(f"unsupported storage profile: {storage}")
    load_save = ("    ldr \\reg, =gSaveBlock2\n" if storage == "direct" else
                 "    ldr \\reg, =gSaveBlock2Ptr\n    ldr \\reg, [\\reg]\n")
    return f'''.syntax unified
.thumb

.macro LOAD_SAVE reg
{load_save}.endm

.macro SET_COUNTER_STATE value
    ldr r1, =sPlayTimeCounterState
    movs r0, #\\value
    strb r0, [r1]
.endm

.global PlayTimeCounter_Reset
.type PlayTimeCounter_Reset, %function
PlayTimeCounter_Reset:
    SET_COUNTER_STATE 0
    LOAD_SAVE r2
    movs r1, #0
    movs r0, #0
    strh r0, [r2, #14]
    strb r1, [r2, #16]
    strb r1, [r2, #17]
    strb r1, [r2, #18]
    bx lr
.size PlayTimeCounter_Reset, . - PlayTimeCounter_Reset

.global PlayTimeCounter_Start
.type PlayTimeCounter_Start, %function
PlayTimeCounter_Start:
    push {{lr}}
    SET_COUNTER_STATE 1
    LOAD_SAVE r0
    ldrh r0, [r0, #14]
    ldr r1, =999
    cmp r0, r1
    bls .LStartReturn
    bl PlayTimeCounter_SetToMax
.LStartReturn:
    pop {{r0}}
    bx r0
.size PlayTimeCounter_Start, . - PlayTimeCounter_Start

.global PlayTimeCounter_Stop
.type PlayTimeCounter_Stop, %function
PlayTimeCounter_Stop:
    SET_COUNTER_STATE 0
    bx lr
.size PlayTimeCounter_Stop, . - PlayTimeCounter_Stop

.global PlayTimeCounter_Update
.type PlayTimeCounter_Update, %function
PlayTimeCounter_Update:
    push {{r4, lr}}
    ldr r0, =sPlayTimeCounterState
    ldrb r0, [r0]
    cmp r0, #1
    bne .LUpdateReturn
    LOAD_SAVE r4
    ldrb r0, [r4, #18]
    adds r0, #1
    strb r0, [r4, #18]
    cmp r0, #60
    blo .LUpdateReturn
    movs r0, #0
    strb r0, [r4, #18]
    ldrb r0, [r4, #17]
    adds r0, #1
    strb r0, [r4, #17]
    cmp r0, #60
    blo .LUpdateReturn
    movs r0, #0
    strb r0, [r4, #17]
    ldrb r0, [r4, #16]
    adds r0, #1
    strb r0, [r4, #16]
    cmp r0, #60
    blo .LUpdateReturn
    movs r0, #0
    strb r0, [r4, #16]
    ldrh r0, [r4, #14]
    adds r0, #1
    strh r0, [r4, #14]
    ldr r1, =999
    cmp r0, r1
    bls .LUpdateReturn
    bl PlayTimeCounter_SetToMax
.LUpdateReturn:
    pop {{r4}}
    pop {{r0}}
    bx r0
.size PlayTimeCounter_Update, . - PlayTimeCounter_Update

.global PlayTimeCounter_SetToMax
.type PlayTimeCounter_SetToMax, %function
PlayTimeCounter_SetToMax:
    SET_COUNTER_STATE 2
    LOAD_SAVE r2
    ldr r0, =999
    strh r0, [r2, #14]
    movs r1, #59
    strb r1, [r2, #16]
    strb r1, [r2, #17]
    strb r1, [r2, #18]
    bx lr
.size PlayTimeCounter_SetToMax, . - PlayTimeCounter_SetToMax
'''


def literal_record(data: bytes, cluster: int, storage: str) -> dict[str, str]:
    offsets = LAYOUTS[storage]["literals"]
    values = {name: tuple(struct.unpack_from("<I", data, cluster + offset)[0]
                          for offset in positions)
              for name, positions in offsets.items()}
    state, save = values["reset"]
    if not (values["start"][0] == values["stop"][0]
            == values["update"][0] == values["max"][0] == state):
        raise ValueError("play-time state literals disagree")
    if not (values["start"][1] == values["update"][1]
            == values["max"][1] == save):
        raise ValueError("play-time storage literals disagree")
    if (values["start"][2], values["update"][2], values["max"][2]) != (
            999, 999 << 16, 999):
        raise ValueError("maximum-hour literals disagree")
    if not 0x03000000 <= state <= 0x03007FFF:
        raise ValueError("counter state leaves IWRAM")
    save_name = "gSaveBlock2" if storage == "direct" else "gSaveBlock2Ptr"
    save_range = ((0x02000000, 0x0203FFFF) if storage == "direct"
                  else (0x03000000, 0x03007FFF))
    if not save_range[0] <= save <= save_range[1]:
        raise ValueError(f"{save_name} leaves expected RAM")
    return {"sPlayTimeCounterState": f"0x{state:08X}", save_name: f"0x{save:08X}"}


def function_records(data: bytes, cluster: int, storage: str) -> list[dict[str, object]]:
    records = []
    for name, relative, length, call_count in LAYOUTS[storage]["functions"]:
        offset = cluster + relative
        cfg = disassemble_thumb_cfg.trace(data, offset, max_span=length)
        calls = sorted(cfg["calls"], key=lambda item: item["source"])
        if (cfg["range_end"] != ROM_BASE + offset + length
                or len(cfg["returns"]) != 1 or len(calls) != call_count):
            raise ValueError(f"CFG boundary mismatch for {name}")
        records.append({"name": name, "address": f"0x{ROM_BASE + offset:08X}",
                        "range_end_exclusive": f"0x{ROM_BASE + offset + length:08X}",
                        "rom_code_range": {"start_offset": offset,
                                           "end_offset_exclusive": offset + length,
                                           "length": length,
                                           "sha256": digest(data[offset:offset + length]),
                                           "raw_bytes_published": False},
                        "calls": [{"source": f"0x{call['source']:08X}",
                                   "target": f"0x{call['target']:08X}"}
                                  for call in calls],
                        "control_flow": {"instruction_halfwords":
                                             cfg["instruction_halfwords"],
                                         "edge_count": len(cfg["edges"]),
                                         "return_count": len(cfg["returns"]),
                                         "call_count": len(calls),
                                         "canonical_instruction_bytes_sha256":
                                             cfg["canonical_instruction_bytes_sha256"],
                                         "raw_halfwords_omitted": True}})
    maximum = next(item["address"] for item in records
                   if item["name"] == "PlayTimeCounter_SetToMax")
    for name in ("PlayTimeCounter_Start", "PlayTimeCounter_Update"):
        item = next(record for record in records if record["name"] == name)
        if item["calls"][0]["target"] != maximum:
            raise ValueError(f"{name} does not call observed SetToMax")
        item["calls"][0]["name"] = "PlayTimeCounter_SetToMax"
    return records


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          profile: str) -> dict:
    naming, storage = PROFILES[profile], PROFILES[profile]["storage"]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/play_time_counter.s")
    (root / source_path).write_text(source_text(storage), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    roms, maps, records = rom_index(rom_dir), [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        cluster = unique_cluster_offset(data, storage)
        functions = function_records(data, cluster, storage)
        map_path = Path(f"analysis/{release_id}-play-time-counter-disassembly.json")
        evidence = {"schema_version": 1, "axis": "Disassembly",
                    "target": {"release": release_id, "sha256": sha256},
                    "profile": profile, "storage_profile": storage,
                    "origin_reference": index == 0,
                    "source": source_path.as_posix(), "source_sha256": source_sha256,
                    "cluster": {"rom_offset": cluster,
                                "address": f"0x{ROM_BASE + cluster:08X}",
                                "range_end_exclusive":
                                    f"0x{ROM_BASE + cluster + LAYOUTS[storage]['cluster_length']:08X}"},
                    "functions": functions,
                    "literal_addresses": literal_record(data, cluster, storage),
                    "verified_behavior": {"state_values": {"stopped": 0,
                                                            "running": 1,
                                                            "maxed_out": 2},
                                          "save_field_offsets": {"hours": 14,
                                                                 "minutes": 16,
                                                                 "seconds": 17,
                                                                 "vblanks": 18},
                                          "thresholds": {"vblanks": 60,
                                                         "seconds": 60,
                                                         "minutes": 60,
                                                         "maximum_hours": 999}},
                    "naming_basis": {**naming,
                                     "match_kind": "independent cluster layout, CFGs, literals, thresholds and call targets"},
                    "raw_rom_bytes_included": False}
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": release_id, "language": release["language"],
                        "revision": release["revision"],
                        "build_kind": release["build_kind"], "sha256": sha256,
                        "origin_reference": index == 0,
                        "cluster_address": evidence["cluster"]["address"],
                        "functions": [{"name": item["name"], "address": item["address"],
                                       "code_sha256": item["rom_code_range"]["sha256"]}
                                      for item in functions], "evidence": map_path.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "functions": [item[0] for item in LAYOUTS[storage]["functions"]],
               "profile": profile, "storage_profile": storage,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/play-time-counter-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/play-time-counter-disassembly.md")
    (root / research_path).write_text(
        f"# {game} play-time counter disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) contain one complete five-function counter "
        f"cluster with the `{storage}` storage profile. Independent ROM evidence verifies "
        "the reset/start/stop/update/max states, 60/60/60 rollover thresholds, 999-hour "
        "clamp, save offsets, CFG boundaries and SetToMax calls without publishing ROM "
        "bytes or instruction halfwords.\n", encoding="utf-8", newline="\n")
    test_path = Path("tests/test_play_time_counter_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/play-time-counter-disassembly.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "functions": summary["functions"], "profile": profile,
        "storage_profile": storage, "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_play_time.py",
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
