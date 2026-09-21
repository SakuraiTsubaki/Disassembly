#!/usr/bin/env python3
"""Inspect a Game Boy ROM header without retaining or copying ROM bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

NINTENDO_LOGO = bytes.fromhex(
    "ce ed 66 66 cc 0d 00 0b 03 73 00 83 00 0c 00 0d"
    "00 08 11 1f 88 89 00 0e dc cc 6e e6 dd dd d9 99"
    "bb bb 67 63 6e 0e ec cc dd dc 99 9f bb b9 33 3e"
)


def _hashes(data: bytes) -> dict[str, str]:
    return {
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _title(data: bytes) -> str:
    # In CGB-compatible cartridges 0x143 is the CGB flag, reducing the title
    # field from 16 bytes to 15. Do not decode that flag as title text.
    title_end = 0x143 if data[0x143] in (0x80, 0xC0) else 0x144
    raw = data[0x134:title_end].split(b"\0", 1)[0]
    return raw.decode("ascii", errors="replace").rstrip()


def inspect_bytes(data: bytes, *, filename: str | None = None) -> dict[str, Any]:
    """Return reproducible identity and header validation for one ROM image."""
    if len(data) < 0x150:
        raise ValueError("file is too small to contain a Game Boy cartridge header")

    calculated_header_checksum = 0
    for value in data[0x134:0x14D]:
        calculated_header_checksum = (calculated_header_checksum - value - 1) & 0xFF

    stored_global_checksum = int.from_bytes(data[0x14E:0x150], "big")
    calculated_global_checksum = (
        sum(data[:0x14E]) + sum(data[0x150:])
    ) & 0xFFFF

    result: dict[str, Any] = {
        "size": len(data),
        **_hashes(data),
        "header": {
            "title": _title(data),
            "cgb_flag": data[0x143],
            "new_licensee_code": data[0x144:0x146].decode("ascii", errors="replace"),
            "sgb_flag": data[0x146],
            "cartridge_type": data[0x147],
            "rom_size_code": data[0x148],
            "ram_size_code": data[0x149],
            "destination_code": data[0x14A],
            "old_licensee_code": data[0x14B],
            "revision": data[0x14C],
            "header_checksum": data[0x14D],
            "global_checksum": stored_global_checksum,
        },
        "validation": {
            "nintendo_logo_valid": data[0x104:0x134] == NINTENDO_LOGO,
            "header_checksum_valid": data[0x14D] == calculated_header_checksum,
            "global_checksum_valid": stored_global_checksum == calculated_global_checksum,
            "calculated_header_checksum": calculated_header_checksum,
            "calculated_global_checksum": calculated_global_checksum,
        },
    }
    if filename is not None:
        result["filename"] = filename
    return result


def inspect_file(path: Path) -> dict[str, Any]:
    return inspect_bytes(path.read_bytes(), filename=path.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--expect-sha256")
    parser.add_argument("--require-valid", action="store_true")
    args = parser.parse_args()

    if not args.path.is_file():
        parser.error(f"not a file: {args.path}")

    try:
        result = inspect_file(args.path)
    except ValueError as exc:
        parser.error(str(exc))

    checks = result["validation"]
    if args.expect_sha256 is not None:
        expected = args.expect_sha256.lower()
        checks["expected_sha256"] = expected
        checks["sha256_matches"] = result["sha256"] == expected

    # ASCII escaping keeps JSON portable on Windows consoles with legacy code
    # pages while preserving the exact Unicode string after JSON decoding.
    print(json.dumps(result, ensure_ascii=True, indent=None if args.compact else 2))

    required = [
        checks["nintendo_logo_valid"],
        checks["header_checksum_valid"],
        checks["global_checksum_valid"],
    ]
    if "sha256_matches" in checks:
        required.append(checks["sha256_matches"])
    return 0 if not args.require_valid or all(required) else 1


if __name__ == "__main__":
    raise SystemExit(main())

