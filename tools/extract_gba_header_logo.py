#!/usr/bin/env python3
"""Extract the fixed GBA header logo as a deterministic monochrome PNG."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

LOGO_OFFSET = 0x04
LOGO_SIZE = 156
WIDTH = 104
HEIGHT = 16
SCALE = 4

# The GBA BIOS prepends this Huffman header/tree before decoding the 156-byte
# cartridge-header payload. The Huffman result is then decoded as BIOS RL-style
# 16-bit cumulative deltas, producing 208 bytes (104 x 16, 1 bpp).
BIOS_HUFFMAN_HEADER = bytes((
    0x24, 0xD4, 0x00, 0x00, 0x0F, 0x40, 0x00, 0x00, 0x00, 0x01, 0x81, 0x82,
    0x82, 0x83, 0x0F, 0x83, 0x0C, 0xC3, 0x03, 0x83, 0x01, 0x83, 0x04, 0xC3,
    0x08, 0x0E, 0x02, 0xC2, 0x0D, 0xC2, 0x07, 0x0B, 0x06, 0x0A, 0x05, 0x09,
))


def chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def huffman_decode(encoded: bytes) -> bytes:
    header = int.from_bytes(encoded[:4], "little")
    symbol_bits = header & 0x0F
    output_size = header >> 8
    if symbol_bits not in (4, 8):
        raise ValueError("unsupported BIOS Huffman symbol width")
    tree_root = 5
    code_pos = 4 + ((encoded[4] + 1) << 1)
    tree_pos = tree_root
    output = bytearray(output_size)
    output_pos = decoded_bits = code_bits = 0
    code = 0
    while output_pos < output_size:
        if code_bits == 0:
            if code_pos + 4 > len(encoded):
                raise ValueError("truncated GBA logo Huffman stream")
            code = int.from_bytes(encoded[code_pos:code_pos + 4], "little")
            code_pos += 4
            code_bits = 32
        code_bits -= 1
        branch = (code >> code_bits) & 1
        node = encoded[tree_pos]
        increment = ((node & 0x3F) + 1) << 1
        if tree_pos & 1:
            increment -= 1
        tree_pos += increment + branch
        if tree_pos >= len(encoded):
            raise ValueError("invalid GBA logo Huffman tree traversal")
        if (node << branch) & 0x80:
            output[output_pos] |= encoded[tree_pos] << decoded_bits
            decoded_bits += symbol_bits
            if decoded_bits == 8:
                output_pos += 1
                decoded_bits = 0
            tree_pos = tree_root
    return bytes(output)


def cumulative_decode(encrypted: bytes) -> bytes:
    if len(encrypted) < 4:
        raise ValueError("truncated GBA logo cumulative stream")
    output_size = int.from_bytes(encrypted[:4], "little") >> 8
    if output_size != WIDTH * HEIGHT // 8:
        raise ValueError("unexpected decoded GBA logo size")
    output = bytearray(output_size)
    total = 0
    for output_pos, input_pos in zip(range(0, output_size, 2), range(4, len(encrypted), 2)):
        if input_pos + 2 > len(encrypted):
            raise ValueError("truncated GBA logo cumulative stream")
        total = (total + int.from_bytes(encrypted[input_pos:input_pos + 2], "little")) & 0xFFFF
        output[output_pos:output_pos + 2] = total.to_bytes(2, "little")
    return bytes(output)


def decode_logo(logo: bytes) -> bytes:
    if len(logo) != LOGO_SIZE:
        raise ValueError("GBA header logo must be exactly 156 bytes")
    return cumulative_decode(huffman_decode(BIOS_HUFFMAN_HEADER + logo))


def render_logo(logo: bytes) -> bytes:
    decoded = decode_logo(logo)
    rows = []
    for y in range(HEIGHT):
        logical = []
        for x in range(WIDTH):
            tile_x, pixel_x = divmod(x, 8)
            tile_y, pixel_y = divmod(y, 8)
            bit_index = (tile_y * (WIDTH // 8) + tile_x) * 64 + pixel_y * 8 + pixel_x
            bit = (decoded[bit_index // 8] >> (bit_index % 8)) & 1
            logical.append(0 if bit else 255)
        scan = bytes([0]) + b"".join(bytes((value, value, value, 255)) * SCALE for value in logical)
        rows.extend([scan] * SCALE)
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", WIDTH * SCALE, HEIGHT * SCALE, 8, 6, 0, 0, 0)
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")


def extract(data: bytes, expected_sha256: str | None = None) -> tuple[bytes, dict]:
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    if len(data) < LOGO_OFFSET + LOGO_SIZE:
        raise ValueError("ROM is too short for the GBA header logo")
    logo = data[LOGO_OFFSET:LOGO_OFFSET + LOGO_SIZE]
    png = render_logo(logo)
    return png, {
        "schema_version": 1,
        "source_size": len(data),
        "source_sha256": digest,
        "source_offset": LOGO_OFFSET,
        "source_length": LOGO_SIZE,
        "source_bytes_sha256": hashlib.sha256(logo).hexdigest(),
        "format": "gba-bios-huffman-plus-cumulative-104x16-1bpp-tiled",
        "width": WIDTH,
        "height": HEIGHT,
        "png_width": WIDTH * SCALE,
        "png_height": HEIGHT * SCALE,
        "nearest_neighbor_scale": SCALE,
        "png_sha256": hashlib.sha256(png).hexdigest(),
    }


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
