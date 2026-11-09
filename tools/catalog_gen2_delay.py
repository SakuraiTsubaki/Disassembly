#!/usr/bin/env python3
"""Reconstruct Generation II DelayFrame and DelayFrames across a release catalog."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


LENGTH = 21
DELAY_FRAME_LENGTH = 14


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
    code = data[offset:offset + LENGTH]
    if len(code) != LENGTH:
        return None
    if code[:3] != bytes.fromhex("3e01ea"):
        return None
    if code[5:8] != bytes.fromhex("7600fa") or code[3:5] != code[8:10]:
        return None
    if code[10:15] != bytes.fromhex("a720f8c9cd") or code[17:] != bytes.fromhex("0d20fac9"):
        return None
    bank = offset // 0x4000
    address = offset if bank == 0 else 0x4000 + offset % 0x4000
    if bank != 0 or int.from_bytes(code[15:17], "little") != address:
        return None
    return {
        "rom_offset": offset,
        "bank": bank,
        "delay_frame_address": address,
        "delay_frames_address": address + DELAY_FRAME_LENGTH,
        "w_vblank_occurred_address": int.from_bytes(code[3:5], "little"),
        "range_end_exclusive": offset + LENGTH,
        "length": LENGTH,
        "code_sha256": digest(code),
    }


def locate(data: bytes) -> list[dict[str, int | str]]:
    return [match for offset in range(min(0x4000, len(data)) - LENGTH + 1)
            if (match := decode(data, offset)) is not None]


def source_text() -> str:
    return """SECTION \"Delay Reconstruction\", ROM0

DelayFrame::
    ld a, 1
    ld [wVBlankOccurred], a
.halt
    halt
    nop
    ld a, [wVBlankOccurred]
    and a
    jr nz, .halt
    ret

DelayFrames::
    call DelayFrame
    dec c
    jr nz, DelayFrames
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path = Path("research/releases.csv")
    releases = load_releases(root / catalog_path)
    roms = rom_index(rom_dir)
    source_path = Path("src/delay.asm")
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
            raise ValueError(f"expected one delay pair in {release_id}, found {len(matches)}")
        found = matches[0]
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256, "status": release["status"]},
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "functions": {
                "DelayFrame": {
                    "bank": found["bank"],
                    "address": found["delay_frame_address"],
                    "length": DELAY_FRAME_LENGTH,
                    "wait_flag_address": found["w_vblank_occurred_address"],
                },
                "DelayFrames": {
                    "bank": found["bank"],
                    "address": found["delay_frames_address"],
                    "length": LENGTH - DELAY_FRAME_LENGTH,
                    "frame_count_register": "C",
                },
                "combined": found,
            },
            "semantics": {
                "DelayFrame": "set the VBlank completion flag, halt until the interrupt clears it, then return",
                "DelayFrames": "call DelayFrame and decrement C until C reaches zero",
                "zero_count_precondition": "C must be nonzero; zero wraps and waits 256 frames",
                "halt_loop_target": "HALT instruction",
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/delay.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-delay.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release["status"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "delay_frame_address": f"0x{found['delay_frame_address']:04X}",
            "delay_frames_address": f"0x{found['delay_frames_address']:04X}",
            "wait_flag_address": f"0x{found['w_vblank_occurred_address']:04X}",
            "code_sha256": found["code_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "game": game,
        "functions": ["DelayFrame", "DelayFrames"],
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/delay-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/delay-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} delay routines\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged "
        f"releases ({languages}) contain one structurally verified ROM0 `DelayFrame` / "
        "`DelayFrames` pair. The reconstruction records the release-specific VBlank flag "
        "address and exact routine hash without publishing ROM bytes. Korean builds remain "
        "ahead of English in the release order where an official Korean version exists. "
        "Release candidate/verified status is preserved and is not promoted by this match.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_delay_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/delay-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "functions": ["DelayFrame", "DelayFrames"],
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen2_delay.py",
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
        build(args.root, args.rom_dir, args.game, args.reference_repository, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
