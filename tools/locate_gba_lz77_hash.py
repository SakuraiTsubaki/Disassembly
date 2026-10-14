#!/usr/bin/env python3
"""Locate BIOS-LZ77 streams by decoded size and SHA-256 without publishing bytes."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "extract_gba_lz77_4bpp", Path(__file__).with_name("extract_gba_lz77_4bpp.py")
)
_LZ = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LZ)


def locate(rom: bytes, decoded_length: int, decoded_sha256: str) -> list[dict]:
    header = b"\x10" + decoded_length.to_bytes(3, "little")
    wanted = decoded_sha256.lower()
    matches = []
    cursor = 0
    while True:
        cursor = rom.find(header, cursor)
        if cursor < 0:
            return matches
        try:
            decoded, used = _LZ.decompress(rom, cursor)
        except ValueError:
            cursor += 1
            continue
        digest = hashlib.sha256(decoded).hexdigest()
        if digest == wanted:
            matches.append(
                {
                    "source_offset": cursor,
                    "compressed_length": used,
                    "compressed_sha256": hashlib.sha256(rom[cursor : cursor + used]).hexdigest(),
                    "decompressed_length": len(decoded),
                    "decompressed_sha256": digest,
                }
            )
        cursor += 1


def inspect(path: Path, decoded_length: int, decoded_sha256: str, expected_sha256: str | None = None) -> dict:
    rom = path.read_bytes()
    digest = hashlib.sha256(rom).hexdigest()
    if expected_sha256 and digest != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    matches = locate(rom, decoded_length, decoded_sha256)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one decoded-hash match, found {len(matches)}")
    return {
        "schema_version": 1,
        "rom_size": len(rom),
        "rom_sha256": digest,
        "match": matches[0],
        "raw_rom_bytes_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--decoded-length", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--decoded-sha256", required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.rom, args.decoded_length, args.decoded_sha256, args.expected_sha256)
    except (OSError, OverflowError, ValueError) as error:
        parser.error(str(error))
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
