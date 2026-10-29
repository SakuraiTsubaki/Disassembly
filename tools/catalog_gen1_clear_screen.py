#!/usr/bin/env python3
"""Locate and catalog Generation I ClearScreen across release sets."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


PROFILES = {
    "classic": {"repository": "pret/pokered",
                "commit": "af519899719f0754965776faac0e836a3b906e6d",
                "path": "home/copy2.asm"},
    "yellow": {"repository": "pret/pokeyellow",
               "commit": "31b7c2ea2ba6c8c64ed083723fbaa8cbb74669cb",
               "path": "home/copy2.asm"},
}
LANGUAGES = {"jp": "Japanese", "en": "English", "de": "German",
             "es": "Spanish", "fr": "French", "it": "Italian"}
SCREEN_AREA = 20 * 18
ROUTINE_LENGTH = 19


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


def infer_language(release_id: str) -> str:
    for code, language in LANGUAGES.items():
        if f"-{code}-" in release_id:
            return language
    raise ValueError(f"cannot infer language from release id: {release_id}")


def load_releases(root: Path) -> tuple[Path, list[dict]]:
    csv_path = root / "research/releases.csv"
    if csv_path.is_file():
        with csv_path.open(encoding="utf-8", newline="") as handle:
            return Path("research/releases.csv"), list(csv.DictReader(handle))
    reports = sorted((root / "analysis").glob("*-release-header-report.json"))
    if len(reports) != 1:
        raise ValueError(f"expected one release header report, found {len(reports)}")
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    releases = [{"id": item["id"], "language": infer_language(item["id"]),
                 "revision": item["header"]["revision"], "status": "candidate",
                 "sha256": item["sha256"]} for item in report["releases"]]
    return reports[0].relative_to(root), releases


def decode_candidate(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + ROUTINE_LENGTH]
    if len(code) != ROUTINE_LENGTH:
        return None
    if not (code[:5] == bytes.fromhex("0168010421")
            and code[7] == 0x3E
            and code[9:16] == bytes.fromhex("220d20fc0520f9")
            and code[16] == 0xC3):
        return None
    tilemap = code[5] | code[6] << 8
    delay3 = code[17] | code[18] << 8
    if not 0xC000 <= tilemap <= 0xDFFF or not 0x0100 <= delay3 < 0x4000:
        return None
    return {"offset": offset, "tilemap_address": tilemap,
            "blank_tile": code[8], "delay3_address": delay3}


def locate(data: bytes) -> list[dict]:
    return [item for offset in range(0x150, min(0x4000, len(data)) - ROUTINE_LENGTH + 1)
            if (item := decode_candidate(data, offset)) is not None]


def source_text() -> str:
    return """SECTION \"ClearScreen Reconstruction\", ROM0

ClearScreen::
    ld bc, SCREEN_AREA
    inc b
    ld hl, wTileMap
    ld a, \" \"
.loop
    ld [hli], a
    dec c
    jr nz, .loop
    dec b
    jr nz, .loop
    jp Delay3
"""


def build(root: Path, rom_dir: Path, game: str, profile_name: str) -> dict:
    profile = PROFILES[profile_name]
    catalog_path, releases = load_releases(root)
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    source_path = Path("src/clear_screen.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    roms = rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        matches = locate(data)
        if len(matches) != 1:
            raise ValueError(f"expected one ClearScreen in {release_id}, found {len(matches)}")
        match = matches[0]
        offset, end = match["offset"], match["offset"] + ROUTINE_LENGTH
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256,
                       "status": release.get("status", "candidate")},
            "origin_reference": index == 0,
            "axis": "Disassembly",
            "profile": profile_name,
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": {"name": "ClearScreen", "rom_offset": offset, "bank": 0,
                         "address": offset, "range_end_exclusive": end,
                         "length": ROUTINE_LENGTH,
                         "code_sha256": digest(data[offset:end]),
                         "raw_bytes_published": False,
                         "tail_jump": {"name": "Delay3",
                                       "address": match["delay3_address"]}},
            "verified_behavior": {
                "tilemap_address": match["tilemap_address"],
                "blank_tile_value": match["blank_tile"],
                "filled_byte_count": SCREEN_AREA,
                "counter_encoding": "BC=$0168 then INC B; C wraps for the second pass",
                "waits_for_bg_update": "tail-jump to Delay3",
            },
            "naming_basis": {"repository": profile["repository"],
                             "commit": profile["commit"], "path": profile["path"]},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-clear-screen.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": release_id, "language": release["language"],
                        "revision": int(release["revision"]),
                        "status": release.get("status", "candidate"),
                        "sha256": sha256, "origin_reference": index == 0,
                        "address": f"0x{offset:04X}",
                        "tilemap_address": f"0x{match['tilemap_address']:04X}",
                        "blank_tile_value": match["blank_tile"],
                        "delay3_address": f"0x{match['delay3_address']:04X}",
                        "code_sha256": evidence["function"]["code_sha256"],
                        "evidence": map_path.as_posix()})

    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "function": "ClearScreen", "profile": profile_name,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/clear-screen-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/clear-screen-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} ClearScreen disassembly\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) contain exactly one ROM0 routine with the "
        "19-byte ClearScreen control structure. It fills the 20x18 tilemap with the "
        "release's blank tile and tail-jumps to Delay3. Maps preserve RAM addresses, "
        "tile values, targets and hashes without ROM bytes. Existing candidate status "
        "is retained and never promoted by a structural match.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_clear_screen_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/clear-screen-reconstruction.json", {
        "schema_version": 1, "game": game, "axis": "Disassembly",
        "function": "ClearScreen", "profile": profile_name,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gen1_clear_screen.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)}
                    for path in outputs],
        "raw_rom_bytes_included": False})
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
