#!/usr/bin/env python3
"""Catalog the repeatedly called local Thumb target for GBA releases."""
from __future__ import annotations

import argparse
from collections import Counter
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


def edge_kinds(edges: list[dict]) -> dict[str, int]:
    kinds = {edge["kind"] for edge in edges}
    return {kind: sum(edge["kind"] == kind for edge in edges) for kind in sorted(kinds)}


def unique_repeated_target(calls: list[dict], frequency: int = 3) -> int:
    counts = Counter(call["target"] for call in calls)
    matches = [target for target, count in counts.items() if count == frequency]
    other_repeated = [target for target, count in counts.items() if count > 1 and count != frequency]
    if len(matches) != 1 or other_repeated:
        raise ValueError("expected one uniquely repeated direct-call target")
    return matches[0]


def locate(data: bytes) -> tuple[dict, dict, int]:
    entry = disassemble_gba_entry.decode(struct.unpack_from("<I", data)[0])
    bootstrap = disassemble_gba_bootstrap.trace(data, entry["target_address"] - ROM_BASE)
    transition = bootstrap["transition"]
    if transition["target_state"] != "thumb":
        raise ValueError("bootstrap does not enter Thumb state")
    caller = disassemble_thumb_cfg.trace(
        data, transition["target_address"] - ROM_BASE, max_span=0x800
    )
    target = unique_repeated_target(caller["calls"])
    if not caller["start_address"] <= target <= caller["range_end"] + 8:
        raise ValueError("repeated target is not adjacent to the main Thumb body")
    function = disassemble_thumb_cfg.trace(data, target - ROM_BASE, max_span=0x400)
    if not function["return_observed"] or len(function["returns"]) != 1:
        raise ValueError("repeated target does not have one observed return")
    return caller, function, target


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str) -> dict:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        caller, function, target = locate(data)
        start = target - ROM_BASE
        end = function["range_end"] - ROM_BASE
        output = Path(f"analysis/{release_id}-repeated-callback-cfg-map.json")
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "discovery": {
                "caller": "thumb_entry_reachable",
                "caller_address": f"0x{caller['start_address']:08X}",
                "repeated_direct_call_count": 3,
                "target_address": f"0x{target:08X}",
            },
            "function": {
                "name": "repeated_callback_target",
                "address": f"0x{target:08X}",
                "range_end_exclusive": f"0x{function['range_end']:08X}",
                "rom_code_range": {
                    "start_offset": start,
                    "end_offset_exclusive": end,
                    "length": end - start,
                    "sha256": digest(data[start:end]),
                    "raw_bytes_published": False,
                },
            },
            "control_flow": {
                "instruction_halfwords": function["instruction_halfwords"],
                "edge_count": len(function["edges"]),
                "edge_kinds": edge_kinds(function["edges"]),
                "direct_call_count": len(function["calls"]),
                "return_count": len(function["returns"]),
                "canonical_instruction_bytes_sha256":
                    function["canonical_instruction_bytes_sha256"],
                "raw_halfwords_omitted": True,
            },
            "raw_rom_bytes_included": False,
        }
        write_json(root / output, evidence)
        maps.append(output)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "target_address": evidence["discovery"]["target_address"],
            "instruction_halfwords": function["instruction_halfwords"],
            "direct_call_count": len(function["calls"]),
            "evidence": output.as_posix(),
        })

    summary = {
        "schema_version": 1,
        "axis": "Disassembly",
        "game": game,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "discovery_rule": "unique target called exactly three times by thumb_entry_reachable",
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/repeated-callback-cfg-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/repeated-callback-cfg.md")
    (root / research_path).write_text(
        f"# {game} repeated callback CFG\n\n"
        f"The Japanese release `{releases[0]['id']}` remains the origin reference. "
        f"For all {len(records)} cataloged releases ({languages}), the reachable Thumb "
        "main body has exactly one direct-call target referenced three times. Each "
        "per-release map independently traces that target through its observed return "
        "and preserves addresses, structure, and hashes without publishing ROM bytes "
        "or instruction halfwords.\n",
        encoding="utf-8", newline="\n"
    )
    test_path = Path("tests/test_repeated_callback_cfg.py")
    outputs = [catalog_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "game": game,
        "evidence_kind": "repeated-callback-cfg",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gba_repeated_callback_cfg.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [
            {"path": path.as_posix(), "sha256": file_hash(root / path)}
            for path in outputs
        ],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/repeated-callback-cfg.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--game", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
