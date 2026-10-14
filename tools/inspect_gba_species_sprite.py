#!/usr/bin/env python3
"""Identify a GBA species sprite sheet table entry and its table xrefs."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "trace_gba_lz77_load", Path(__file__).with_name("trace_gba_lz77_load.py")
)
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)

ENTRY_SIZE = 8


def _locations(data: bytes, value: int) -> list[int]:
    encoded = value.to_bytes(4, "little")
    result = []
    cursor = 0
    while True:
        cursor = data.find(encoded, cursor)
        if cursor < 0:
            return result
        result.append(cursor)
        cursor += 1


def _thumb_literal_refs(data: bytes, literal_offsets: list[int], search_back: int = 0x800) -> list[dict]:
    refs = []
    for literal in literal_offsets:
        for offset in range(max(0, literal - search_back), literal, 2):
            instruction = int.from_bytes(data[offset : offset + 2], "little")
            if _BASE.literal_target(offset, instruction) == literal:
                refs.append(
                    {
                        "instruction_offset": offset,
                        "literal_offset": literal,
                        "destination_register": (instruction >> 8) & 7,
                    }
                )
    return refs


def inspect_bytes(data: bytes, source_offset: int, species: int) -> dict:
    if not 0 <= source_offset < len(data) or data[source_offset] != 0x10:
        raise ValueError("source is not a GBA BIOS LZ77 stream")
    if not 0 <= species <= 0xFFFF:
        raise ValueError("species must fit in a u16")

    source_pointer = _BASE.ROM_BASE + source_offset
    entries = []
    for entry_offset in _locations(data, source_pointer):
        if entry_offset + ENTRY_SIZE > len(data):
            continue
        size = int.from_bytes(data[entry_offset + 4 : entry_offset + 6], "little")
        tag = int.from_bytes(data[entry_offset + 6 : entry_offset + 8], "little")
        if tag != species:
            continue
        table_offset = entry_offset - species * ENTRY_SIZE
        if table_offset < 0:
            continue
        table_pointer = _BASE.ROM_BASE + table_offset
        table_pointer_locations = _locations(data, table_pointer)
        entries.append(
            {
                "entry_offset": entry_offset,
                "data_pointer": source_pointer,
                "size": size,
                "tag": tag,
                "table_offset": table_offset,
                "table_pointer": table_pointer,
                "table_pointer_locations": table_pointer_locations,
                "table_thumb_references": _thumb_literal_refs(data, table_pointer_locations),
            }
        )
    if len(entries) != 1:
        raise ValueError(f"expected one species sprite entry, found {len(entries)}")
    return {
        "asset": {
            "source_offset": source_offset,
            "source_pointer": source_pointer,
            "decompressed_length": int.from_bytes(data[source_offset + 1 : source_offset + 4], "little"),
        },
        "species": species,
        "entries": entries,
        "raw_bytes_published": False,
    }


def inspect(path: Path, source_offset: int, species: int, expected_sha256: str | None = None) -> dict:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    result = inspect_bytes(data, source_offset, species)
    result.update({"schema_version": 1, "source_size": len(data), "source_sha256": digest})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--source-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--species", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.rom, args.source_offset, args.species, args.expected_sha256)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
