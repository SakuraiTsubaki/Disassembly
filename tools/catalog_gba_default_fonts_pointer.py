#!/usr/bin/env python3
"""Trace and catalog SetDefaultFontsPointer in Gen III Disassembly projects."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gba_init_heap
import disassemble_thumb_cfg

ROM_BASE = 0x08000000
SHAPE = (12, 6, 1, 1, 0)
CALLEE_SHAPE = (6, 3, 0, 1, 0)
PROFILES = {
    "emerald": {"repository": "pret/pokeemerald",
                "commit": "fe1d8e51b265851676b65885818b1f5f62586135",
                "call_offset_from_init_heap": -1, "default_table": "sFontInfos",
                "path": "src/text.c"},
    "frlg": {"repository": "pret/pokefirered",
             "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14",
             "call_offset_from_init_heap": 1, "default_table": "gFontInfos",
             "path": "src/new_menu_helpers.c"},
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
    if (len(values) == 6 and values[0] == 0xB500
            and values[1] & 0xF800 == 0x4800
            and values[-2:] == [0xBC01, 0x4700]):
        return "load-default-table-then-set-pointer"
    return "unknown"

def locate_from_boot(data: bytes, family: str) -> tuple[dict, dict, dict]:
    caller, _, init_heap = catalog_gba_init_heap.locate_from_boot(data, family)
    calls = sorted(caller["calls"], key=lambda item: item["source"])
    indices = [index for index, call in enumerate(calls)
               if call["target"] == init_heap["start_address"]]
    offset = PROFILES[family]["call_offset_from_init_heap"]
    if len(indices) != 1 or not 0 <= indices[0] + offset < len(calls):
        raise ValueError("could not resolve family-specific default-font boot call")
    call = calls[indices[0] + offset]
    function = disassemble_thumb_cfg.trace(data, call["target"] - ROM_BASE, max_span=0x100)
    return caller, call, function

def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    profile = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/set_default_fonts_pointer.s")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in ("SetDefaultFontsPointer:", profile["default_table"], "SetFontsPointer"):
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
            raise ValueError(f"SetDefaultFontsPointer signature differs: {release_id}")
        call = function["calls"][0]
        callee = disassemble_thumb_cfg.trace(data, call["target"] - ROM_BASE, max_span=0x80)
        if shape(callee) != CALLEE_SHAPE:
            raise ValueError(f"SetFontsPointer signature differs: {release_id}")
        instruction = sorted(function["instructions"], key=lambda item: item["address"])[1]
        pool = ((instruction["address"] + 4) & ~3) + (instruction["halfword"] & 0xFF) * 4
        table = struct.unpack_from("<I", data, pool - ROM_BASE)[0]
        if not 0x08000000 <= table < 0x0A000000:
            raise ValueError(f"default font table is outside ROM: {release_id}")
        heap_path = Path(f"analysis/{release_id}-init-heap-disassembly.json")
        heap = json.loads((root / heap_path).read_text(encoding="utf-8"))
        if int(heap["function"]["address"], 16) not in {
                item["target"] for item in caller["calls"]}:
            raise ValueError(f"InitHeap cross-reference differs: {release_id}")
        start, end = function["start_address"] - ROM_BASE, function["range_end"] - ROM_BASE
        output = Path(f"analysis/{release_id}-default-fonts-pointer-disassembly.json")
        evidence = {
            "schema_version": 1, "axis": "Disassembly",
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0, "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "discovery": {"caller": "thumb_entry_reachable",
                          "caller_address": f"0x{caller['start_address']:08X}",
                          "boot_call_source": f"0x{boot_call['source']:08X}",
                          "call_offset_from_init_heap": profile["call_offset_from_init_heap"]},
            "function": {"name": "SetDefaultFontsPointer",
                         "address": f"0x{function['start_address']:08X}",
                         "range_end_exclusive": f"0x{function['range_end']:08X}",
                         "rom_code_range": {"start_offset": start,
                                            "end_offset_exclusive": end,
                                            "length": end - start,
                                            "sha256": digest(data[start:end]),
                                            "raw_bytes_published": False},
                         "calls": [{"name": "SetFontsPointer",
                                    "source": f"0x{call['source']:08X}",
                                    "target": f"0x{call['target']:08X}",
                                    "callee_code_sha256":
                                        callee["canonical_instruction_bytes_sha256"]}]},
            "control_flow": {"instruction_halfwords": function["instruction_halfwords"],
                             "edge_count": len(function["edges"]),
                             "direct_call_count": len(function["calls"]),
                             "return_count": len(function["returns"]),
                             "canonical_instruction_bytes_sha256":
                                 function["canonical_instruction_bytes_sha256"],
                             "raw_halfwords_omitted": True},
            "verified_behavior": {"instruction_form": instruction_form(function),
                                  "default_table_name": profile["default_table"],
                                  "default_table_address": f"0x{table:08X}",
                                  "callee_shape": list(CALLEE_SHAPE)},
            "cross_reference": {"init_heap_map": heap_path.as_posix(),
                                "init_heap_map_sha256": file_hash(root / heap_path)},
            "naming_basis": {"repository": profile["repository"],
                             "commit": profile["commit"], "path": profile["path"]},
            "raw_rom_bytes_included": False,
        }
        write_json(root / output, evidence)
        maps.append(output)
        records.append({"id": release_id, "language": release["language"],
                        "revision": release["revision"], "build_kind": release["build_kind"],
                        "sha256": sha256, "origin_reference": index == 0,
                        "address": evidence["function"]["address"],
                        "default_table_address": evidence["verified_behavior"]["default_table_address"],
                        "code_sha256": evidence["function"]["rom_code_range"]["sha256"],
                        "evidence": output.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "function": "SetDefaultFontsPointer", "family_profile": family,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/default-fonts-pointer-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/default-fonts-pointer-disassembly.md")
    (root / research_path).write_text(
        f"# {game} SetDefaultFontsPointer disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) preserve the 12-byte wrapper that loads "
        f"`{profile['default_table']}` and calls SetFontsPointer. Family-specific "
        "boot ordering around InitHeap is independently checked. Maps publish only "
        "addresses, structure and hashes, never ROM bytes or instruction halfwords.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_default_fonts_pointer_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/default-fonts-pointer-disassembly.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": "SetDefaultFontsPointer", "family_profile": family,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_default_fonts_pointer.py",
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

