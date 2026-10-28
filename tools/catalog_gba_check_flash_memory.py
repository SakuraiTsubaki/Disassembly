#!/usr/bin/env python3
"""Locate and catalog CheckForFlashMemory in Gen III ROM releases."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import disassemble_gba_bootstrap
import disassemble_gba_entry
import disassemble_thumb_cfg


ROM_BASE = 0x08000000
SHAPE = (38, 17, 2, 1, 3)
PROFILES = {
    "rs": ("pret/pokeruby", "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f", "src/load_save.c"),
    "emerald": ("pret/pokeemerald", "fe1d8e51b265851676b65885818b1f5f62586135", "src/load_save.c"),
    "frlg": ("pret/pokefirered", "037335f4c725d7c9aecdac87066f2002b4bd7e14", "src/load_save.c"),
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


def locate(data: bytes) -> tuple[dict, dict]:
    entry = disassemble_gba_entry.decode(struct.unpack_from("<I", data)[0])
    bootstrap = disassemble_gba_bootstrap.trace(data, entry["target_address"] - ROM_BASE)
    transition = bootstrap["transition"]
    if transition["target_state"] != "thumb":
        raise ValueError("bootstrap does not enter Thumb state")
    caller = disassemble_thumb_cfg.trace(
        data, transition["target_address"] - ROM_BASE, max_span=0x1000
    )
    matches = []
    for target in sorted({call["target"] for call in caller["calls"]}):
        if not ROM_BASE <= target < ROM_BASE + len(data):
            continue
        candidate = disassemble_thumb_cfg.trace(data, target - ROM_BASE, max_span=0x800)
        if shape(candidate) == SHAPE:
            kinds = sorted(edge["kind"] for edge in candidate["edges"])
            if kinds == ["branch", "conditional-fallthrough", "conditional-taken"]:
                matches.append(candidate)
    if len(matches) != 1:
        raise ValueError(f"expected one flash-detection signature, found {len(matches)}")
    return caller, matches[0]


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          family: str) -> dict:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/check_flash_memory.s")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in ("CheckForFlashMemory:", "bl IdentifyFlash", "bl InitFlashTimer",
                  "gFlashMemoryPresent"):
        if token not in source:
            raise ValueError(f"disassembly source is missing token: {token}")
    repository, commit, reference_path = PROFILES[family]
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        caller, function = locate(data)
        start = function["start_address"] - ROM_BASE
        end = function["range_end"] - ROM_BASE
        calls = sorted(function["calls"], key=lambda item: item["source"])
        output = Path(f"analysis/{release_id}-check-flash-memory-disassembly.json")
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "axis": "Disassembly",
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "discovery": {
                "caller": "thumb_entry_reachable",
                "caller_address": f"0x{caller['start_address']:08X}",
                "rule": "unique direct target matching the flash-detection CFG signature",
            },
            "function": {
                "name": "CheckForFlashMemory",
                "address": f"0x{function['start_address']:08X}",
                "range_end_exclusive": f"0x{function['range_end']:08X}",
                "rom_code_range": {
                    "start_offset": start, "end_offset_exclusive": end,
                    "length": end - start, "sha256": digest(data[start:end]),
                    "raw_bytes_published": False,
                },
                "calls": [
                    {"name": name, "source": f"0x{call['source']:08X}",
                     "target": f"0x{call['target']:08X}"}
                    for name, call in zip(("IdentifyFlash", "InitFlashTimer"), calls)
                ],
            },
            "control_flow": {
                "instruction_halfwords": function["instruction_halfwords"],
                "edge_count": len(function["edges"]),
                "edge_kinds": {
                    kind: sum(edge["kind"] == kind for edge in function["edges"])
                    for kind in sorted({edge["kind"] for edge in function["edges"]})
                },
                "direct_call_count": len(calls),
                "return_count": len(function["returns"]),
                "canonical_instruction_bytes_sha256":
                    function["canonical_instruction_bytes_sha256"],
                "raw_halfwords_omitted": True,
            },
            "naming_basis": {
                "repository": repository, "commit": commit, "path": reference_path,
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        write_json(root / output, evidence)
        maps.append(output)
        records.append({
            "id": release_id, "language": release["language"],
            "revision": release["revision"], "build_kind": release["build_kind"],
            "sha256": sha256, "origin_reference": index == 0,
            "address": evidence["function"]["address"],
            "code_sha256": evidence["function"]["rom_code_range"]["sha256"],
            "evidence": output.as_posix(),
        })

    summary = {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": "CheckForFlashMemory", "origin_reference": releases[0]["id"],
        "release_count": len(records), "source": source_path.as_posix(),
        "releases": records, "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/check-flash-memory-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/check-flash-memory-disassembly.md")
    (root / research_path).write_text(
        f"# {game} CheckForFlashMemory disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) independently resolve one boot-call target "
        "with the 38-byte flash-detection CFG. The two calls are named from the pinned "
        f"`{repository}` source at `{commit}`. Maps publish addresses and hashes, not "
        "ROM bytes or instruction halfwords.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_check_flash_memory_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/check-flash-memory-disassembly.json", {
        "schema_version": 1, "game": game, "axis": "Disassembly",
        "function": "CheckForFlashMemory", "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gba_check_flash_memory.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)}
                    for path in outputs],
        "raw_rom_bytes_included": False,
    })
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
