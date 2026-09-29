#!/usr/bin/env python3
"""Disassemble the initial GBA ARM bootstrap through its first literal-backed BX."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

ROM_BASE = 0x08000000


def trace(data: bytes, start_offset: int, max_words: int = 64) -> dict:
    if start_offset < 0 or start_offset % 4:
        raise ValueError("start offset must be nonnegative and word-aligned")
    if start_offset + 4 > len(data):
        raise ValueError("start offset is outside the ROM")
    loads: dict[int, dict] = {}
    instructions = []
    transition = None
    for index in range(max_words):
        offset = start_offset + index * 4
        if offset + 4 > len(data):
            break
        raw = data[offset:offset + 4]
        word = struct.unpack("<I", raw)[0]
        address = ROM_BASE + offset
        item = {"address": address, "word": word, "bytes_le": raw.hex(), "kind": "other"}
        if word & 0x0FFFFFF0 == 0x012FFF10:
            register = word & 15
            item.update({"kind": "bx", "register": register})
            source = loads.get(register)
            if source:
                value = source["value"]
                transition = {
                    "instruction_address": address,
                    "register": register,
                    "loaded_at": source["instruction_address"],
                    "literal_address": source["literal_address"],
                    "raw_target": value,
                    "target_address": value & ~1,
                    "target_state": "thumb" if value & 1 else "arm",
                }
            instructions.append(item)
            break
        if word & 0x0E5F0000 == 0x041F0000 and word & (1 << 20):
            register = (word >> 12) & 15
            immediate = word & 0xFFF
            literal_address = address + 8 + (immediate if word & (1 << 23) else -immediate)
            literal_offset = literal_address - ROM_BASE
            if not 0 <= literal_offset <= len(data) - 4:
                raise ValueError("literal load points outside the ROM")
            value = struct.unpack_from("<I", data, literal_offset)[0]
            item.update({"kind": "ldr-literal", "register": register, "literal_address": literal_address, "value": value})
            loads[register] = {"instruction_address": address, "literal_address": literal_address, "value": value}
        instructions.append(item)
    if transition is None:
        raise ValueError("no literal-backed BX transition found within scan limit")
    end_offset = start_offset + len(instructions) * 4
    return {
        "schema_version": 1,
        "rom_base": ROM_BASE,
        "start_offset": start_offset,
        "start_address": ROM_BASE + start_offset,
        "end_offset": end_offset,
        "instruction_count": len(instructions),
        "instruction_bytes_sha256": hashlib.sha256(data[start_offset:end_offset]).hexdigest(),
        "instructions": instructions,
        "transition": transition,
    }


def analyze(data: bytes, start_offset: int, expected_sha256: str | None = None, max_words: int = 64) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    result = trace(data, start_offset, max_words)
    result.update({"source_size": len(data), "source_sha256": digest})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--start-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--max-words", type=int, default=64)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = analyze(args.rom.read_bytes(), args.start_offset, args.expected_sha256, args.max_words)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
