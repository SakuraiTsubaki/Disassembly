#!/usr/bin/env python3
"""Trace and catalog InitMainCallbacks in Gen III Disassembly projects."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gba_check_flash_memory
import disassemble_thumb_cfg


ROM_BASE = 0x08000000
PROFILES = {
    "rs": {"shape": (22, 11, 1, 1, 0), "form": "rs-base",
           "repository": "pret/pokeruby",
           "commit": "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f", "path": "src/main.c",
           "zeroed": ["gMain.vblankCounter1", "gMain.vblankCounter2", "gMain.callback1"],
           "pointers": []},
    "emerald": {"shape": (38, 19, 1, 1, 0), "form": "emerald-storage",
                "repository": "pret/pokeemerald",
                "commit": "fe1d8e51b265851676b65885818b1f5f62586135", "path": "src/main.c",
                "zeroed": ["gMain.vblankCounter1", "gTrainerHillVBlankCounter",
                           "gMain.vblankCounter2", "gMain.callback1"],
                "pointers": ["gSaveBlock2Ptr", "gPokemonStoragePtr"]},
    "frlg": {"shape": (48, 24, 1, 1, 0), "form": "frlg-save-blocks",
             "repository": "pret/pokefirered",
             "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14", "path": "src/main.c",
             "zeroed": ["gMain.vblankCounter1", "gMain.vblankCounter2", "gMain.callback1",
                        "gSaveBlock2EncryptionKey", "gQuestLogPlaybackState"],
             "pointers": ["gSaveBlock2Ptr", "gSaveBlock1Ptr"]},
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


def shape(cfg: dict) -> tuple[int, int, int, int, int]:
    return (cfg["range_end"] - cfg["start_address"], cfg["instruction_halfwords"],
            len(cfg["calls"]), len(cfg["returns"]), len(cfg["edges"]))


def instruction_form(cfg: dict) -> str:
    halfwords = [item["halfword"] for item in
                 sorted(cfg["instructions"], key=lambda item: item["address"])]
    if (len(halfwords) == 11 and halfwords[:4] == [0xB500, halfwords[1], 0x2100, 0x6201]
            and halfwords[1] & 0xF800 == 0x4800
            and halfwords[4:6] == [0x6241, 0x6001]
            and halfwords[-2:] == [0xBC01, 0x4700]):
        return "rs-base"
    if (len(halfwords) == 19 and halfwords[0] == 0xB500
            and halfwords[2:4] == [0x2000, 0x6210]
            and halfwords[5:8] == [0x6008, 0x6250, 0x6010]
            and halfwords[-2:] == [0xBC01, 0x4700]):
        return "emerald-storage"
    if (len(halfwords) == 24 and halfwords[0] == 0xB510
            and halfwords[2:6] == [0x2400, 0x6204, 0x6244, 0x6004]
            and halfwords[-3:] == [0xBC10, 0xBC01, 0x4700]):
        return "frlg-save-blocks"
    return "unknown"


def locate_from_boot(data: bytes) -> tuple[dict, dict, dict]:
    caller, flash = catalog_gba_check_flash_memory.locate(data)
    calls = sorted(caller["calls"], key=lambda item: item["source"])
    indices = [index for index, call in enumerate(calls)
               if call["target"] == flash["start_address"]]
    if len(indices) != 1 or indices[0] + 1 >= len(calls):
        raise ValueError("could not resolve the call immediately after CheckForFlashMemory")
    call = calls[indices[0] + 1]
    function = disassemble_thumb_cfg.trace(data, call["target"] - ROM_BASE, max_span=0x400)
    return caller, call, function


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    profile = PROFILES[family]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/init_main_callbacks.s")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in ("InitMainCallbacks:", "SetMainCallback2", "Copyright", "gMain"):
        if token not in source:
            raise ValueError(f"disassembly source is missing token: {token}")
    for token in profile["pointers"]:
        if token not in source:
            raise ValueError(f"disassembly source is missing profile token: {token}")

    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        caller, boot_call, function = locate_from_boot(data)
        actual_shape, actual_form = shape(function), instruction_form(function)
        if actual_shape != profile["shape"]:
            raise ValueError(f"InitMainCallbacks structural signature differs: {release_id}")
        if actual_form != profile["form"]:
            raise ValueError(f"InitMainCallbacks instruction form differs: {release_id}")
        call = function["calls"][0]
        start, end = function["start_address"] - ROM_BASE, function["range_end"] - ROM_BASE
        check_path = Path(f"analysis/{release_id}-check-flash-memory-disassembly.json")
        check = json.loads((root / check_path).read_text(encoding="utf-8"))
        if int(check["function"]["address"], 16) not in {
                item["target"] for item in caller["calls"]}:
            raise ValueError(f"CheckForFlashMemory cross-reference differs: {release_id}")
        output = Path(f"analysis/{release_id}-init-main-callbacks-disassembly.json")
        evidence = {
            "schema_version": 1, "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0, "axis": "Disassembly",
            "source": source_path.as_posix(), "source_sha256": file_hash(root / source_path),
            "discovery": {"caller": "thumb_entry_reachable",
                          "caller_address": f"0x{caller['start_address']:08X}",
                          "boot_call_source": f"0x{boot_call['source']:08X}",
                          "rule": "direct boot call immediately after CheckForFlashMemory"},
            "function": {"name": "InitMainCallbacks",
                         "address": f"0x{function['start_address']:08X}",
                         "range_end_exclusive": f"0x{function['range_end']:08X}",
                         "rom_code_range": {"start_offset": start,
                                            "end_offset_exclusive": end,
                                            "length": end - start,
                                            "sha256": digest(data[start:end]),
                                            "raw_bytes_published": False},
                         "calls": [{"name": "SetMainCallback2",
                                    "source": f"0x{call['source']:08X}",
                                    "target": f"0x{call['target']:08X}"}]},
            "control_flow": {"instruction_halfwords": function["instruction_halfwords"],
                             "edge_count": len(function["edges"]),
                             "direct_call_count": len(function["calls"]),
                             "return_count": len(function["returns"]),
                             "canonical_instruction_bytes_sha256":
                                 function["canonical_instruction_bytes_sha256"],
                             "raw_halfwords_omitted": True},
            "verified_behavior": {"instruction_form": actual_form,
                                  "zeroed_state": profile["zeroed"],
                                  "initialized_pointers": profile["pointers"],
                                  "callback2_initializer": "copyright-screen initializer"},
            "cross_reference": {"check_flash_memory_map": check_path.as_posix(),
                                "check_flash_memory_map_sha256": file_hash(root / check_path)},
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
                        "instruction_form": actual_form,
                        "code_sha256": evidence["function"]["rom_code_range"]["sha256"],
                        "evidence": output.as_posix()})

    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "function": "InitMainCallbacks", "family_profile": family,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/init-main-callbacks-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/init-main-callbacks-disassembly.md")
    (root / research_path).write_text(
        f"# {game} InitMainCallbacks disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) independently resolve the direct boot call "
        "immediately after CheckForFlashMemory and preserve the family-specific "
        f"`{profile['form']}` structure. The routine clears callback state, installs "
        "the copyright-screen callback through SetMainCallback2, and performs the "
        "profile-specific pointer initialization. Maps publish structure and hashes, "
        "never ROM bytes or halfwords.\n", encoding="utf-8", newline="\n")
    test_path = Path("tests/test_init_main_callbacks_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/init-main-callbacks-disassembly.json", {
        "schema_version": 1, "game": game, "axis": "Disassembly",
        "function": "InitMainCallbacks", "family_profile": family,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_init_main_callbacks.py",
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
