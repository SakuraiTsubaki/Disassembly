#!/usr/bin/env python3
"""Extract an uncompressed Game Box 1bpp tile range as a deterministic PNG."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path


TILE_BYTES = 8
TILE_SIZE = 8


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def render(raw: bytes, tiles_per_row: int, scale: int = 4) -> bytes:
    if not raw or len(raw) % TILE_BYTES:
        raise ValueError("1bpp input length must be a non-zero multiple of 8 bytes")
    tile_count = len(raw) // TILE_BYTES
    if tiles_per_row <= 0 or tile_count % tiles_per_row:
        raise ValueError("tile count must be divisible by tiles_per_row")
    width = tiles_per_row * TILE_SIZE
    height = (tile_count // tiles_per_row) * TILE_SIZE
    logical = [[255] * width for _ in range(height)]
    for tile in range(tile_count):
        tile_x = tile % tiles_per_row
        tile_y = tile // tiles_per_row
        for y, bits in enumerate(raw[tile * TILE_BYTES:(tile + 1) * TILE_BYTES]):
            for x in range(TILE_SIZE):
                logical[tile_y * TILE_SIZE + y][tile_x * TILE_SIZE + x] = 0 if bits & (0x80 >> x) else 255
    rows = []
    for row in logical:
        expanded = bytes(value for value in row for _ in range(scale))
        scanline = b"\x00" + expanded
        rows.extend([scanline] * scale)
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width * scale, height * scale, 8, 0, 0, 0, 0)
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + _chunk(b"IEND", b"")


def extract(rom: bytes, offset: int, tile_count: int, tiles_per_row: int, expected_sha256: str | None = None):
    digest = hashlib.sha256(rom).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError(f"ROM SHA-256 mismatch: expected {expected_sha256}, got {digest}")
    length = tile_count * TILE_BYTES
    raw = rom[offset:offset + length]
    if len(raw) != length:
        raise ValueError("requested tile range extends past the ROM")
    png = render(raw, tiles_per_row)
    return png, {
        "rom_size": len(rom),
        "rom_sha256": digest,
        "source_offset": offset,
        "source_length": length,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "format": "game-box-1bpp-8x8-tiles",
        "tile_count": tile_count,
        "tiles_per_row": tiles_per_row,
        "logical_width": tiles_per_row * TILE_SIZE,
        "logical_height": (tile_count // tiles_per_row) * TILE_SIZE,
        "png_sha256": hashlib.sha256(png).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--offset", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--tile-count", required=True, type=int)
    parser.add_argument("--tiles-per-row", required=True, type=int)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--png", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    png, report = extract(args.rom.read_bytes(), args.offset, args.tile_count, args.tiles_per_row, args.expected_sha256)
    args.png.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.png.write_bytes(png)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
