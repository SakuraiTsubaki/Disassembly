#!/usr/bin/env python3
"""Reconstruct Generation II CountSetBits across a release catalog."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


PREFIX = bytes.fromhex("0e002a5f1608cb3b3e00894f1520f70520f079ea")
SUFFIX = bytes.fromhex("c9")
LENGTH = len(PREFIX) + 2 + len(SUFFIX)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def count_set_bits(data: bytes) -> int:
    if not 1 <= len(data) <= 0xFF:
        raise ValueError("input must contain between 1 and 255 bytes")
    return sum(byte.bit_count() for byte in data) & 0xFF


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def load_releases(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        releases = list(csv.DictReader(handle))
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("release catalog must begin with Japanese origin")
    languages = [item["language"] for item in releases]
    if "Korean" in languages and languages.index("Korean") > languages.index("English"):
        raise ValueError("Korean release must precede English when available")
    return releases


def rom_index(directory: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in {".gb", ".gbc"}:
            result.setdefault(file_hash(path), path)
    return result


def locate(data: bytes) -> list[dict]:
    result, start, limit = [], 0, min(0x4000, len(data))
    while True:
        offset = data.find(PREFIX, start, limit)
        if offset < 0:
            return result
        end = offset + LENGTH
        if end <= limit and data[end - 1:end] == SUFFIX:
            routine = data[offset:end]
            result.append({
                "rom_offset": offset,
                "bank": 0,
                "address": offset,
                "range_end_exclusive": end,
                "length": LENGTH,
                "work_ram_address": int.from_bytes(routine[-3:-1], "little"),
                "code_sha256": digest(routine),
            })
        start = offset + 1


def source_text() -> str:
    return """SECTION "Pokedex Flag Reconstruction", ROM0

CountSetBits::
    ld c, 0
.next
    ld a, [hli]
    ld e, a
    ld d, 8
.count
    srl e
    ld a, 0
    adc c
    ld c, a
    dec d
    jr nz, .count
    dec b
    jr nz, .next
    ld a, c
    ld [wNumSetBits], a
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path = Path("research/releases.csv")
    releases = load_releases(root / catalog_path)
    roms = rom_index(rom_dir)
    source_path = Path("src/count_set_bits.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        matches = locate(data)
        if len(matches) != 1:
            raise ValueError(f"expected one CountSetBits in {release_id}, found {len(matches)}")
        function = {**matches[0], "name": "CountSetBits", "raw_bytes_published": False}
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256, "status": release["status"]},
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": function,
            "semantics": {
                "input": "B bytes beginning at HL; B must be between 1 and 255",
                "operation": "count all set bits while advancing HL by B bytes",
                "result": "A, C and wNumSetBits contain the low eight bits of the count",
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/pokedex_flags.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-count-set-bits.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release["status"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "address": f"0x{function['address']:04X}",
            "work_ram_address": f"0x{function['work_ram_address']:04X}",
            "code_sha256": function["code_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "game": game,
        "function": "CountSetBits",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/count-set-bits-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/count-set-bits-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} CountSetBits\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) contain exactly one "
        "ROM0 implementation of the same bit-count loop. The release-specific "
        "wNumSetBits address and complete routine hash are recorded without ROM "
        "bytes. Korean precedes English where available; release status is unchanged.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_count_set_bits_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/count-set-bits-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "CountSetBits",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen2_count_set_bits.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.game, args.reference_repository,
              args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
