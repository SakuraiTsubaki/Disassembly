#!/usr/bin/env python3
"""Validate publication-safe disassembly evidence manifests.

The validator checks repository outputs without requiring a ROM.  When a local
ROM is supplied it additionally verifies the target and byte-range hashes, but
never emits ROM bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_offset(value: Any, field: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError(f"{field} must be a hexadecimal string")
    try:
        return int(value, 16)
    except ValueError as error:
        raise ValueError(f"{field} is not valid hexadecimal") from error


def require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be a 64-character SHA-256")
    if value != value.lower() or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be lowercase hexadecimal")
    return value


def resolve_output(root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("output path must be a non-empty string")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"output path escapes repository root: {relative}") from error
    return candidate


RAW_ROM_FIELDS = {"block_bytes", "bytes", "raw_bytes", "rom_bytes"}


def find_raw_rom_fields(value: Any, location: str = "$") -> list[str]:
    """Return JSON paths containing fields that publish verbatim ROM bytes."""
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if key in RAW_ROM_FIELDS:
                findings.append(child_location)
            findings.extend(find_raw_rom_fields(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_raw_rom_fields(child, f"{location}[{index}]"))
    return findings


def validate(manifest_path: Path, root: Path, rom_path: Path | None = None) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if manifest.get("raw_rom_bytes_included") is not False:
        errors.append("raw_rom_bytes_included must be false")

    target = manifest.get("target")
    if not isinstance(target, dict) or not isinstance(target.get("release"), str):
        errors.append("target.release must be present")
        expected_rom_hash = None
    else:
        try:
            expected_rom_hash = require_sha256(target.get("sha256"), "target.sha256")
        except ValueError as error:
            errors.append(str(error))
            expected_rom_hash = None

    blocks: list[tuple[int, int, str, str]] = []
    raw_blocks = manifest.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        errors.append("blocks must be a non-empty list")
    else:
        for index, block in enumerate(raw_blocks):
            try:
                if not isinstance(block, dict) or not isinstance(block.get("path"), str):
                    raise ValueError(f"blocks[{index}].path must be present")
                start = parse_offset(block.get("start"), f"blocks[{index}].start")
                end = parse_offset(block.get("end_exclusive"), f"blocks[{index}].end_exclusive")
                if start >= end:
                    raise ValueError(f"blocks[{index}] has an empty or reversed range")
                block_hash = require_sha256(block.get("bytes_sha256"), f"blocks[{index}].bytes_sha256")
                blocks.append((start, end, block_hash, block["path"]))
            except ValueError as error:
                errors.append(str(error))

    for previous, current in zip(sorted(blocks), sorted(blocks)[1:]):
        if current[0] < previous[1]:
            errors.append(f"block ranges overlap: {previous[3]} and {current[3]}")

    checked_outputs = 0
    raw_outputs = manifest.get("outputs")
    if not isinstance(raw_outputs, list) or not raw_outputs:
        errors.append("outputs must be a non-empty list")
    else:
        seen_paths: set[str] = set()
        for index, output in enumerate(raw_outputs):
            try:
                if not isinstance(output, dict):
                    raise ValueError(f"outputs[{index}] must be an object")
                relative = output.get("path")
                if relative in seen_paths:
                    raise ValueError(f"duplicate output path: {relative}")
                seen_paths.add(relative)
                expected = require_sha256(output.get("sha256"), f"outputs[{index}].sha256")
                output_path = resolve_output(root, relative)
                if not output_path.is_file():
                    raise ValueError(f"output is missing: {relative}")
                if sha256(output_path) != expected:
                    raise ValueError(f"output hash mismatch: {relative}")
                if output_path.suffix.lower() == ".json":
                    report = json.loads(output_path.read_text(encoding="utf-8"))
                    raw_fields = find_raw_rom_fields(report)
                    if raw_fields:
                        raise ValueError(
                            f"publication output contains raw ROM fields: {relative}: "
                            + ", ".join(raw_fields)
                        )
                checked_outputs += 1
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                errors.append(str(error))

    rom_verified = False
    checked_blocks = 0
    if rom_path is not None:
        if not rom_path.is_file():
            errors.append("ROM path is not a file")
        else:
            rom_size = rom_path.stat().st_size
            if expected_rom_hash is not None and sha256(rom_path) != expected_rom_hash:
                errors.append("ROM SHA-256 does not match target.sha256")
            else:
                rom_verified = expected_rom_hash is not None
            with rom_path.open("rb") as rom:
                for start, end, expected, label in blocks:
                    if end > rom_size:
                        errors.append(f"block exceeds ROM size: {label}")
                        continue
                    rom.seek(start)
                    actual = hashlib.sha256(rom.read(end - start)).hexdigest()
                    if actual != expected:
                        errors.append(f"block hash mismatch: {label}")
                    else:
                        checked_blocks += 1

    return {
        "schema_version": 1,
        "valid": not errors,
        "manifest": str(manifest_path),
        "checked_outputs": checked_outputs,
        "checked_blocks": checked_blocks,
        "rom_verified": rom_verified,
        "errors": errors,
        "raw_rom_bytes_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, help="repository root (defaults to manifest parent parent)")
    parser.add_argument("--rom", type=Path, help="optional local ROM for target and range verification")
    parser.add_argument("--report", type=Path, help="optional JSON report path")
    args = parser.parse_args()

    root = (args.root or args.manifest.parent.parent).resolve()
    result = validate(args.manifest.resolve(), root, args.rom.resolve() if args.rom else None)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
