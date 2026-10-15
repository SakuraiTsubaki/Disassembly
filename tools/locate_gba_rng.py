#!/usr/bin/env python3
"""Locate Generation III Random/SeedRng Thumb routines and publish safe evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path


ROM_BASE = 0x08000000
MULTIPLIER = 1103515245
INCREMENT = 24691
RANDOM = {
    "standard": (0x4A04,0x6811,0x4804,0x4348,0x4904,0x1840,0x6010,0x0C00,0x4770),
    "emerald": (0x4A06,0x6811,0x4806,0x4348,0x4906,0x1840,0x6010,0x4A06,0x6811,0x3101,0x6011,0x0C00,0x4770),
}
SEED = {
    "standard": (0x0400,0x0C00,0x4901,0x6008,0x4770),
    "emerald": (0x0400,0x0C00,0x4902,0x6008,0x4902,0x2000,0x7008,0x4770),
}
SEED_DELTA = {"standard": 32, "emerald": 44}


def packed(pattern: tuple[int, ...]) -> bytes:
    return struct.pack(f"<{len(pattern)}H", *pattern)


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def code(data: bytes, offset: int, length: int) -> dict[str, object]:
    return {
        "address": f"0x{ROM_BASE + offset:08X}",
        "rom_offset": offset,
        "range_end_exclusive": f"0x{ROM_BASE + offset + length:08X}",
        "length": length,
        "code_sha256": hashlib.sha256(data[offset:offset + length]).hexdigest(),
    }


def candidate(data: bytes, offset: int, variant: str) -> dict[str, object] | None:
    random_bytes = packed(RANDOM[variant])
    seed_offset = offset + SEED_DELTA[variant]
    seed_bytes = packed(SEED[variant])
    if data[offset:offset + len(random_bytes)] != random_bytes:
        return None
    if data[seed_offset:seed_offset + len(seed_bytes)] != seed_bytes:
        return None
    try:
        if variant == "standard":
            state = u32(data, offset + 20)
            constants = (u32(data, offset + 24), u32(data, offset + 28))
            if u32(data, seed_offset + 12) != state:
                return None
            globals_record = {"gRngValue": f"0x{state:08X}"}
        else:
            state = u32(data, offset + 28)
            constants = (u32(data, offset + 32), u32(data, offset + 36))
            if u32(data, seed_offset + 16) != state:
                return None
            globals_record = {
                "gRngValue": f"0x{state:08X}",
                "sRandCount": f"0x{u32(data, offset + 40):08X}",
                "sUnknown": f"0x{u32(data, seed_offset + 20):08X}",
            }
    except struct.error:
        return None
    if constants != (MULTIPLIER, INCREMENT):
        return None
    return {
        "variant": variant,
        "globals": globals_record,
        "functions": {
            "Random": code(data, offset, len(random_bytes)),
            "SeedRng": code(data, seed_offset, len(seed_bytes)),
        },
    }


def locate(data: bytes, variant: str) -> list[dict[str, object]]:
    needle = packed(RANDOM[variant])
    matches = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return matches
        record = candidate(data, offset, variant)
        if record is not None:
            matches.append(record)
        start = offset + 2


def build_manifest(root: Path) -> None:
    with (root / "research/releases.csv").open(encoding="utf-8", newline="") as handle:
        release_ids = [row["id"] for row in csv.DictReader(handle)]
    relative_outputs = [
        Path("src/random.asm"),
        *(Path(f"analysis/{release_id}-rng.json") for release_id in release_ids),
        Path("research/rng-reconstruction.md"),
        Path("tests/test_rng_reconstruction.py"),
    ]
    missing = [path.as_posix() for path in relative_outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing manifest output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "functions": ["Random", "SeedRng"],
        "releases": release_ids,
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/locate_gba_rng.py",
            "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "outputs": [
            {"path": path.as_posix(), "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest()}
            for path in relative_outputs
        ],
        "raw_rom_bytes_included": False,
    }
    (root / "manifests/rng-reconstruction.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--variant", choices=tuple(RANDOM), required=True)
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
    matches = locate(data, args.variant)
    if len(matches) != 1:
        parser.error(f"expected exactly one RNG pair, found {len(matches)}")
    report = {
        "schema_version": 1,
        "target": {"release": args.release, "sha256": digest},
        **matches[0],
        "algorithm": {"state_bits": 32, "multiplier": MULTIPLIER, "increment": INCREMENT, "return_bits": "state[31:16]"},
        "naming_basis": {"repository": args.reference_repository, "commit": args.reference_commit, "path": "src/random.c", "raw_rom_bytes_published": False},
        "raw_rom_bytes_included": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.root is not None:
        try:
            build_manifest(args.root)
        except (OSError, KeyError, ValueError) as error:
            parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
