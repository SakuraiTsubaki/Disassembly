#!/usr/bin/env python3
"""Verify the Generation II link-synchronised _BattleRandom routine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


LENGTH = 55
STREAM_LENGTH = 10


def inspect(data: bytes, offset: int, random_address: int) -> dict[str, object] | None:
    if offset < 0 or offset + LENGTH > len(data):
        return None
    chunk = data[offset:offset + LENGTH]
    fixed = {
        0: 0xFA, 3: 0xA7, 4: 0xCA, 7: 0xE5, 8: 0xC5,
        9: 0xFA, 12: 0x4F, 13: 0x06, 14: 0x00, 15: 0x21,
        18: 0x09, 19: 0x3C, 20: 0xEA, 23: 0xFE, 24: 0x09,
        25: 0x7E, 26: 0xC1, 27: 0xE1, 28: 0xD8,
        29: 0xE5, 30: 0xC5, 31: 0xF5, 32: 0xAF, 33: 0xEA,
        36: 0x21, 39: 0x06, 40: 0x0A,
        41: 0x7E, 42: 0x4F, 43: 0x87, 44: 0x87, 45: 0x81,
        46: 0x3C, 47: 0x22, 48: 0x05, 49: 0x20, 50: 0xF6,
        51: 0xF1, 52: 0xC1, 53: 0xE1, 54: 0xC9,
    }
    if any(chunk[index] != value for index, value in fixed.items()):
        return None
    if int.from_bytes(chunk[5:7], "little") != random_address:
        return None
    count = int.from_bytes(chunk[10:12], "little")
    seeds = int.from_bytes(chunk[16:18], "little")
    if chunk[21:23] != chunk[10:12] or chunk[34:36] != chunk[10:12]:
        return None
    if chunk[37:39] != chunk[16:18]:
        return None
    bank = offset // 0x4000
    address = 0x4000 + offset % 0x4000 if bank else offset
    loop_address = address + 41
    branch_target = address + 51 + int.from_bytes(chunk[50:51], "little", signed=True)
    if branch_target != loop_address:
        return None
    return {
        "rom_offset": offset,
        "bank": bank,
        "address": address,
        "range_end_exclusive": offset + LENGTH,
        "length": LENGTH,
        "code_sha256": hashlib.sha256(chunk).hexdigest(),
        "state": {
            "wLinkMode": int.from_bytes(chunk[1:3], "little"),
            "wLinkBattleRNCount": count,
            "wLinkBattleRNs": seeds,
            "stream_length": STREAM_LENGTH,
        },
        "control_flow": {
            "non_link_jump": {"bank": 0, "address": random_address},
            "early_return_offset": 28,
            "refresh_loop_offset": 41,
            "refresh_loop_back_edge": {"from_offset": 49, "to_offset": 41},
        },
        "prng": {"formula": "seed = (seed * 5 + 1) mod 256", "seed_count": STREAM_LENGTH},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--wrapper-report", type=Path, required=True)
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
    wrapper = json.loads(args.wrapper_report.read_text(encoding="utf-8"))
    random = json.loads(args.random_report.read_text(encoding="utf-8"))
    identity = {"release": args.release, "sha256": digest}
    if wrapper["target"] != identity or random["target"] != identity:
        parser.error("dependency report identity mismatch")
    offset = wrapper["function"]["target"]["rom_offset"]
    function = inspect(data, offset, random["function"]["address"])
    if function is None:
        parser.error("_BattleRandom core does not match the verified structure")
    if (function["bank"], function["address"]) != (
        wrapper["function"]["target"]["bank"], wrapper["function"]["target"]["address"]
    ):
        parser.error("wrapper target mismatch")
    report = {
        "schema_version": 1,
        "target": identity,
        "function": {"name": "_BattleRandom", **function},
        "semantics": {
            "non_link": "tail-jump to Random",
            "link": "consume a shared 10-byte stream and refresh every seed with a 5x+1 LCG",
            "synchronization": "shared link state avoids peer RNG desynchronization",
            "return_register": "A",
        },
        "naming_basis": {
            "repository": args.reference_repository,
            "commit": args.reference_commit,
            "path": "engine/battle/core.asm",
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
            Path("src/battle_random_core.asm"),
            *(Path(f"analysis/{release}-battle-random-core.json") for release in releases),
            Path("research/battle-random-core-reconstruction.md"),
            Path("tests/test_battle_random_core_reconstruction.py"),
        ]
        missing = [path.as_posix() for path in outputs if not (args.root / path).is_file()]
        if missing:
            parser.error("missing manifest output(s): " + ", ".join(missing))
        manifest = {
            "schema_version": 1,
            "function": "_BattleRandom",
            "releases": releases,
            "generator": {
                "repository": "SakuraiTsubaki/Disassembly",
                "tool": "tools/inspect_gen2_battle_random_core.py",
                "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            "outputs": [
                {"path": path.as_posix(), "sha256": hashlib.sha256((args.root / path).read_bytes()).hexdigest()}
                for path in outputs
            ],
            "raw_rom_bytes_included": False,
        }
        (args.root / "manifests/battle-random-core-reconstruction.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
