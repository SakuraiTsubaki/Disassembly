#!/usr/bin/env python3
"""Inspect a Game Boy Advance ROM header without retaining ROM bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

NINTENDO_LOGO = bytes.fromhex(
    "24 ff ae 51 69 9a a2 21 3d 84 82 0a 84 e4 09 ad"
    "11 24 8b 98 c0 81 7f 21 a3 52 be 19 93 09 ce 20"
    "10 46 4a 4a f8 27 31 ec 58 c7 e8 33 82 e3 ce bf"
    "85 f4 df 94 ce 4b 09 c1 94 56 8a c0 13 72 a7 fc"
    "9f 84 4d 73 a3 ca 9a 61 58 97 a3 27 fc 03 98 76"
    "23 1d c7 61 03 04 ae 56 bf 38 84 00 40 a7 0e fd"
    "ff 52 fe 03 6f 95 30 f1 97 fb c0 85 60 d6 80 25"
    "a9 63 be 03 01 4e 38 e2 f9 a2 34 ff bb 3e 03 44"
    "78 00 90 cb 88 11 3a 94 65 c0 7c 63 87 f0 3c af"
    "d6 25 e4 8b 38 0a ac 72 21 d4 f8 07"
)


def _decode_ascii(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("ascii", errors="replace").rstrip()


def inspect_bytes(data: bytes, *, filename: str | None = None) -> dict[str, Any]:
    """Return reproducible identity and GBA header validation for one ROM."""
    if len(data) < 0xC0:
        raise ValueError("file is too small to contain a Game Boy Advance cartridge header")

    calculated_header_checksum = (-sum(data[0xA0:0xBD]) - 0x19) & 0xFF
    result: dict[str, Any] = {
        "size": len(data),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "header": {
            "entry_point": data[0:4].hex(),
            "title": _decode_ascii(data[0xA0:0xAC]),
            "game_code": _decode_ascii(data[0xAC:0xB0]),
            "maker_code": _decode_ascii(data[0xB0:0xB2]),
            "fixed_value": data[0xB2],
            "main_unit_code": data[0xB3],
            "device_type": data[0xB4],
            "software_version": data[0xBC],
            "header_checksum": data[0xBD],
        },
        "validation": {
            "nintendo_logo_valid": data[0x04:0xA0] == NINTENDO_LOGO,
            "fixed_value_valid": data[0xB2] == 0x96,
            "reserved_area_valid": data[0xB5:0xBC] == bytes(7)
            and data[0xBE:0xC0] == bytes(2),
            "header_checksum_valid": data[0xBD] == calculated_header_checksum,
            "calculated_header_checksum": calculated_header_checksum,
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

    print(json.dumps(result, ensure_ascii=True, indent=None if args.compact else 2))
    required = [
        checks["nintendo_logo_valid"],
        checks["fixed_value_valid"],
        checks["reserved_area_valid"],
        checks["header_checksum_valid"],
    ]
    if "sha256_matches" in checks:
        required.append(checks["sha256_matches"])
    return 0 if not args.require_valid or all(required) else 1


if __name__ == "__main__":
    raise SystemExit(main())

