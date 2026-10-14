#!/usr/bin/env python3
"""Locate Generation II standard-font loaders without publishing ROM bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROM_BASE = 0
FONT_DESTINATION = 0x8800
FONT_TILES = 128


def banked_offset(bank: int, address: int) -> int:
    if bank == 0:
        if not 0 <= address < 0x4000:
            raise ValueError("bank 0 address is outside the fixed window")
        return address
    if not 0x4000 <= address < 0x8000:
        raise ValueError("banked address is outside the switchable window")
    return bank * 0x4000 + address - 0x4000


def _word(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def locate_gold_silver(data: bytes) -> list[dict]:
    results = []
    for offset in range(0, len(data) - 12):
        if data[offset] != 0x11 or data[offset + 3 : offset + 7] != b"\x21\x00\x88\x01":
            continue
        if data[offset + 7] != FONT_TILES or data[offset + 9] != 0xC3:
            continue
        source_address = _word(data, offset + 1)
        source_bank = data[offset + 8]
        try:
            source_offset = banked_offset(source_bank, source_address)
        except ValueError:
            continue
        start = offset
        initializer = None
        if offset >= 3 and data[offset - 3] == 0xCD:
            start = offset - 3
            initializer = {"address": start, "target": _word(data, start + 1)}
        end = offset + 13
        record = {
            "family": "gold-silver",
            "loader_offset": start,
            "range_end_exclusive": end,
            "code_length": end - start,
            "code_sha256": hashlib.sha256(data[start:end]).hexdigest(),
            "font": {
                "bank": source_bank,
                "address": source_address,
                "source_offset": source_offset,
                "destination": FONT_DESTINATION,
                "tile_count": FONT_TILES,
                "format": "game-boy-1bpp-8x8-tiles",
            },
            "transfer": {"kind": "tail-jump", "target": _word(data, offset + 10)},
            "initializer_call": initializer,
            "raw_bytes_published": False,
        }
        results.append(record)
    return results


def locate_crystal(data: bytes) -> list[dict]:
    results = []
    for offset in range(0, len(data) - 64):
        if data[offset] != 0x11 or data[offset + 3 : offset + 7] != b"\x21\x00\x88\x01":
            continue
        if data[offset + 7 : offset + 14] != b"\x80\x3e\xf0\x40\xcb\x7f\xca":
            continue
        source_address = _word(data, offset + 1)
        source_bank = data[offset + 8]
        expected_sources = [source_address + index * 0x100 for index in range(4)]
        expected_destinations = [FONT_DESTINATION + index * 0x200 for index in range(4)]
        calls = []
        valid = True
        for index in range(4):
            chunk = offset + 16 + index * 12
            if (
                data[chunk] != 0x11
                or _word(data, chunk + 1) != expected_sources[index]
                or data[chunk + 3] != 0x21
                or _word(data, chunk + 4) != expected_destinations[index]
                or data[chunk + 6 : chunk + 9] != bytes((0x01, 32, source_bank))
                or data[chunk + 9] != 0xCD
            ):
                valid = False
                break
            calls.append({"address": chunk + 9, "target": _word(data, chunk + 10)})
        if not valid or data[offset + 64] != 0xC9:
            continue
        source_offset = banked_offset(source_bank, source_address)
        end = offset + 65
        results.append(
            {
                "family": "crystal",
                "loader_offset": offset,
                "range_end_exclusive": end,
                "code_length": 65,
                "code_sha256": hashlib.sha256(data[offset:end]).hexdigest(),
                "font": {
                    "bank": source_bank,
                    "address": source_address,
                    "source_offset": source_offset,
                    "destination": FONT_DESTINATION,
                    "tile_count": FONT_TILES,
                    "chunk_tile_count": 32,
                    "format": "game-boy-1bpp-8x8-tiles",
                },
                "lcd_enabled_branch": {
                    "address": offset + 13,
                    "disabled_target": _word(data, offset + 14),
                    "enabled_transfer_count": 4,
                },
                "calls": calls,
                "return_offset": offset + 64,
                "raw_bytes_published": False,
            }
        )
    return results


def inspect(path: Path, family: str, expected_sha256: str | None = None) -> dict:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    matches = locate_gold_silver(data) if family == "gold-silver" else locate_crystal(data)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one loader, found {len(matches)}")
    return {
        "schema_version": 1,
        "source_size": len(data),
        "source_sha256": digest,
        **matches[0],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--family", choices=("gold-silver", "crystal"), required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.rom, args.family, args.expected_sha256)
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
