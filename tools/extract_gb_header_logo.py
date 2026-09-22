#!/usr/bin/env python3
"""Extract the fixed Game Boy header logo bytes as a deterministic 48x8 PNG."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

LOGO_OFFSET = 0x104
LOGO_SIZE = 48
WIDTH = 48
HEIGHT = 8
SCALE = 8


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def render_logo(logo: bytes) -> bytes:
    if len(logo) != LOGO_SIZE:
        raise ValueError("Game Boy header logo must be exactly 48 bytes")
    logical = [[255] * WIDTH for _ in range(HEIGHT)]
    for tile_index in range(24):
        tile_x, tile_y = tile_index % 12, tile_index // 12
        bits = (logo[tile_index * 2] << 8) | logo[tile_index * 2 + 1]
        for y in range(4):
            for x in range(4):
                logical[tile_y * 4 + y][tile_x * 4 + x] = 0 if bits & (1 << (15 - y * 4 - x)) else 255
    rows = []
    for y in range(HEIGHT):
        pixels = []
        for value in logical[y]:
            pixels.extend([(value, value, value, 255)] * SCALE)
        row = bytes([0]) + b"".join(bytes(pixel) for pixel in pixels)
        rows.extend([row] * SCALE)
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", WIDTH * SCALE, HEIGHT * SCALE, 8, 6, 0, 0, 0)
    return signature + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + png_chunk(b"IEND", b"")


def extract(data: bytes, expected_sha256: str | None = None) -> tuple[bytes, dict]:
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    if len(data) < LOGO_OFFSET + LOGO_SIZE:
        raise ValueError("ROM is too short for the Game Boy header logo")
    logo = data[LOGO_OFFSET:LOGO_OFFSET + LOGO_SIZE]
    png = render_logo(logo)
    report = {
        "schema_version": 1,
        "source_size": len(data),
        "source_sha256": digest,
        "source_offset": LOGO_OFFSET,
        "source_length": LOGO_SIZE,
        "source_bytes_sha256": hashlib.sha256(logo).hexdigest(),
        "format": "12x2-tiles-4x4-1bpp-msb-first",
        "width": WIDTH,
        "height": HEIGHT,
        "png_width": WIDTH * SCALE,
        "png_height": HEIGHT * SCALE,
        "nearest_neighbor_scale": SCALE,
        "png_sha256": hashlib.sha256(png).hexdigest(),
    }
    return png, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        png, report = extract(args.rom.read_bytes(), args.expected_sha256)
        args.png.write_bytes(png)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
