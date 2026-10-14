#!/usr/bin/env python3
"""Trace GBA LZ77 asset pointers into direct Thumb loader call sites."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROM_BASE = 0x08000000


def decode_thumb_bl(data: bytes, offset: int) -> int | None:
    if offset + 4 > len(data):
        return None
    high = int.from_bytes(data[offset : offset + 2], "little")
    low = int.from_bytes(data[offset + 2 : offset + 4], "little")
    if high & 0xF800 != 0xF000 or low & 0xF800 != 0xF800:
        return None
    value = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if value & (1 << 22):
        value -= 1 << 23
    return ROM_BASE + offset + 4 + value


def literal_target(offset: int, instruction: int) -> int | None:
    if instruction & 0xF800 != 0x4800:
        return None
    return ((offset + 4) & ~3) + (instruction & 0xFF) * 4


def trace(data: bytes, source_offset: int, search_back: int = 0x800) -> dict:
    if not 0 <= source_offset < len(data):
        raise ValueError("source offset is outside ROM")
    if data[source_offset] != 0x10:
        raise ValueError("source does not begin with a GBA BIOS LZ77 header")
    source_pointer = ROM_BASE + source_offset
    encoded = source_pointer.to_bytes(4, "little")
    pointer_locations = []
    cursor = 0
    while True:
        cursor = data.find(encoded, cursor)
        if cursor < 0:
            break
        pointer_locations.append(cursor)
        cursor += 1
    references = []
    for literal in pointer_locations:
        for instruction_offset in range(max(0, literal - search_back), literal, 2):
            instruction = int.from_bytes(data[instruction_offset : instruction_offset + 2], "little")
            if literal_target(instruction_offset, instruction) != literal:
                continue
            register = (instruction >> 8) & 7
            item = {
                "instruction_offset": instruction_offset,
                "literal_offset": literal,
                "destination_register": register,
            }
            next_offset = instruction_offset + 2
            next_instruction = int.from_bytes(data[next_offset : next_offset + 2], "little")
            destination_literal = literal_target(next_offset, next_instruction)
            call_offset = instruction_offset + 4
            call_target = decode_thumb_bl(data, call_offset)
            if register == 0 and destination_literal is not None and call_target is not None:
                item.update(
                    {
                        "destination_literal_offset": destination_literal,
                        "destination": int.from_bytes(
                            data[destination_literal : destination_literal + 4], "little"
                        ),
                        "call_offset": call_offset,
                        "call_target": call_target,
                        "loader_sequence_length": 8,
                        "loader_sequence_sha256": hashlib.sha256(
                            data[instruction_offset : instruction_offset + 8]
                        ).hexdigest(),
                    }
                )
            references.append(item)
    return {
        "asset": {
            "source_offset": source_offset,
            "source_pointer": source_pointer,
            "decompressed_length": int.from_bytes(data[source_offset + 1 : source_offset + 4], "little"),
        },
        "pointer_locations": pointer_locations,
        "thumb_references": references,
        "raw_bytes_published": False,
    }


def inspect(path: Path, source_offset: int, expected_sha256: str | None = None) -> dict:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    result = trace(data, source_offset)
    result.update({"schema_version": 1, "source_size": len(data), "source_sha256": digest})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--source-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.rom, args.source_offset, args.expected_sha256)
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
