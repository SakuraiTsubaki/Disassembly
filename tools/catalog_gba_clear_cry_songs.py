#!/usr/bin/env python3
"""Disassemble ClearPokemonCrySongs across Gen III release catalogs."""
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
PREFIX = bytes.fromhex("00b581b06946002008800449044a6846")
EPILOGUE = bytes.fromhex("01b001bc0047")
FUNCTION_LENGTH = 26
DESTINATION_LITERAL_OFFSET = 28
MODE_LITERAL_OFFSET = 32
CPU_SET_MODE = 0x01000034
HALFWORD_COUNT = 0x34
BYTE_COUNT = HALFWORD_COUNT * 2
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


def matching_offsets(data: bytes) -> list[int]:
    matches, start = [], 0
    while True:
        offset = data.find(PREFIX, start)
        if offset < 0:
            return matches
        if (offset % 2 == 0
                and data[offset + 20:offset + FUNCTION_LENGTH] == EPILOGUE
                and len(data) >= offset + MODE_LITERAL_OFFSET + 4
                and struct.unpack_from("<I", data, offset + MODE_LITERAL_OFFSET)[0]
                == CPU_SET_MODE):
            matches.append(offset)
        start = offset + 2


def unique_function_offset(data: bytes) -> int:
    matches = matching_offsets(data)
    if len(matches) != 1:
        raise ValueError(f"expected one ClearPokemonCrySongs candidate, found {len(matches)}")
    return matches[0]


def source_text() -> str:
    return '''.syntax unified
.thumb

.global ClearPokemonCrySongs
.type ClearPokemonCrySongs, %function
ClearPokemonCrySongs:
    push {lr}
    sub sp, #4
    mov r1, sp
    movs r0, #0
    strh r0, [r1]
    ldr r1, =gPokemonCrySongs
    ldr r2, =0x01000034
    mov r0, sp
    bl CpuSet
    add sp, #4
    pop {r0}
    bx r0
.size ClearPokemonCrySongs, . - ClearPokemonCrySongs
'''


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          profile: str) -> dict:
    naming = PROFILES[profile]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/clear_pokemon_cry_songs.s")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    roms, maps, records = rom_index(rom_dir), [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        offset = unique_function_offset(data)
        destination = struct.unpack_from("<I", data,
                                         offset + DESTINATION_LITERAL_OFFSET)[0]
        if not 0x03000000 <= destination < 0x03008000:
            raise ValueError(f"destination leaves IWRAM: {release_id}")
        cfg = disassemble_thumb_cfg.trace(data, offset, max_span=FUNCTION_LENGTH)
        if (cfg["range_end"] != ROM_BASE + offset + FUNCTION_LENGTH
                or len(cfg["returns"]) != 1 or len(cfg["calls"]) != 1):
            raise ValueError(f"CFG boundary mismatch: {release_id}")
        code = data[offset:offset + FUNCTION_LENGTH]
        call = cfg["calls"][0]
        map_path = Path(f"analysis/{release_id}-clear-pokemon-cry-songs-disassembly.json")
        evidence = {"schema_version": 1, "axis": "Disassembly",
                    "target": {"release": release_id, "sha256": sha256},
                    "profile": profile, "origin_reference": index == 0,
                    "source": source_path.as_posix(), "source_sha256": source_sha256,
                    "function": {"name": "ClearPokemonCrySongs",
                                 "address": f"0x{ROM_BASE + offset:08X}",
                                 "range_end_exclusive":
                                     f"0x{ROM_BASE + offset + FUNCTION_LENGTH:08X}",
                                 "rom_code_range": {"start_offset": offset,
                                                    "end_offset_exclusive":
                                                        offset + FUNCTION_LENGTH,
                                                    "length": FUNCTION_LENGTH,
                                                    "sha256": digest(code),
                                                    "raw_bytes_published": False},
                                 "call": {"name": "CpuSet",
                                          "source": f"0x{call['source']:08X}",
                                          "target": f"0x{call['target']:08X}"}},
                    "control_flow": {"instruction_halfwords": cfg["instruction_halfwords"],
                                     "edge_count": len(cfg["edges"]),
                                     "return_count": len(cfg["returns"]),
                                     "call_count": len(cfg["calls"]),
                                     "canonical_instruction_bytes_sha256":
                                         cfg["canonical_instruction_bytes_sha256"],
                                     "raw_halfwords_omitted": True},
                    "state": {"gPokemonCrySongs": f"0x{destination:08X}",
                              "byte_count": BYTE_COUNT},
                    "verified_behavior": {"fill_value": 0, "unit": "halfword",
                                          "halfword_count": HALFWORD_COUNT,
                                          "source_fixed": True,
                                          "cpu_set_mode": f"0x{CPU_SET_MODE:08X}"},
                    "naming_basis": {**naming,
                                     "match_kind": "independent Thumb CFG, CpuSet mode, destination class and clear size"},
                    "raw_rom_bytes_included": False}
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": release_id, "language": release["language"],
                        "revision": release["revision"],
                        "build_kind": release["build_kind"], "sha256": sha256,
                        "origin_reference": index == 0,
                        "address": evidence["function"]["address"],
                        "code_sha256": evidence["function"]["rom_code_range"]["sha256"],
                        "destination": evidence["state"]["gPokemonCrySongs"],
                        "cpu_set_target": evidence["function"]["call"]["target"],
                        "evidence": map_path.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "function": "ClearPokemonCrySongs", "profile": profile,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "cleared_byte_count": BYTE_COUNT, "source": source_path.as_posix(),
               "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/clear-pokemon-cry-songs-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/clear-pokemon-cry-songs-disassembly.md")
    (root / research_path).write_text(
        f"# {game} ClearPokemonCrySongs disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) contain exactly one 26-byte Thumb function. "
        "It places a zero halfword on the stack and calls CpuSet in source-fixed mode "
        "to clear 52 halfwords (104 bytes) at the release-specific gPokemonCrySongs "
        "IWRAM address. Maps preserve ranges, hashes, destinations, call targets and "
        "raw-free CFG evidence.\n", encoding="utf-8", newline="\n")
    test_path = Path("tests/test_clear_pokemon_cry_songs_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/clear-pokemon-cry-songs-disassembly.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": summary["function"], "profile": profile,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_clear_cry_songs.py",
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
