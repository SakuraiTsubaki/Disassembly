#!/usr/bin/env python3
"""Locate and verify Generation I FillMemory variants across release catalogs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


PROFILES = {
    "classic": {
        "routine": bytes.fromhex("d5577a220b78b120f9d1c9"),
        "repository": "pret/pokered",
        "commit": "af519899719f0754965776faac0e836a3b906e6d",
        "path": "home/tilemap.asm",
        "zero_length": "BC must be nonzero; zero wraps and fills 65,536 bytes",
    },
    "yellow": {
        "routine": bytes.fromhex("f578a7280479a7280104f1220d20fc0520f9c9"),
        "repository": "pret/pokeyellow",
        "commit": "31b7c2ea2ba6c8c64ed083723fbaa8cbb74669cb",
        "path": "home/copy2.asm",
        "zero_length": "BC must be nonzero; zero follows the 8-bit path and fills 256 bytes",
    },
}
LANGUAGES = {
    "jp": "Japanese", "en": "English", "de": "German",
    "es": "Spanish", "fr": "French", "it": "Italian",
}


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


def locate(data: bytes, routine: bytes) -> list[int]:
    result, start = [], 0
    while True:
        offset = data.find(routine, start)
        if offset < 0:
            return result
        result.append(offset)
        start = offset + 1


def infer_language(release_id: str) -> str:
    for code, language in LANGUAGES.items():
        if f"-{code}-" in release_id:
            return language
    raise ValueError(f"cannot infer language from release id: {release_id}")


def load_releases(root: Path) -> tuple[Path, list[dict]]:
    csv_path = root / "research/releases.csv"
    if csv_path.is_file():
        with csv_path.open(encoding="utf-8", newline="") as handle:
            releases = list(csv.DictReader(handle))
        return Path("research/releases.csv"), releases
    reports = sorted((root / "analysis").glob("*-release-header-report.json"))
    if len(reports) != 1:
        raise ValueError(f"expected one release header report, found {len(reports)}")
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    releases = []
    for item in report["releases"]:
        releases.append({
            "id": item["id"],
            "language": infer_language(item["id"]),
            "revision": item["header"]["revision"],
            "status": "candidate",
            "sha256": item["sha256"],
        })
    return reports[0].relative_to(root), releases


def source_text(profile: str) -> str:
    if profile == "classic":
        return """SECTION \"FillMemory Reconstruction\", ROM0

FillMemory::
    push de
    ld d, a
.loop
    ld a, d
    ld [hli], a
    dec bc
    ld a, b
    or c
    jr nz, .loop
    pop de
    ret
"""
    return """SECTION \"FillMemory Reconstruction\", ROM0

FillMemory::
    push af
    ld a, b
    and a
    jr z, .eight_bit_amount
    ld a, c
    and a
    jr z, .multiple_of_100
.eight_bit_amount
    inc b
.multiple_of_100
    pop af
.loop
    ld [hli], a
    dec c
    jr nz, .loop
    dec b
    jr nz, .loop
    ret
"""


def build(root: Path, rom_dir: Path, game: str, profile_name: str) -> dict:
    profile = PROFILES[profile_name]
    catalog_path, releases = load_releases(root)
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    roms = rom_index(rom_dir)
    source_path = Path("src/fill_memory.asm")
    (root / source_path).write_text(
        source_text(profile_name), encoding="utf-8", newline="\n"
    )
    routine = profile["routine"]
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        matches = locate(data, routine)
        if len(matches) != 1:
            raise ValueError(f"expected one FillMemory in {release_id}, found {len(matches)}")
        offset = matches[0]
        bank = offset // 0x4000
        address = offset if bank == 0 else 0x4000 + offset % 0x4000
        if bank != 0:
            raise ValueError(f"FillMemory unexpectedly leaves ROM0: {release_id}")
        evidence = {
            "schema_version": 1,
            "target": {
                "release": release_id,
                "sha256": sha256,
                "status": release.get("status", "candidate"),
            },
            "origin_reference": index == 0,
            "profile": profile_name,
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": {
                "name": "FillMemory",
                "rom_offset": offset,
                "bank": bank,
                "address": address,
                "range_end_exclusive": offset + len(routine),
                "length": len(routine),
                "code_sha256": digest(data[offset:offset + len(routine)]),
                "raw_bytes_published": False,
            },
            "semantics": {
                "destination": "HL",
                "length": "BC",
                "fill_value": "A",
                "operation": "fill memory while incrementing HL",
                "zero_length_precondition": profile["zero_length"],
                "return_registers": "HL points one byte past the range; BC is zero",
                "preserves": ["DE"] if profile_name == "classic" else [],
            },
            "naming_basis": {
                "repository": profile["repository"],
                "commit": profile["commit"],
                "path": profile["path"],
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-fill-memory.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release.get("status", "candidate"),
            "sha256": sha256,
            "origin_reference": index == 0,
            "profile": profile_name,
            "address": f"0x{address:04X}",
            "code_sha256": evidence["function"]["code_sha256"],
            "evidence": map_path.as_posix(),
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "function": "FillMemory",
        "profile": profile_name,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/fill-memory-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/fill-memory-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} `FillMemory` disassembly\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) contain exactly one "
        f"ROM0 `{profile_name}` implementation. The RGBDS source preserves the "
        "observed countdown strategy and the release maps retain identity, address, "
        "variant and code hash without publishing ROM bytes. Candidate/verified "
        "status is carried through from the existing release catalog and is not "
        "promoted by this match.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_fill_memory_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/fill-memory-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "FillMemory",
        "profile": profile_name,
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen1_fill_memory.py",
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
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.game, args.profile)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
