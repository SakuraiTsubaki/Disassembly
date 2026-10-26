#!/usr/bin/env python3
"""Locate and verify the Generation I CopyData byte-copy routine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROUTINE = bytes.fromhex("2a12130b79b020f8c9")
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
    releases_csv = root / "research/releases.csv"
    if releases_csv.is_file():
        with releases_csv.open(encoding="utf-8", newline="") as handle:
            return [row["id"] for row in csv.DictReader(handle)]
    reports = sorted((root / "analysis").glob("*-release-header-report.json"))
    if len(reports) != 1:
        raise ValueError(f"expected one release header report, found {len(reports)}")
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    return [release["id"] for release in report["releases"]]


def build_manifest(root: Path) -> None:
    releases = release_ids(root)
    relative_outputs = [
        Path("src/copy_data.asm"),
        *(Path(f"analysis/{release}-copy-data.json") for release in releases),
        Path("research/copy-data-reconstruction.md"),
        Path("tests/test_copy_data_reconstruction.py"),
    ]
    missing = [path.as_posix() for path in relative_outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing manifest output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "function": "CopyData",
        "releases": releases,
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/locate_gen1_copy_data.py",
            "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "outputs": [
            {"path": path.as_posix(), "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest()}
            for path in relative_outputs
        ],
        "raw_rom_bytes_included": False,
    }
    output = root / "manifests/copy-data-reconstruction.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--reference-repository", default="pret/pokered")
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
        parser.error(f"expected exactly one CopyData routine, found {len(matches)}")
    report = {
        "schema_version": 1,
        "target": {"release": args.release, "sha256": digest},
        "function": {"name": "CopyData", **matches[0]},
        "semantics": {
            "source": "HL",
            "destination": "DE",
            "length": "BC",
            "operation": "copy one byte, increment HL and DE, decrement BC, repeat until BC is zero",
            "zero_length_precondition": "BC must be nonzero; zero would wrap and copy 65536 bytes",
            "return_registers": "HL and DE point one byte past their ranges; BC is zero",
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
