#!/usr/bin/env python3
"""Trace and catalog ResetBgs in Gen III Disassembly projects."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gba_clear_dma3_requests
import disassemble_thumb_cfg


ROM_BASE = 0x08000000
SHAPE = (20, 10, 2, 1, 0)
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
    if (len(values) == 10 and values[0] == 0xB500
            and values[1] & 0xF800 == 0xF000 and values[2] & 0xF800 == 0xF800
            and values[3:6] == [0x4903, 0x2000, 0x8208]
            and values[6] & 0xF800 == 0xF000 and values[7] & 0xF800 == 0xF800
            and values[8:] == [0xBC01, 0x4700]):
        return "reset-structs-clear-dispcnt-hide-bgs"
    return "unknown"


def locate_from_boot(data: bytes) -> tuple[dict, dict, dict]:
    caller, _, clear_dma = catalog_gba_clear_dma3_requests.locate_from_boot(data)
    calls = sorted(caller["calls"], key=lambda item: item["source"])
    indices = [index for index, call in enumerate(calls)
               if call["target"] == clear_dma["start_address"]]
    if len(indices) != 1 or indices[0] + 1 >= len(calls):
        raise ValueError("could not resolve the call immediately after ClearDma3Requests")
    call = calls[indices[0] + 1]
    function = disassemble_thumb_cfg.trace(data, call["target"] - ROM_BASE, max_span=0x100)
    return caller, call, function


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    repository, commit = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/reset_bgs.s")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in ("ResetBgs:", "ResetBgControlStructs", "sGpuBgConfigs",
                  "SetTextModeAndHideBgs"):
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
            raise ValueError(f"ResetBgs structural signature differs: {release_id}")
        calls = sorted(function["calls"], key=lambda item: item["source"])
        if [call["target"] - function["start_address"] for call in calls] != [0x44, 0x3CC]:
            raise ValueError(f"ResetBgs callee offsets differ: {release_id}")
        instructions = sorted(function["instructions"], key=lambda item: item["address"])
        literal_address = ((instructions[3]["address"] + 4) & ~3) + 12
        bg_control = struct.unpack_from("<I", data, literal_address - ROM_BASE)[0]
        if not 0x03000000 <= bg_control <= 0x03007FEF:
            raise ValueError(f"ResetBgs control cache is outside IWRAM: {release_id}")
        prior_path = Path(f"analysis/{release_id}-clear-dma3-requests-disassembly.json")
        prior = json.loads((root / prior_path).read_text(encoding="utf-8"))
        if int(prior["function"]["address"], 16) not in {
                item["target"] for item in caller["calls"]}:
            raise ValueError(f"ClearDma3Requests cross-reference differs: {release_id}")
        start, end = function["start_address"] - ROM_BASE, function["range_end"] - ROM_BASE
        output = Path(f"analysis/{release_id}-reset-bgs-disassembly.json")
        evidence = {
            "schema_version": 1, "axis": "Disassembly",
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0, "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "discovery": {"caller": "thumb_entry_reachable",
                          "caller_address": f"0x{caller['start_address']:08X}",
                          "boot_call_source": f"0x{boot_call['source']:08X}",
                          "rule": "direct boot call immediately after ClearDma3Requests"},
            "function": {"name": "ResetBgs", "address": f"0x{function['start_address']:08X}",
                         "range_end_exclusive": f"0x{function['range_end']:08X}",
                         "rom_code_range": {"start_offset": start,
                                            "end_offset_exclusive": end,
                                            "length": end - start,
                                            "sha256": digest(data[start:end]),
                                            "raw_bytes_published": False},
                         "calls": [{"name": name, "source": f"0x{call['source']:08X}",
                                    "target": f"0x{call['target']:08X}"}
                                   for name, call in zip(
                                       ["ResetBgControlStructs", "SetTextModeAndHideBgs"], calls)]},
            "control_flow": {"instruction_halfwords": function["instruction_halfwords"],
                             "edge_count": len(function["edges"]),
                             "direct_call_count": len(function["calls"]),
                             "return_count": len(function["returns"]),
                             "canonical_instruction_bytes_sha256":
                                 function["canonical_instruction_bytes_sha256"],
                             "raw_halfwords_omitted": True},
            "verified_behavior": {"instruction_form": instruction_form(function),
                                  "sGpuBgConfigs_address": f"0x{bg_control:08X}",
                                  "bgVisibilityAndMode_address": f"0x{bg_control + 0x10:08X}",
                                  "bgVisibilityAndMode_value": 0,
                                  "callee_relative_offsets": [0x44, 0x3CC]},
            "cross_reference": {"clear_dma3_requests_map": prior_path.as_posix(),
                                "clear_dma3_requests_map_sha256": file_hash(root / prior_path)},
            "naming_basis": {"repository": repository, "commit": commit,
                             "path": "src/bg.c"}, "raw_rom_bytes_included": False,
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
               "function": "ResetBgs", "family_profile": family,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/reset-bgs-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/reset-bgs-disassembly.md")
    (root / research_path).write_text(
        f"# {game} ResetBgs disassembly\n\n`{releases[0]['id']}` is the Japanese "
        f"origin reference. All {len(records)} cataloged releases ({languages}) resolve "
        "the boot call immediately after ClearDma3Requests. Each 20-byte wrapper resets "
        "BG control structures, clears DISPCNT, then selects text mode and hides BGs. "
        "Maps preserve addresses, call targets and hashes without ROM bytes.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_reset_bgs_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/reset-bgs-disassembly.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": "ResetBgs", "family_profile": family,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_reset_bgs.py",
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
