#!/usr/bin/env python3
"""Trace and catalog ClearDma3Requests in Gen III Disassembly projects."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gba_init_map_music
import disassemble_thumb_cfg


ROM_BASE = 0x08000000
SHAPE = (42, 21, 0, 1, 2)
FORM = [0xB500, 0x4A0A, 0x2001, 0x7010, 0x4909, 0x2000, 0x7008,
        0x2300, 0x4808, 0x217F, 0x8103, 0x6003, 0x6043, 0x3010,
        0x3901, 0x2900, 0xDAF8, 0x2000, 0x7010, 0xBC01, 0x4700]
PROFILES = {
    "emerald": ("pret/pokeemerald", "fe1d8e51b265851676b65885818b1f5f62586135"),
    "frlg": ("pret/pokefirered", "037335f4c725d7c9aecdac87066f2002b4bd7e14"),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def rom_index(directory: Path) -> dict[str, Path]:
    return {file_hash(path): path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() == ".gba"}


def shape(cfg: dict) -> tuple[int, int, int, int, int]:
    return (cfg["range_end"] - cfg["start_address"], cfg["instruction_halfwords"],
            len(cfg["calls"]), len(cfg["returns"]), len(cfg["edges"]))


def instruction_form(cfg: dict) -> str:
    values = [item["halfword"] for item in
              sorted(cfg["instructions"], key=lambda item: item["address"])]
    return "lock-clear-128-requests-unlock" if values == FORM else "unknown"


def literal_value(data: bytes, instruction: dict) -> int:
    address = instruction["address"]
    pool = ((address + 4) & ~3) + (instruction["halfword"] & 0xFF) * 4
    return struct.unpack_from("<I", data, pool - ROM_BASE)[0]


def locate_from_boot(data: bytes) -> tuple[dict, dict, dict]:
    caller, _, init_map = catalog_gba_init_map_music.locate_from_boot(data)
    calls = sorted(caller["calls"], key=lambda item: item["source"])
    indices = [index for index, call in enumerate(calls)
               if call["target"] == init_map["start_address"]]
    if len(indices) != 1 or indices[0] + 1 >= len(calls):
        raise ValueError("could not resolve the call immediately after InitMapMusic")
    call = calls[indices[0] + 1]
    function = disassemble_thumb_cfg.trace(data, call["target"] - ROM_BASE, max_span=0x200)
    return caller, call, function


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    repository, commit = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/clear_dma3_requests.s")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in ("ClearDma3Requests:", "sDma3ManagerLocked",
                  "sDma3RequestCursor", "sDma3Requests", "#0x7f"):
        if token not in source:
            raise ValueError(f"disassembly source is missing token: {token}")
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        caller, boot_call, function = locate_from_boot(data)
        if shape(function) != SHAPE or instruction_form(function) == "unknown":
            raise ValueError(f"ClearDma3Requests structural signature differs: {release_id}")
        instructions = sorted(function["instructions"], key=lambda item: item["address"])
        globals_ = [literal_value(data, instructions[i]) for i in (1, 4, 8)]
        if not all(0x03000000 <= value <= 0x03007FFF for value in globals_[:2]):
            raise ValueError(f"DMA3 manager globals are outside IWRAM: {release_id}")
        if not 0x02000000 <= globals_[2] <= 0x03007FFF:
            raise ValueError(f"DMA3 request array is outside work RAM: {release_id}")
        backward = [edge for edge in function["edges"]
                    if edge["target"] < edge["source"]]
        if len(backward) != 1:
            raise ValueError(f"expected one request-array loop: {release_id}")
        init_path = Path(f"analysis/{release_id}-init-map-music-disassembly.json")
        init_map = json.loads((root / init_path).read_text(encoding="utf-8"))
        if int(init_map["function"]["address"], 16) not in {
                item["target"] for item in caller["calls"]}:
            raise ValueError(f"InitMapMusic cross-reference differs: {release_id}")
        start = function["start_address"] - ROM_BASE
        end = function["range_end"] - ROM_BASE
        output = Path(f"analysis/{release_id}-clear-dma3-requests-disassembly.json")
        evidence = {
            "schema_version": 1, "axis": "Disassembly",
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0, "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "discovery": {"caller": "thumb_entry_reachable",
                          "caller_address": f"0x{caller['start_address']:08X}",
                          "boot_call_source": f"0x{boot_call['source']:08X}",
                          "rule": "direct boot call immediately after InitMapMusic"},
            "function": {"name": "ClearDma3Requests",
                         "address": f"0x{function['start_address']:08X}",
                         "range_end_exclusive": f"0x{function['range_end']:08X}",
                         "rom_code_range": {"start_offset": start,
                                            "end_offset_exclusive": end,
                                            "length": end - start,
                                            "sha256": digest(data[start:end]),
                                            "raw_bytes_published": False}},
            "control_flow": {"instruction_halfwords": function["instruction_halfwords"],
                             "edge_count": len(function["edges"]),
                             "direct_call_count": len(function["calls"]),
                             "return_count": len(function["returns"]),
                             "loop_back_edge": {"source": f"0x{backward[0]['source']:08X}",
                                                "target": f"0x{backward[0]['target']:08X}"},
                             "canonical_instruction_bytes_sha256":
                                 function["canonical_instruction_bytes_sha256"],
                             "raw_halfwords_omitted": True},
            "verified_behavior": {"instruction_form": instruction_form(function),
                                  "locks_manager_during_reset": True,
                                  "resets_request_cursor": True,
                                  "request_count": 128,
                                  "request_stride": 16,
                                  "cleared_offsets": [8, 0, 4],
                                  "global_addresses": {
                                      "sDma3ManagerLocked": f"0x{globals_[0]:08X}",
                                      "sDma3RequestCursor": f"0x{globals_[1]:08X}",
                                      "sDma3Requests": f"0x{globals_[2]:08X}"}},
            "cross_reference": {"init_map_music_map": init_path.as_posix(),
                                "init_map_music_map_sha256": file_hash(root / init_path)},
            "naming_basis": {"repository": repository, "commit": commit,
                             "path": "src/dma3_manager.c"},
            "raw_rom_bytes_included": False,
        }
        write_json(root / output, evidence)
        maps.append(output)
        records.append({"id": release_id, "language": release["language"],
                        "revision": release["revision"], "build_kind": release["build_kind"],
                        "sha256": sha256, "origin_reference": index == 0,
                        "address": evidence["function"]["address"],
                        "code_sha256": evidence["function"]["rom_code_range"]["sha256"],
                        "evidence": output.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "function": "ClearDma3Requests", "family_profile": family,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/clear-dma3-requests-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/clear-dma3-requests-disassembly.md")
    (root / research_path).write_text(
        f"# {game} ClearDma3Requests disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) resolve the boot call immediately after "
        "InitMapMusic and preserve the same 42-byte routine: lock the manager, reset "
        "the cursor, clear size/source/destination in 128 sixteen-byte requests, then "
        "unlock. Maps retain addresses, structure and hashes without ROM bytes.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_clear_dma3_requests_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/clear-dma3-requests-disassembly.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": "ClearDma3Requests", "family_profile": family,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_clear_dma3_requests.py",
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

