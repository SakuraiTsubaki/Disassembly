#!/usr/bin/env python3
"""Trace and catalog InitHeap in Gen III Disassembly projects."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gba_reset_bgs
import disassemble_thumb_cfg


ROM_BASE = 0x08000000
SHAPE = (18, 9, 1, 1, 0)
PROFILES = {
    "emerald": {"repository": "pret/pokeemerald",
                "commit": "fe1d8e51b265851676b65885818b1f5f62586135",
                "calls_after_reset_bgs": 2},
    "frlg": {"repository": "pret/pokefirered",
             "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14",
             "calls_after_reset_bgs": 1},
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
    if (len(values) == 9 and values[0] == 0xB500
            and values[1] & 0xF800 == 0x4800 and values[1] & 0x0700 == 0x0200
            and values[2] == 0x6010
            and values[3] & 0xF800 == 0x4800 and values[3] & 0x0700 == 0x0200
            and values[4] == 0x6011 and values[-2:] == [0xBC01, 0x4700]):
        return "record-arena-then-first-block"
    return "unknown"


def locate_from_boot(data: bytes, family: str) -> tuple[dict, dict, dict]:
    caller, _, reset_bgs = catalog_gba_reset_bgs.locate_from_boot(data)
    calls = sorted(caller["calls"], key=lambda item: item["source"])
    indices = [index for index, call in enumerate(calls)
               if call["target"] == reset_bgs["start_address"]]
    step = PROFILES[family]["calls_after_reset_bgs"]
    if len(indices) != 1 or indices[0] + step >= len(calls):
        raise ValueError("could not resolve family-specific InitHeap boot call")
    call = calls[indices[0] + step]
    function = disassemble_thumb_cfg.trace(data, call["target"] - ROM_BASE, max_span=0x100)
    return caller, call, function


def literal_value(data: bytes, instruction: dict) -> int:
    pool = ((instruction["address"] + 4) & ~3) + (instruction["halfword"] & 0xFF) * 4
    return struct.unpack_from("<I", data, pool - ROM_BASE)[0]


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    profile = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/init_heap.s")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in ("InitHeap:", "sHeapStart", "sHeapSize", "PutFirstMemBlockHeader"):
        if token not in source:
            raise ValueError(f"disassembly source is missing token: {token}")
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        caller, boot_call, function = locate_from_boot(data, family)
        if shape(function) != SHAPE or instruction_form(function) == "unknown":
            raise ValueError(f"InitHeap structural signature differs: {release_id}")
        call = function["calls"][0]
        first_block = disassemble_thumb_cfg.trace(
            data, call["target"] - ROM_BASE, max_span=0x100)
        if shape(first_block) != SHAPE:
            raise ValueError(f"PutFirstMemBlockHeader structural signature differs: {release_id}")
        instructions = sorted(function["instructions"], key=lambda item: item["address"])
        globals_ = [literal_value(data, instructions[i]) for i in (1, 3)]
        if not all(0x03000000 <= value <= 0x03007FFC for value in globals_):
            raise ValueError(f"heap globals are outside IWRAM: {release_id}")
        prior_path = Path(f"analysis/{release_id}-reset-bgs-disassembly.json")
        prior = json.loads((root / prior_path).read_text(encoding="utf-8"))
        if int(prior["function"]["address"], 16) not in {
                item["target"] for item in caller["calls"]}:
            raise ValueError(f"ResetBgs cross-reference differs: {release_id}")
        start, end = function["start_address"] - ROM_BASE, function["range_end"] - ROM_BASE
        output = Path(f"analysis/{release_id}-init-heap-disassembly.json")
        evidence = {
            "schema_version": 1, "axis": "Disassembly",
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0, "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "discovery": {"caller": "thumb_entry_reachable",
                          "caller_address": f"0x{caller['start_address']:08X}",
                          "boot_call_source": f"0x{boot_call['source']:08X}",
                          "calls_after_reset_bgs": profile["calls_after_reset_bgs"]},
            "function": {"name": "InitHeap", "address": f"0x{function['start_address']:08X}",
                         "range_end_exclusive": f"0x{function['range_end']:08X}",
                         "rom_code_range": {"start_offset": start,
                                            "end_offset_exclusive": end,
                                            "length": end - start,
                                            "sha256": digest(data[start:end]),
                                            "raw_bytes_published": False},
                         "calls": [{"name": "PutFirstMemBlockHeader",
                                    "source": f"0x{call['source']:08X}",
                                    "target": f"0x{call['target']:08X}",
                                    "relative_offset":
                                        call["target"] - function["start_address"],
                                    "callee_code_sha256":
                                        first_block["canonical_instruction_bytes_sha256"]}]},
            "control_flow": {"instruction_halfwords": function["instruction_halfwords"],
                             "edge_count": len(function["edges"]),
                             "direct_call_count": len(function["calls"]),
                             "return_count": len(function["returns"]),
                             "canonical_instruction_bytes_sha256":
                                 function["canonical_instruction_bytes_sha256"],
                             "raw_halfwords_omitted": True},
            "verified_behavior": {"instruction_form": instruction_form(function),
                                  "records_heap_start_and_size": True,
                                  "sHeapStart_address": f"0x{globals_[0]:08X}",
                                  "sHeapSize_address": f"0x{globals_[1]:08X}",
                                  "callee_shape": list(SHAPE)},
            "cross_reference": {"reset_bgs_map": prior_path.as_posix(),
                                "reset_bgs_map_sha256": file_hash(root / prior_path)},
            "naming_basis": {"repository": profile["repository"],
                             "commit": profile["commit"], "path": "src/malloc.c"},
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
               "function": "InitHeap", "family_profile": family,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/init-heap-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/init-heap-disassembly.md")
    (root / research_path).write_text(
        f"# {game} InitHeap disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) preserve the 18-byte arena bootstrap that "
        "stores the heap start and size before calling PutFirstMemBlockHeader. The "
        f"family-specific boot order uses {profile['calls_after_reset_bgs']} call(s) "
        "after ResetBgs. Maps retain addresses and hashes without ROM bytes.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_init_heap_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/init-heap-disassembly.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": "InitHeap", "family_profile": family,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_init_heap.py",
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
