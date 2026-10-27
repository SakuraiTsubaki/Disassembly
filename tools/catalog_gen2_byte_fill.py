#!/usr/bin/env python3
"""Locate and verify the Generation II ByteFill routine across a release catalog."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROUTINE = bytes.fromhex("040c1801220d20fc0520f9c9")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def rom_index(directory: Path) -> dict[str, Path]:
    result = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in {".gb", ".gbc"}:
            result.setdefault(file_hash(path), path)
    return result


def locate(data: bytes) -> list[int]:
    result, start = [], 0
    while True:
        offset = data.find(ROUTINE, start)
        if offset < 0:
            return result
        result.append(offset)
        start = offset + 1


def source_text() -> str:
    return """SECTION \"ByteFill Reconstruction\", ROM0

ByteFill::
    inc b
    inc c
    jr .handle_loop
.put_byte
    ld [hli], a
.handle_loop
    dec c
    jr nz, .put_byte
    dec b
    jr nz, .put_byte
    ret
"""


def load_releases(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        releases = list(csv.DictReader(handle))
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("release catalog must begin with Japanese origin")
    languages = [item["language"] for item in releases]
    if "Korean" in languages and languages.index("Korean") > languages.index("English"):
        raise ValueError("Korean release must precede English when available")
    return releases


def build(root: Path, rom_dir: Path, game: str, reference_commit: str) -> dict:
    catalog_path = Path("research/releases.csv")
    releases = load_releases(root / catalog_path)
    roms = rom_index(rom_dir)
    source_path = Path("src/byte_fill.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        matches = locate(data)
        if len(matches) != 1:
            raise ValueError(f"expected one ByteFill routine in {release_id}, found {len(matches)}")
        offset = matches[0]
        bank = offset // 0x4000
        address = offset if bank == 0 else 0x4000 + offset % 0x4000
        if bank != 0:
            raise ValueError(f"ByteFill unexpectedly leaves ROM0: {release_id}")
        evidence = {
            "schema_version": 1,
            "target": {
                "release": release_id,
                "sha256": sha256,
                "status": release["status"],
            },
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": {
                "name": "ByteFill",
                "rom_offset": offset,
                "bank": bank,
                "address": address,
                "range_end_exclusive": offset + len(ROUTINE),
                "length": len(ROUTINE),
                "code_sha256": digest(data[offset:offset + len(ROUTINE)]),
                "raw_bytes_published": False,
            },
            "semantics": {
                "destination": "HL",
                "length": "BC",
                "fill_value": "A",
                "operation": "write A while incrementing HL until BC bytes are filled",
                "zero_length_supported": True,
                "return_registers": "HL points one byte past the range; BC is zero",
                "loop_strategy": "increment B and C before split 8-bit countdowns",
            },
            "naming_basis": {
                "repository": "pret/pokegold",
                "commit": reference_commit,
                "path": "home/copy.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-byte-fill.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release["status"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "address": f"0x{address:04X}",
            "code_sha256": evidence["function"]["code_sha256"],
            "evidence": map_path.as_posix(),
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "function": "ByteFill",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/byte-fill-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/byte-fill-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} `ByteFill` disassembly\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) contain exactly one "
        "ROM0 implementation of the same 12-byte routine. The committed RGBDS "
        "source reconstructs its split 8-bit countdown, including the zero-length "
        "no-op case. Per-release reports "
        "retain ROM identity, address and code hash without publishing ROM bytes. "
        "Candidate/verified release status is preserved from `research/releases.csv` "
        "and is not promoted by this function match.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_byte_fill_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/byte-fill-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "ByteFill",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen2_byte_fill.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [
            {"path": path.as_posix(), "sha256": file_hash(root / path)}
            for path in outputs
        ],
        "raw_rom_bytes_included": False,
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.game, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
