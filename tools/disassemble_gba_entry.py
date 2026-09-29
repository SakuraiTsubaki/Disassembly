#!/usr/bin/env python3
"""Disassemble and round-trip the ARM branch at a GBA ROM entry point."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

ROM_BASE = 0x08000000


def decode(word: int, address: int = ROM_BASE) -> dict:
    opcode = word >> 24
    if opcode not in (0xEA, 0xEB):
        raise ValueError("entry word is not an ARM B/BL immediate")
    immediate = word & 0x00FFFFFF
    if immediate & 0x00800000:
        immediate -= 0x01000000
    displacement = immediate << 2
    return {
        "schema_version": 1,
        "entry_address": address,
        "instruction_word": word,
        "instruction_bytes_le": struct.pack("<I", word).hex(),
        "mnemonic": "bl" if opcode == 0xEB else "b",
        "displacement": displacement,
        "target_address": (address + 8 + displacement) & 0xFFFFFFFF,
        "execution_state": "arm",
    }


def encode(target: int, address: int = ROM_BASE, link: bool = False) -> int:
    displacement = target - (address + 8)
    if displacement % 4:
        raise ValueError("ARM branch target must be word-aligned")
    immediate = displacement // 4
    if not -(1 << 23) <= immediate < (1 << 23):
        raise ValueError("ARM branch target is out of range")
    return (0xEB000000 if link else 0xEA000000) | (immediate & 0x00FFFFFF)


def analyze(data: bytes, expected_sha256: str | None = None) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    if len(data) < 4:
        raise ValueError("ROM is shorter than the entry word")
    result = decode(struct.unpack_from("<I", data)[0])
    if encode(result["target_address"], link=result["mnemonic"] == "bl") != result["instruction_word"]:
        raise ValueError("entry branch failed round-trip encoding")
    result.update({"source_size": len(data), "source_sha256": digest, "round_trip_verified": True})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = analyze(args.rom.read_bytes(), args.expected_sha256)
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
