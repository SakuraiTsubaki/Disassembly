#!/usr/bin/env python3
"""Verify the Generation II BattleRandom bank-switch wrapper."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


LENGTH = 18


def inspect(data: bytes, offset: int) -> dict[str, object] | None:
    if offset < 0 or offset + LENGTH > len(data):
        return None
    chunk = data[offset:offset + LENGTH]
    if not (
        chunk[0] == 0xF0
        and chunk[2:5] == bytes((0xF5, 0x3E, chunk[4]))
        and chunk[5:7] == bytes((0xD7, 0xCD))
        and chunk[9] == 0xEA
        and chunk[12:15] == bytes((0xF1, 0xD7, 0xFA))
        and chunk[15:17] == chunk[10:12]
        and chunk[17] == 0xC9
    ):
        return None
    target_bank = chunk[4]
    target_address = int.from_bytes(chunk[7:9], "little")
    if target_bank == 0 or not 0x4000 <= target_address < 0x8000:
        return None
    target_offset = target_bank * 0x4000 + target_address - 0x4000
    if target_offset >= len(data):
        return None
    bank = offset // 0x4000
    address = offset if bank == 0 else 0x4000 + offset % 0x4000
    return {
        "rom_offset": offset,
        "bank": bank,
        "address": address,
        "range_end_exclusive": offset + LENGTH,
        "length": LENGTH,
        "code_sha256": hashlib.sha256(chunk).hexdigest(),
        "hROMBank": 0xFF00 + chunk[1],
        "bank_switch": {"opcode": "RST $10", "vector": 0x10},
        "target": {
            "bank": target_bank,
            "address": target_address,
            "rom_offset": target_offset,
        },
        "temporary_wram": int.from_bytes(chunk[10:12], "little"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--random-report", type=Path, required=True)
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
    random_report = json.loads(args.random_report.read_text(encoding="utf-8"))
    if random_report["target"] != {"release": args.release, "sha256": digest}:
        parser.error("Random report identity mismatch")
    offset = random_report["function"]["range_end_exclusive"]
    function = inspect(data, offset)
    if function is None:
        parser.error("BattleRandom does not follow the verified Random routine")
    report = {
        "schema_version": 1,
        "target": {"release": args.release, "sha256": digest},
        "function": {"name": "BattleRandom", **function},
        "semantics": {
            "operation": "bank-switch call to _BattleRandom with A preserved through WRAM",
            "return_register": "A",
            "placement": "immediately follows the verified Random routine",
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
        with (args.root / "research/releases.csv").open(encoding="utf-8", newline="") as handle:
            releases = [row["id"] for row in csv.DictReader(handle)]
        outputs = [
            Path("src/battle_random.asm"),
            *(Path(f"analysis/{release}-battle-random.json") for release in releases),
            Path("research/battle-random-reconstruction.md"),
            Path("tests/test_battle_random_reconstruction.py"),
        ]
        missing = [path.as_posix() for path in outputs if not (args.root / path).is_file()]
        if missing:
            parser.error("missing manifest output(s): " + ", ".join(missing))
        manifest = {
            "schema_version": 1,
            "function": "BattleRandom",
            "releases": releases,
            "generator": {
                "repository": "SakuraiTsubaki/Disassembly",
                "tool": "tools/locate_gen2_battle_random.py",
                "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            "outputs": [
                {"path": path.as_posix(), "sha256": hashlib.sha256((args.root / path).read_bytes()).hexdigest()}
                for path in outputs
            ],
            "raw_rom_bytes_included": False,
        }
        (args.root / "manifests/battle-random-reconstruction.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
