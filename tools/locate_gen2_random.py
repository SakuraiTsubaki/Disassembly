#!/usr/bin/env python3
"""Locate and verify the Generation II hardware-divider Random routine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


LENGTH = 19


def candidate_at(data: bytes, offset: int) -> dict[str, int] | None:
    if offset + LENGTH > len(data):
        return None
    chunk = data[offset:offset + LENGTH]
    add = chunk[5]
    sub = chunk[13]
    expected = bytes((
        0xC5, 0xF0, 0x04, 0x47, 0xF0, add, 0x88, 0xE0, add,
        0xF0, 0x04, 0x47, 0xF0, sub, 0x98, 0xE0, sub, 0xC1, 0xC9,
    ))
    if chunk != expected or sub != ((add + 1) & 0xFF):
        return None
    return {"hRandomAdd": 0xFF00 + add, "hRandomSub": 0xFF00 + sub}


def locate(data: bytes) -> list[dict[str, object]]:
    prefix = bytes((0xC5, 0xF0, 0x04, 0x47, 0xF0))
    results = []
    start = 0
    while True:
        offset = data.find(prefix, start)
        if offset < 0:
            break
        globals_record = candidate_at(data, offset)
        if globals_record is not None:
            bank = offset // 0x4000
            address = offset if bank == 0 else 0x4000 + (offset % 0x4000)
            results.append({
                "rom_offset": offset,
                "bank": bank,
                "address": address,
                "range_end_exclusive": offset + LENGTH,
                "length": LENGTH,
                "code_sha256": hashlib.sha256(data[offset:offset + LENGTH]).hexdigest(),
                "globals": globals_record,
            })
        start = offset + 1
    return results


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
        parser.error(f"expected exactly one Random routine, found {len(matches)}")
    report = {
        "schema_version": 1,
        "target": {"release": args.release, "sha256": digest},
        "function": {"name": "Random", **matches[0]},
        "semantics": {
            "entropy_source": "DIV register (0xFF04)",
            "add_state": "hRandomAdd = hRandomAdd + DIV + carry",
            "subtract_state": "hRandomSub = DIV - hRandomSub - carry",
            "return_register": "A (updated hRandomSub)",
        },
        "naming_basis": {
            "repository": args.reference_repository,
            "commit": args.reference_commit,
            "path": "home/random.asm",
            "raw_rom_bytes_published": False,
        },
        "raw_rom_bytes_included": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.root is not None:
        releases_path = args.root / "research/releases.csv"
        with releases_path.open(encoding="utf-8", newline="") as handle:
            release_ids = [row["id"] for row in csv.DictReader(handle)]
        relative_outputs = [
            Path("src/random.asm"),
            *(Path(f"analysis/{release_id}-random.json") for release_id in release_ids),
            Path("research/random-reconstruction.md"),
            Path("tests/test_random_reconstruction.py"),
        ]
        missing = [path.as_posix() for path in relative_outputs if not (args.root / path).is_file()]
        if missing:
            parser.error("missing manifest output(s): " + ", ".join(missing))
        manifest = {
            "schema_version": 1,
            "function": "Random",
            "releases": release_ids,
            "generator": {
                "repository": "SakuraiTsubaki/Disassembly",
                "tool": "tools/locate_gen2_random.py",
                "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            "outputs": [
                {"path": path.as_posix(), "sha256": hashlib.sha256((args.root / path).read_bytes()).hexdigest()}
                for path in relative_outputs
            ],
            "raw_rom_bytes_included": False,
        }
        manifest_path = args.root / "manifests/random-reconstruction.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
