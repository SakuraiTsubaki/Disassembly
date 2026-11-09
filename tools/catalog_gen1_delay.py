#!/usr/bin/env python3
"""Reconstruct Generation I DelayFrame and DelayFrames across release catalogs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen1_clear_screen as common


DELAY_FRAME_LENGTH = 11
DELAY_FRAMES_LENGTH = 7
PROFILES = {
    "classic": {
        "repository": "pret/pokered",
        "commit": "0dbf95cd12f5b1511c62ce69efe283000f780a8f",
    },
    "yellow": {
        "repository": "pret/pokeyellow",
        "commit": "b452f2ab07185075140061c5084ab866d5e4a794",
    },
}


def decode_delay_frame(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + DELAY_FRAME_LENGTH]
    if len(code) != DELAY_FRAME_LENGTH:
        return None
    if code[:3] != bytes.fromhex("3e01e0") or code[4:6] != bytes.fromhex("76f0"):
        return None
    if code[3] != code[6] or code[7:] != bytes.fromhex("a720fac9"):
        return None
    if offset >= 0x4000:
        return None
    return {
        "rom_offset": offset,
        "bank": 0,
        "address": offset,
        "range_end_exclusive": offset + DELAY_FRAME_LENGTH,
        "length": DELAY_FRAME_LENGTH,
        "h_vblank_occurred_offset": code[3],
        "h_vblank_occurred_address": 0xFF00 + code[3],
        "code_sha256": common.digest(code),
    }


def locate_delay_frame(data: bytes) -> list[dict]:
    return [match for offset in range(min(0x4000, len(data)) - DELAY_FRAME_LENGTH + 1)
            if (match := decode_delay_frame(data, offset)) is not None]


def locate_delay_frames(data: bytes, delay_frame_address: int) -> list[dict]:
    code = bytes((0xCD, delay_frame_address & 0xFF, delay_frame_address >> 8,
                  0x0D, 0x20, 0xFA, 0xC9))
    matches = []
    start, limit = 0, min(0x4000, len(data))
    while True:
        offset = data.find(code, start, limit)
        if offset < 0:
            return matches
        matches.append({
            "rom_offset": offset,
            "bank": 0,
            "address": offset,
            "range_end_exclusive": offset + DELAY_FRAMES_LENGTH,
            "length": DELAY_FRAMES_LENGTH,
            "delay_frame_target": delay_frame_address,
            "code_sha256": common.digest(code),
        })
        start = offset + 1


def source_text() -> str:
    return """SECTION \"DelayFrame Reconstruction\", ROM0

DelayFrame::
    ld a, 1
    ldh [hVBlankOccurred], a
.halt
    halt
    ldh a, [hVBlankOccurred]
    and a
    jr nz, .halt
    ret

SECTION \"DelayFrames Reconstruction\", ROM0

DelayFrames::
    call DelayFrame
    dec c
    jr nz, DelayFrames
    ret
"""


def build(root: Path, rom_dir: Path, game: str, profile_name: str) -> dict:
    profile = PROFILES[profile_name]
    catalog_path, releases = common.load_releases(root)
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    roms = common.rom_index(rom_dir)
    source_path = Path("src/delay.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        frame_matches = locate_delay_frame(data)
        if len(frame_matches) != 1:
            raise ValueError(f"expected one DelayFrame in {release_id}, found {len(frame_matches)}")
        frame = frame_matches[0]
        frames_matches = locate_delay_frames(data, frame["address"])
        if len(frames_matches) != 1:
            raise ValueError(f"expected one DelayFrames in {release_id}, found {len(frames_matches)}")
        frames = frames_matches[0]
        evidence = {
            "schema_version": 1,
            "axis": "Disassembly",
            "target": {"release": release_id, "sha256": sha256,
                       "status": release.get("status", "candidate")},
            "origin_reference": index == 0,
            "profile": profile_name,
            "source": source_path.as_posix(),
            "source_sha256": common.file_hash(root / source_path),
            "functions": {"DelayFrame": frame, "DelayFrames": frames},
            "semantics": {
                "DelayFrame": "set the VBlank flag, halt until the interrupt clears it, then return",
                "DelayFrames": "call DelayFrame and decrement C until C reaches zero",
                "zero_count_precondition": "C must be nonzero; zero wraps and waits 256 frames",
                "halt_loop_target": "HALT instruction",
            },
            "naming_basis": {
                "repository": profile["repository"],
                "commit": profile["commit"],
                "paths": ["home/vblank.asm", "home/delay.asm"],
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-delay.json")
        common.write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release.get("status", "candidate"),
            "sha256": sha256,
            "origin_reference": index == 0,
            "delay_frame_address": f"0x{frame['address']:04X}",
            "delay_frames_address": f"0x{frames['address']:04X}",
            "h_vblank_occurred_address": f"0x{frame['h_vblank_occurred_address']:04X}",
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "axis": "Disassembly",
        "game": game,
        "profile": profile_name,
        "functions": ["DelayFrame", "DelayFrames"],
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/delay-summary.json")
    common.write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/delay-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} delay routines\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) independently contain one ROM0 `DelayFrame` "
        "and one `DelayFrames` caller bound to it. The reports retain release identity, "
        "addresses, HRAM flag location and function hashes without publishing ROM bytes. "
        "Existing candidate/verified status is preserved and is not promoted by this match.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_delay_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    common.write_json(root / "manifests/delay-reconstruction.json", {
        "schema_version": 1,
        "axis": "Disassembly",
        "game": game,
        "profile": profile_name,
        "functions": ["DelayFrame", "DelayFrames"],
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen1_delay.py",
            "tool_sha256": common.file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": common.file_hash(root / path)}
                    for path in outputs],
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
