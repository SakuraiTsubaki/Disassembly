#!/usr/bin/env python3
"""Locate and verify the Generation II CopyBytes routine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROUTINE = bytes.fromhex("040c18032a12130d20fa0520f7c9")
LENGTH = len(ROUTINE)


def locate(data: bytes) -> list[dict[str, object]]:
    results = []
    start = 0
    while True:
        offset = data.find(ROUTINE, start)
        if offset < 0:
            break
        bank = offset // 0x4000
        address = offset if bank == 0 else 0x4000 + offset % 0x4000
        results.append(
            {
                "rom_offset": offset,
                "bank": bank,
                "address": address,
                "range_end_exclusive": offset + LENGTH,
                "length": LENGTH,
                "code_sha256": hashlib.sha256(ROUTINE).hexdigest(),
            }
        )
        start = offset + 1
    return results


def release_ids(root: Path) -> list[str]:
    with (root / "research/releases.csv").open(encoding="utf-8", newline="") as handle:
        return [row["id"] for row in csv.DictReader(handle)]


def build_manifest(root: Path) -> None:
    releases = release_ids(root)
    relative_outputs = [
        Path("src/copy_bytes.asm"),
        *(Path(f"analysis/{release}-copy-bytes.json") for release in releases),
        Path("research/copy-bytes-reconstruction.md"),
        Path("tests/test_copy_bytes_reconstruction.py"),
    ]
    missing = [path.as_posix() for path in relative_outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing manifest output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "function": "CopyBytes",
        "releases": releases,
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/locate_gen2_copy_bytes.py",
            "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "outputs": [
            {"path": path.as_posix(), "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest()}
            for path in relative_outputs
        ],
        "raw_rom_bytes_included": False,
    }
    output = root / "manifests/copy-bytes-reconstruction.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    data = args.rom.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != args.expected_sha256.lower():
        parser.error("ROM SHA-256 mismatch")
    matches = locate(data)
    if len(matches) != 1:
        parser.error(f"expected exactly one CopyBytes routine, found {len(matches)}")
    report = {
        "schema_version": 1,
        "target": {"release": args.release, "sha256": digest},
        "function": {"name": "CopyBytes", **matches[0]},
        "semantics": {
            "source": "HL",
            "destination": "DE",
            "length": "BC",
            "operation": "copy BC bytes while incrementing HL and DE",
            "zero_length_supported": True,
            "return_registers": "HL and DE point one byte past their ranges; BC is zero",
            "loop_strategy": "increment B and C before split 8-bit countdowns to include final runs",
        },
        "naming_basis": {
            "repository": args.reference_repository,
            "commit": args.reference_commit,
            "path": "home/copy.asm",
            "raw_rom_bytes_published": False,
        },
        "raw_rom_bytes_included": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.root is not None:
        try:
            build_manifest(args.root)
        except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
            parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
