#!/usr/bin/env python3
"""Trace and catalog InitMapMusic in Gen III Disassembly projects."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gba_init_main_callbacks
import disassemble_thumb_cfg


ROM_BASE = 0x08000000
SHAPE = (16, 8, 1, 1, 0)
PROFILES = {
    "rs": ("pret/pokeruby", "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f"),
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
    if (len(halfwords) == 8 and halfwords[0] == 0xB500
            and halfwords[1] & 0xFF00 == 0x4900
            and halfwords[2:4] == [0x2000, 0x7008]
            and halfwords[-2:] == [0xBC01, 0x4700]):
        return "clear-iwram-byte-then-call"
    return "unknown"


def locate_from_boot(data: bytes) -> tuple[dict, dict, dict]:
    caller, _, init_callbacks = catalog_gba_init_main_callbacks.locate_from_boot(data)
    calls = sorted(caller["calls"], key=lambda item: item["source"])
    indices = [index for index, call in enumerate(calls)
               if call["target"] == init_callbacks["start_address"]]
    if len(indices) != 1 or indices[0] + 1 >= len(calls):
        raise ValueError("could not resolve the call immediately after InitMainCallbacks")
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
    source_path = Path("src/init_map_music.s")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in ("InitMapMusic:", "gDisableMusic", "movs r0, #0",
                  "bl ResetMapMusic"):
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
        if shape(function) != SHAPE:
            raise ValueError(f"InitMapMusic structural signature differs: {release_id}")
        form = instruction_form(function)
        if form != "clear-iwram-byte-then-call":
            raise ValueError(f"InitMapMusic instruction form differs: {release_id}")
        call = function["calls"][0]
        if call["target"] != function["start_address"] + 0x10C:
            raise ValueError(f"ResetMapMusic relative target differs: {release_id}")
        start, end = function["start_address"] - ROM_BASE, function["range_end"] - ROM_BASE
        disable_music = struct.unpack_from("<I", data, end)[0]
        if not 0x03000000 <= disable_music <= 0x03007FFF:
            raise ValueError(f"gDisableMusic literal is outside IWRAM: {release_id}")
        init_path = Path(f"analysis/{release_id}-init-main-callbacks-disassembly.json")
        init_map = json.loads((root / init_path).read_text(encoding="utf-8"))
        if int(init_map["function"]["address"], 16) not in {
                item["target"] for item in caller["calls"]}:
            raise ValueError(f"InitMainCallbacks cross-reference differs: {release_id}")
        output = Path(f"analysis/{release_id}-init-map-music-disassembly.json")
        evidence = {
            "schema_version": 1, "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0, "axis": "Disassembly",
            "source": source_path.as_posix(), "source_sha256": file_hash(root / source_path),
            "discovery": {"caller": "thumb_entry_reachable",
                          "caller_address": f"0x{caller['start_address']:08X}",
                          "boot_call_source": f"0x{boot_call['source']:08X}",
                          "rule": "direct boot call immediately after InitMainCallbacks"},
            "function": {"name": "InitMapMusic",
                         "address": f"0x{function['start_address']:08X}",
                         "range_end_exclusive": f"0x{function['range_end']:08X}",
                         "rom_code_range": {"start_offset": start,
                                            "end_offset_exclusive": end,
                                            "length": end - start,
                                            "sha256": digest(data[start:end]),
                                            "raw_bytes_published": False},
                         "calls": [{"name": "ResetMapMusic",
                                    "source": f"0x{call['source']:08X}",
                                    "target": f"0x{call['target']:08X}"}]},
            "control_flow": {"instruction_halfwords": function["instruction_halfwords"],
                             "edge_count": len(function["edges"]),
                             "direct_call_count": len(function["calls"]),
                             "return_count": len(function["returns"]),
                             "canonical_instruction_bytes_sha256":
                                 function["canonical_instruction_bytes_sha256"],
                             "raw_halfwords_omitted": True},
            "verified_behavior": {"instruction_form": form,
                                  "gDisableMusic_address": f"0x{disable_music:08X}",
                                  "gDisableMusic_value": 0,
                                  "then_calls": "ResetMapMusic",
                                  "reset_map_music_relative_offset": 0x10C},
            "cross_reference": {"init_main_callbacks_map": init_path.as_posix(),
                                "init_main_callbacks_map_sha256": file_hash(root / init_path)},
            "naming_basis": {"repository": repository, "commit": commit,
                             "path": "src/sound.c"},
            "raw_rom_bytes_included": False,
        }
        write_json(root / output, evidence)
        maps.append(output)
        records.append({"id": release_id, "language": release["language"],
                        "revision": release["revision"], "build_kind": release["build_kind"],
                        "sha256": sha256, "origin_reference": index == 0,
                        "address": evidence["function"]["address"],
                        "gDisableMusic_address": evidence["verified_behavior"]["gDisableMusic_address"],
                        "code_sha256": evidence["function"]["rom_code_range"]["sha256"],
                        "evidence": output.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "function": "InitMapMusic", "family_profile": family,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/init-map-music-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/init-map-music-disassembly.md")
    (root / research_path).write_text(
        f"# {game} InitMapMusic disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) independently resolve the direct boot call "
        "immediately after InitMainCallbacks. Every 16-byte routine clears a verified "
        "IWRAM gDisableMusic byte and calls ResetMapMusic at relative target +0x10C. "
        "Maps publish addresses, structure and hashes, never ROM bytes or halfwords.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_init_map_music_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/init-map-music-disassembly.json", {
        "schema_version": 1, "game": game, "axis": "Disassembly",
        "function": "InitMapMusic", "family_profile": family,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gba_init_map_music.py",
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
