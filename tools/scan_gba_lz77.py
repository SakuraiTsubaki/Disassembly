#!/usr/bin/env python3
"""Scan a bounded GBA ROM region for valid BIOS-LZ77 streams without publishing bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from extract_gba_lz77_4bpp import decompress


def scan(
    rom: bytes,
    start: int,
    end: int,
    decoded_length: int,
    expected_sha256: str | None = None,
) -> dict:
    digest = hashlib.sha256(rom).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("SHA-256 mismatch")
    if start < 0 or end > len(rom) or start >= end:
        raise ValueError("invalid scan range")
    if decoded_length <= 0:
        raise ValueError("decoded length must be positive")

    expected_header = decoded_length.to_bytes(3, "little")
    candidates = []
    offset = start
    while True:
        offset = rom.find(b"\x10", offset, end)
        if offset < 0:
            break
        if offset + 4 <= end and rom[offset + 1 : offset + 4] == expected_header:
            try:
                raw, used = decompress(rom, offset)
            except ValueError:
                pass
            else:
                if offset + used <= end:
                    candidates.append(
                        {
                            "source_offset": offset,
                            "compressed_length": used,
                            "compressed_sha256": hashlib.sha256(rom[offset : offset + used]).hexdigest(),
                            "decompressed_length": len(raw),
                            "decompressed_sha256": hashlib.sha256(raw).hexdigest(),
                        }
                    )
        offset += 1

    return {
        "schema_version": 1,
        "rom_size": len(rom),
        "rom_sha256": digest,
        "scan_start": start,
        "scan_end_exclusive": end,
        "decoded_length_filter": decoded_length,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "raw_rom_bytes_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--start", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--end", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--decoded-length", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = scan(
            args.rom.read_bytes(), args.start, args.end, args.decoded_length, args.expected_sha256
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
