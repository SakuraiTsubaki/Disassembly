#!/usr/bin/env python3
"""Locate Gen I-style Game Boy 1bpp asset loaders without publishing ROM bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PREFIX = bytes.fromhex("f040cb7f200e21")


def banked_offset(bank: int, address: int) -> int:
    if bank == 0:
        if not 0 <= address < 0x4000:
            raise ValueError("bank 0 address must be below 0x4000")
        return address
    if not 0x4000 <= address < 0x8000:
        raise ValueError("switchable-bank address must be in 0x4000..0x7fff")
    return bank * 0x4000 + address - 0x4000


def locate(rom: bytes, source_length: int = 0x400) -> list[dict[str, object]]:
    if source_length <= 0 or source_length % 8:
        raise ValueError("source length must be a positive multiple of 8")
    candidates: list[dict[str, object]] = []
    start = 0
    while True:
        loader = rom.find(PREFIX, start)
        if loader < 0:
            break
        start = loader + 1
        if loader + 32 > len(rom):
            continue
        address = int.from_bytes(rom[loader + 7:loader + 9], "little")
        bank = rom[loader + 16]
        expected = (
            b"\x11\x00\x88\x01"
            + source_length.to_bytes(2, "little")
            + b"\x3e"
            + bytes([bank])
        )
        if rom[loader + 9:loader + 17] != expected:
            continue
        if rom[loader + 20] != 0x11:
            continue
        if int.from_bytes(rom[loader + 21:loader + 23], "little") != address:
            continue
        if rom[loader + 23:loader + 29] != b"\x21\x00\x88\x01" + bytes([source_length // 8, bank]):
            continue
        try:
            offset = banked_offset(bank, address)
        except ValueError:
            continue
        raw = rom[offset:offset + source_length]
        if len(raw) != source_length:
            continue
        candidates.append({
            "loader_offset": loader,
            "bank": bank,
            "cpu_address": address,
            "source_offset": offset,
            "source_length": source_length,
            "tile_count": source_length // 8,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_bytes_omitted": True,
        })
    return candidates


def report(rom: bytes, source_length: int = 0x400, expected_sha256: str | None = None) -> dict[str, object]:
    digest = hashlib.sha256(rom).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError(f"ROM SHA-256 mismatch: expected {expected_sha256}, got {digest}")
    return {
        "schema_version": 1,
        "rom_size": len(rom),
        "rom_sha256": digest,
        "format": "game-boy-1bpp-8x8-tiles",
        "requested_source_length": source_length,
        "candidates": locate(rom, source_length),
        "raw_rom_bytes_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--source-length", type=lambda value: int(value, 0), default=0x400)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = report(args.rom.read_bytes(), args.source_length, args.expected_sha256)
    if not result["candidates"]:
        raise ValueError("no matching 1bpp loader found")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
