#!/usr/bin/env python3
"""Extract a BIOS-LZ77-compressed GBA BGR555 palette as JASC-PAL."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LZ = _load("extract_gba_lz77_4bpp")
_PAL = _load("extract_gba_palette")


def extract(rom: bytes, offset: int, expected_sha256: str | None = None) -> tuple[bytes, dict]:
    digest = hashlib.sha256(rom).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    decoded, used = _LZ.decompress(rom, offset)
    if len(decoded) != 32:
        raise ValueError(f"expected a 16-color palette, decoded {len(decoded)} bytes")
    output = _PAL.jasc(_PAL.decode(decoded, 0, 16))
    return output, {
        "schema_version": 1,
        "rom_size": len(rom),
        "rom_sha256": digest,
        "source_offset": offset,
        "compressed_length": used,
        "compressed_sha256": hashlib.sha256(rom[offset : offset + used]).hexdigest(),
        "decompressed_length": len(decoded),
        "decompressed_sha256": hashlib.sha256(decoded).hexdigest(),
        "color_count": 16,
        "source_format": "gba-bios-lz77-to-bgr555",
        "output_format": "JASC-PAL",
        "palette_sha256": hashlib.sha256(output).hexdigest(),
        "raw_rom_bytes_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--offset", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--expected-sha256")
    parser.add_argument("--palette", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        palette, report = extract(args.rom.read_bytes(), args.offset, args.expected_sha256)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    args.palette.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.palette.write_bytes(palette)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
