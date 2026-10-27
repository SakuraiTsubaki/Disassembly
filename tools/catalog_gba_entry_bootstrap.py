#!/usr/bin/env python3
"""Catalog GBA entry, ARM bootstrap and reachable Thumb CFG evidence."""
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
    return dict(sorted({
        kind: sum(1 for edge in edges if edge["kind"] == kind)
        for kind in {edge["kind"] for edge in edges}
    }.items()))


def entry_source() -> str:
    return """.syntax unified
.arm
.section .text.rom_entry, "ax", %progbits
.global rom_entry
.type rom_entry, %function
rom_entry:
    b rom_bootstrap
.size rom_entry, . - rom_entry
"""


def bootstrap_source() -> str:
    return """.syntax unified
.arm
.section .text.rom_bootstrap, "ax", %progbits
.global rom_bootstrap
.type rom_bootstrap, %function
.extern irq_stack_top
.extern system_stack_top
.extern interrupt_vector
.extern thumb_entry_reachable
rom_bootstrap:
    mov r0, #0x12
    msr cpsr_c, r0
    ldr sp, =irq_stack_top
    mov r0, #0x1f
    msr cpsr_c, r0
    ldr sp, =system_stack_top
    ldr r1, =interrupt_vector
    adr r0, arm_interrupt_return
    str r0, [r1]
    ldr r1, =thumb_entry_reachable + 1
    mov lr, pc
    bx r1
arm_interrupt_return:
.size rom_bootstrap, . - rom_bootstrap
"""


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str) -> dict:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    entry_source_path = Path("src/rom_entry.s")
    bootstrap_source_path = Path("src/rom_bootstrap.s")
    (root / entry_source_path).write_text(entry_source(), encoding="utf-8", newline="\n")
    (root / bootstrap_source_path).write_text(
        bootstrap_source(), encoding="utf-8", newline="\n"
    )
    entry_maps, bootstrap_maps, cfg_maps, records = [], [], [], []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        entry = disassemble_gba_entry.decode(struct.unpack_from("<I", data)[0])
        if disassemble_gba_entry.encode(
            entry["target_address"], link=entry["mnemonic"] == "bl"
        ) != entry["instruction_word"]:
            raise ValueError(f"entry round trip differs: {release_id}")
        bootstrap_offset = entry["target_address"] - ROM_BASE
        bootstrap = disassemble_gba_bootstrap.trace(data, bootstrap_offset)
        transition = bootstrap["transition"]
        if transition["target_state"] != "thumb":
            raise ValueError(f"bootstrap does not enter Thumb state: {release_id}")
        thumb_offset = transition["target_address"] - ROM_BASE
        cfg = disassemble_thumb_cfg.trace(data, thumb_offset, max_span=0x800)
        if cfg["return_observed"]:
            raise ValueError(f"Thumb entry unexpectedly returns: {release_id}")
        loops = [
            edge for edge in cfg["edges"]
            if edge["kind"] == "branch" and edge["target"] < edge["source"]
        ]
        if len(loops) != 1:
            raise ValueError(
                f"expected one Thumb main loop edge, found {len(loops)}: {release_id}"
            )

        common = {
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "raw_rom_bytes_included": False,
        }
        entry_map = {
            "schema_version": 1,
            **common,
            "source": entry_source_path.as_posix(),
            "source_sha256": file_hash(root / entry_source_path),
            "entry": {
                "address": f"0x{entry['entry_address']:08X}",
                "state": entry["execution_state"],
                "operation": entry["mnemonic"],
                "target_address": f"0x{entry['target_address']:08X}",
                "round_trip_verified": True,
                "rom_code_range": {
                    "start_offset": 0,
                    "end_offset_exclusive": 4,
                    "length": 4,
                    "sha256": digest(data[:4]),
                    "raw_bytes_published": False,
                },
            },
        }
        transition_end = bootstrap["end_offset"]
        bootstrap_map = {
            "schema_version": 1,
            **common,
            "source": bootstrap_source_path.as_posix(),
            "source_sha256": file_hash(root / bootstrap_source_path),
            "bootstrap": {
                "address": f"0x{bootstrap['start_address']:08X}",
                "instruction_count": bootstrap["instruction_count"],
                "literal_load_count": sum(
                    item["kind"] == "ldr-literal"
                    for item in bootstrap["instructions"]
                ),
                "rom_code_range": {
                    "start_offset": bootstrap_offset,
                    "end_offset_exclusive": transition_end,
                    "length": transition_end - bootstrap_offset,
                    "sha256": digest(data[bootstrap_offset:transition_end]),
                    "raw_bytes_published": False,
                },
            },
            "transition": {
                "instruction_address": f"0x{transition['instruction_address']:08X}",
                "register": transition["register"],
                "loaded_at": f"0x{transition['loaded_at']:08X}",
                "literal_address": f"0x{transition['literal_address']:08X}",
                "target_address": f"0x{transition['target_address']:08X}",
                "target_state": transition["target_state"],
            },
        }
        start, end = thumb_offset, cfg["range_end"] - ROM_BASE
        cfg_map = {
            "schema_version": 1,
            **common,
            "source": "src/thumb_entry_reachable.s",
            "function": {
                "name": "thumb_entry_reachable",
                "address": f"0x{cfg['start_address']:08X}",
                "range_end_exclusive": f"0x{cfg['range_end']:08X}",
                "nonreturning": True,
                "rom_code_range": {
                    "start_offset": start,
                    "end_offset_exclusive": end,
                    "length": end - start,
                    "sha256": digest(data[start:end]),
                    "raw_bytes_published": False,
                },
            },
            "control_flow": {
                "instruction_halfwords": cfg["instruction_halfwords"],
                "edge_count": len(cfg["edges"]),
                "edge_kinds": edge_kinds(cfg["edges"]),
                "direct_call_count": len(cfg["calls"]),
                "return_count": len(cfg["returns"]),
                "loop_back_edge": {
                    "source": f"0x{loops[0]['source']:08X}",
                    "target": f"0x{loops[0]['target']:08X}",
                },
                "canonical_instruction_bytes_sha256":
                    cfg["canonical_instruction_bytes_sha256"],
                "raw_halfwords_omitted": True,
            },
        }
        entry_path = Path(f"analysis/{release_id}-entrypoint-map.json")
        bootstrap_path = Path(f"analysis/{release_id}-bootstrap-map.json")
        cfg_path = Path(f"analysis/{release_id}-thumb-entry-cfg-map.json")
        write_json(root / entry_path, entry_map)
        write_json(root / bootstrap_path, bootstrap_map)
        write_json(root / cfg_path, cfg_map)
        entry_maps.append(entry_path)
        bootstrap_maps.append(bootstrap_path)
        cfg_maps.append(cfg_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "entry_target": entry_map["entry"]["target_address"],
            "thumb_target": bootstrap_map["transition"]["target_address"],
            "evidence": {
                "entrypoint": entry_path.as_posix(),
                "bootstrap": bootstrap_path.as_posix(),
                "thumb_cfg": cfg_path.as_posix(),
            },
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/entry-bootstrap-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research = {
        Path("research/entrypoint-reconstruction.md"):
            f"# {game} entrypoint disassembly\n\nThe Japanese release `{releases[0]['id']}` is the origin reference. All {len(records)} cataloged releases ({languages}) have a round-trip-verified ARM entry branch. Per-release maps retain targets and range hashes without publishing encoded words.\n",
        Path("research/bootstrap-transition.md"):
            f"# {game} bootstrap disassembly\n\nAll {len(records)} cataloged releases were traced through the first literal-backed ARM register branch. Every build enters Thumb state; maps retain structure, addresses and hashes without raw words or literal values.\n",
        Path("research/thumb-entry-cfg.md"):
            f"# {game} reachable Thumb entry CFG\n\nAll {len(records)} cataloged releases have one non-returning backward main-loop edge. Compact maps retain range and canonical reachable-code hashes, call and edge counts, and omit instruction halfwords.\n",
    }
    for path, text in research.items():
        (root / path).write_text(text, encoding="utf-8", newline="\n")
    tests = {
        "entrypoint": Path("tests/test_entrypoint.py"),
        "bootstrap": Path("tests/test_bootstrap.py"),
        "thumb-cfg": Path("tests/test_thumb_cfg.py"),
    }
    groups = {
        "entrypoint": [
            catalog_path, entry_source_path, summary_path, *entry_maps,
            Path("research/entrypoint-reconstruction.md"), tests["entrypoint"],
        ],
        "bootstrap": [
            catalog_path, bootstrap_source_path, summary_path, *bootstrap_maps,
            Path("research/bootstrap-transition.md"), tests["bootstrap"],
        ],
        "thumb-cfg": [
            catalog_path, summary_path, *cfg_maps,
            Path("research/thumb-entry-cfg.md"), tests["thumb-cfg"],
        ],
    }
    generator = {
        "repository": "SakuraiTsubaki/Disassembly",
        "tool": "tools/catalog_gba_entry_bootstrap.py",
        "tool_sha256": file_hash(Path(__file__)),
    }
    for name, outputs in groups.items():
        missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
        if missing:
            raise ValueError("missing output(s): " + ", ".join(missing))
        write_json(root / f"manifests/{name}.json", {
            "schema_version": 1,
            "game": game,
            "evidence_kind": name,
            "origin_reference": releases[0]["id"],
            "release_count": len(records),
            "generator": generator,
            "outputs": [
                {"path": path.as_posix(), "sha256": file_hash(root / path)}
                for path in outputs
            ],
            "raw_rom_bytes_included": False,
        })
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
