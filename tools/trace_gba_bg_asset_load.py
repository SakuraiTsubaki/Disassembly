#!/usr/bin/env python3
"""Trace a GBA compressed BG asset passed to DecompressAndCopyTileDataToVram."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "trace_gba_lz77_load", Path(__file__).with_name("trace_gba_lz77_load.py")
)
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)


def trace_background_load(data: bytes, source_offset: int) -> dict:
    result = _BASE.trace(data, source_offset)
    loads = []
    for reference in result["thumb_references"]:
        if reference["destination_register"] != 1:
            continue
        start = reference["instruction_offset"]
        call_offset = None
        call_target = None
        immediates = {}
        for offset in range(start + 2, min(start + 0x22, len(data) - 3), 2):
            instruction = int.from_bytes(data[offset : offset + 2], "little")
            if instruction & 0xF800 == 0x2000:
                immediates[f"r{(instruction >> 8) & 7}"] = instruction & 0xFF
            target = _BASE.decode_thumb_bl(data, offset)
            if target is not None:
                call_offset = offset
                call_target = target
                break
        if call_offset is None:
            continue
        end = call_offset + 4
        loads.append(
            {
                "instruction_offset": start,
                "literal_offset": reference["literal_offset"],
                "asset_argument_register": 1,
                "register_immediates": immediates,
                "call_offset": call_offset,
                "call_target": call_target,
                "loader_sequence_length": end - start,
                "loader_sequence_sha256": hashlib.sha256(data[start:end]).hexdigest(),
            }
        )
    result["background_loads"] = loads
    return result


def inspect(path: Path, source_offset: int, expected_sha256: str | None = None) -> dict:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    result = trace_background_load(data, source_offset)
    if len(result["background_loads"]) != 1:
        raise ValueError(f"expected exactly one background load, found {len(result['background_loads'])}")
    result.update({"schema_version": 1, "source_size": len(data), "source_sha256": digest})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--source-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.rom, args.source_offset, args.expected_sha256)
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
