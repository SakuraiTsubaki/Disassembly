#!/usr/bin/env python3
"""Reconstruct Generation II ClearJoypad across a release catalog."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ANCHOR_LENGTH = 7
FUNCTION_OFFSET = 1
FUNCTION_LENGTH = 6


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


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


def decode(data: bytes, offset: int) -> dict[str, int | str] | None:
    code = data[offset:offset + ANCHOR_LENGTH]
    if len(code) != ANCHOR_LENGTH:
        return None
    if code[0:3] != bytes.fromhex("d9afe0") or code[4] != 0xE0 or code[6] != 0xC9:
        return None
    if code[5] != (code[3] + 1) & 0xFF:
        return None
    bank = offset // 0x4000
    if bank != 0:
        return None
    address = offset + FUNCTION_OFFSET
    function = code[FUNCTION_OFFSET:]
    return {
        "rom_offset": address,
        "bank": bank,
        "address": address,
        "range_end_exclusive": address + FUNCTION_LENGTH,
        "length": FUNCTION_LENGTH,
        "joypad_interrupt_placeholder_address": offset,
        "h_joy_pressed_address": 0xFF00 | code[3],
        "h_joy_down_address": 0xFF00 | code[5],
        "code_sha256": digest(function),
    }


def locate(data: bytes) -> list[dict[str, int | str]]:
    return [
        match
        for offset in range(min(0x4000, len(data)) - ANCHOR_LENGTH + 1)
        if (match := decode(data, offset)) is not None
    ]


def source_text() -> str:
    return """SECTION "Clear Joypad Reconstruction", ROM0

ClearJoypad::
    xor a
    ldh [hJoyPressed], a
    ldh [hJoyDown], a
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path = Path("research/releases.csv")
    releases = load_releases(root / catalog_path)
    roms = rom_index(rom_dir)
    source_path = Path("src/clear_joypad.asm")
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
            raise ValueError(f"expected one ClearJoypad in {release_id}, found {len(matches)}")
        found = matches[0]
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256, "status": release["status"]},
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": {
                "name": "ClearJoypad",
                **found,
                "raw_bytes_published": False,
            },
            "semantics": {
                "operation": "clear the pressed-this-frame and currently-held joypad mirrors",
                "zero_source": "XOR A",
                "writes": ["hJoyPressed", "hJoyDown"],
                "return_value": "A is zero",
                "anchor": "immediately follows the ROM0 joypad interrupt RETI placeholder",
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/joypad.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-clear-joypad.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release["status"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "address": f"0x{found['address']:04X}",
            "h_joy_pressed_address": f"0x{found['h_joy_pressed_address']:04X}",
            "h_joy_down_address": f"0x{found['h_joy_down_address']:04X}",
            "code_sha256": found["code_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "game": game,
        "function": "ClearJoypad",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/clear-joypad-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/clear-joypad-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} ClearJoypad\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) contain exactly one "
        "structurally verified ROM0 `ClearJoypad` immediately after the joypad "
        "interrupt `RETI` placeholder. Per-release evidence records the routine "
        "address, both HRAM destinations and code hash without publishing ROM bytes. "
        "Korean precedes English where available, and candidate status is preserved.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_clear_joypad_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/clear-joypad-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "function": "ClearJoypad",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen2_clear_joypad.py",
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
