#!/usr/bin/env python3
"""Disassemble the fixed four-byte LR35902 cartridge entry sequence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ENTRY_OFFSET = 0x100
ENTRY_SIZE = 4


def decode(raw: bytes) -> dict:
    if len(raw) != ENTRY_SIZE:
        raise ValueError("entry sequence must be exactly four bytes")
    if raw[0] != 0x00 or raw[1] != 0xC3:
        raise ValueError("entry sequence is not NOP followed by JP nn")
    target = raw[2] | raw[3] << 8
    return {
        "schema_version": 1,
        "entry_offset": ENTRY_OFFSET,
        "entry_bytes": raw.hex(),
        "entry_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "instructions": [
            {"address": 0x0100, "bytes": "00", "mnemonic": "nop", "size": 1},
            {"address": 0x0101, "bytes": raw[1:].hex(), "mnemonic": "jp", "operand": target, "size": 3},
        ],
        "target_address": target,
    }


def analyze(data: bytes, expected_sha256: str | None = None) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    if len(data) < ENTRY_OFFSET + ENTRY_SIZE:
        raise ValueError("ROM is too short for the cartridge entry sequence")
    result = decode(data[ENTRY_OFFSET:ENTRY_OFFSET + ENTRY_SIZE])
    result.update({"source_size": len(data), "source_sha256": digest})
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
