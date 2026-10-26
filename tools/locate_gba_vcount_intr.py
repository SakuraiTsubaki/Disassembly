#!/usr/bin/env python3
"""Locate and reconstruct the GBA VCount-line-150 interrupt setup routine."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import disassemble_thumb_cfg


FUNCTION_LENGTH = 40
PREFIX = bytes.fromhex("00b50420")
MIDDLE = (0x21FF, 0x4001, 0x2296, 0x0212, 0x1C10, 0x4301, 0x2020, 0x4301, 0x2004)
EPILOGUE = (0xBC01, 0x4700)


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


def is_bl(first: int, second: int) -> bool:
    return first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def matching_offsets(data: bytes) -> list[int]:
    matches = []
    start = 0
    while True:
        offset = data.find(PREFIX, start)
        if offset < 0:
            break
        if offset % 2 == 0 and offset + FUNCTION_LENGTH <= len(data):
            words = struct.unpack_from("<20H", data, offset)
            if (
                is_bl(words[2], words[3])
                and words[4:13] == MIDDLE
                and is_bl(words[13], words[14])
                and words[15] == 0x2004
                and is_bl(words[16], words[17])
                and words[18:20] == EPILOGUE
            ):
                matches.append(offset)
        start = offset + 2
    return matches


def unique_function_offset(data: bytes) -> int:
    matches = matching_offsets(data)
    if len(matches) != 1:
        raise ValueError(f"expected one VCount interrupt candidate, found {len(matches)}")
    return matches[0]


def reconstructed_source() -> str:
    return """.syntax unified
.thumb

.global EnableVCountIntrAtLine150
.type EnableVCountIntrAtLine150, %function
.thumb_func
EnableVCountIntrAtLine150:
    push {lr}
    movs r0, #4
    bl GetGpuReg
    movs r1, #0xff
    ands r1, r0
    movs r2, #150
    lsls r2, r2, #8
    adds r0, r2, #0
    orrs r1, r0
    movs r0, #0x20
    orrs r1, r0
    movs r0, #4
    bl SetGpuReg
    movs r0, #4
    bl EnableInterrupts
    pop {r0}
    bx r0
.size EnableVCountIntrAtLine150, . - EnableVCountIntrAtLine150
"""


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str, reference_repository: str, reference_commit: str) -> dict[str, object]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    roms = rom_index(rom_dir)
    source_path = Path("src/enable_vcount_intr_at_line150.s")
    (root / source_path).write_text(reconstructed_source(), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    outputs: list[Path] = [source_path, catalog_path]
    call_names = ("GetGpuReg", "SetGpuReg", "EnableInterrupts")
    records = []

    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        offset = unique_function_offset(data)
        cfg = disassemble_thumb_cfg.omit_raw_bytes(disassemble_thumb_cfg.analyze(data, offset, sha256, FUNCTION_LENGTH))
        expected_end = 0x08000000 + offset + FUNCTION_LENGTH
        if cfg["range_end"] != expected_end or len(cfg["returns"]) != 1 or len(cfg["calls"]) != 3:
            raise ValueError(f"CFG boundary mismatch: {release_id}")
        cfg_path = Path(f"analysis/{release_id}-enable-vcount-intr-at-line150-cfg.json")
        write_json(root / cfg_path, cfg)
        calls = [{"name": name, "source": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"} for name, call in zip(call_names, cfg["calls"])]
        code = data[offset:offset + FUNCTION_LENGTH]
        mapping = {
            "schema_version": 1,
            "axis": "disassembly",
            "target": {"release": release_id, "sha256": sha256},
            "source": source_path.as_posix(),
            "source_sha256": source_sha256,
            "function": {"name": "EnableVCountIntrAtLine150", "address": f"0x{0x08000000 + offset:08X}", "range_end_exclusive": f"0x{expected_end:08X}", "rom_code_range": {"start_offset": offset, "end_offset_exclusive": offset + FUNCTION_LENGTH, "length": FUNCTION_LENGTH, "sha256": digest(code), "raw_bytes_published": False}, "cfg": cfg_path.as_posix()},
            "calls": calls,
            "constants": {"dispstat_offset": "0x0004", "preserved_low_byte_mask": "0x00FF", "vcount_compare_line": 150, "vcount_enable_bit": "0x0020", "interrupt_flag": "0x0004"},
            "origin_reference": index == 0,
            "naming_basis": {"repository": reference_repository, "commit": reference_commit, "path": "src/main.c", "match_kind": "Thumb instruction sequence, constants, and call order", "raw_rom_bytes_published": False},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-enable-vcount-intr-at-line150-map.json")
        write_json(root / map_path, mapping)
        outputs.extend((cfg_path, map_path))
        records.append({"id": release_id, "language": release["language"], "revision": release["revision"], "build_kind": release["build_kind"], "sha256": sha256, "origin_reference": index == 0, "address": mapping["function"]["address"], "code_sha256": mapping["function"]["rom_code_range"]["sha256"], "calls": calls, "evidence": {"map": map_path.as_posix(), "cfg": cfg_path.as_posix()}})

    summary = {"schema_version": 1, "axis": "disassembly", "game": game, "function": "EnableVCountIntrAtLine150", "origin_reference": releases[0]["id"], "release_count": len(records), "source": source_path.as_posix(), "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/enable-vcount-intr-at-line150-disassembly-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/enable-vcount-intr-at-line150-disassembly.md")
    (root / research_path).write_text(
        f"# {game} EnableVCountIntrAtLine150 disassembly\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. Independent ROM scanning found exactly one matching 40-byte Thumb routine in every one of the {len(records)} cataloged releases ({languages}). Ruby and Sapphire were checked separately and do not contain this routine shape.\n\n"
        "The assembly preserves the low DISPSTAT byte, installs VCount line 150 and its enable bit, then enables interrupt flag 0x0004. Per-release CFGs omit raw instruction halfwords; maps retain only locations, hashes, constants and call targets. "
        f"Names are corroborated by `{reference_repository}` at `{reference_commit}`, `src/main.c`.\n",
        encoding="utf-8", newline="\n")
    outputs.append(research_path)
    test_path = Path("tests/test_enable_vcount_intr_disassembly.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {"schema_version": 1, "axis": "disassembly", "game": game, "function": "EnableVCountIntrAtLine150", "origin_reference": releases[0]["id"], "release_count": len(records), "generator": {"repository": "SakuraiTsubaki/Disassembly", "tool": "tools/locate_gba_vcount_intr.py", "tool_sha256": file_hash(Path(__file__))}, "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs], "raw_rom_bytes_included": False}
    write_json(root / "manifests/enable-vcount-intr-disassembly.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.reference_repository, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
