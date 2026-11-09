#!/usr/bin/env python3
"""Reconstruct Generation I Delay3 and ProtectedDelay3 from verified delay targets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen1_clear_screen as common


PROFILES = {
    "classic": {"repository": "pret/pokered",
                "commit": "0dbf95cd12f5b1511c62ce69efe283000f780a8f"},
    "yellow": {"repository": "pret/pokeyellow",
               "commit": "b452f2ab07185075140061c5084ab866d5e4a794"},
}


def find_all(data: bytes, pattern: bytes, limit: int = 0x4000) -> list[int]:
    result, start = [], 0
    while True:
        offset = data.find(pattern, start, min(limit, len(data)))
        if offset < 0:
            return result
        result.append(offset)
        start = offset + 1


def locate_delay3(data: bytes, delay_frames_address: int) -> list[dict]:
    code = bytes((0x0E, 3, 0xC3, delay_frames_address & 0xFF,
                  delay_frames_address >> 8))
    return [{"rom_offset": offset, "bank": 0, "address": offset,
             "range_end_exclusive": offset + len(code), "length": len(code),
             "frame_count": 3, "delay_frames_target": delay_frames_address,
             "code_sha256": common.digest(code)}
            for offset in find_all(data, code)]


def locate_protected_delay3(data: bytes, delay3_address: int) -> list[dict]:
    code = bytes((0xC5, 0xCD, delay3_address & 0xFF, delay3_address >> 8,
                  0xC1, 0xC9))
    return [{"rom_offset": offset, "bank": 0, "address": offset,
             "range_end_exclusive": offset + len(code), "length": len(code),
             "delay3_target": delay3_address, "preserved_register": "BC",
             "code_sha256": common.digest(code)}
            for offset in find_all(data, code)]


def source_text() -> str:
    return """SECTION \"Delay3 Reconstruction\", ROM0

Delay3::
    ld c, 3
    jp DelayFrames

SECTION \"ProtectedDelay3 Reconstruction\", ROM0

ProtectedDelay3::
    push bc
    call Delay3
    pop bc
    ret
"""


def build(root: Path, rom_dir: Path, game: str, profile_name: str) -> dict:
    profile = PROFILES[profile_name]
    catalog_path, releases = common.load_releases(root)
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with Japanese origin")
    delay_summary_path = Path("analysis/delay-summary.json")
    delay_summary = json.loads((root / delay_summary_path).read_text(encoding="utf-8"))
    delay_records = {item["id"]: item for item in delay_summary["releases"]}
    if set(delay_records) != {item["id"] for item in releases}:
        raise ValueError("delay summary does not cover the release catalog")
    roms = common.rom_index(rom_dir)
    source_path = Path("src/delay3.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    maps: list[Path] = []
    records = []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        if delay_records[release_id]["sha256"] != sha256:
            raise ValueError(f"delay evidence ROM mismatch: {release_id}")
        data = roms[sha256].read_bytes()
        delay_frames_address = int(delay_records[release_id]["delay_frames_address"], 16)
        delay3_matches = locate_delay3(data, delay_frames_address)
        if len(delay3_matches) != 1:
            raise ValueError(f"expected one Delay3 in {release_id}, found {len(delay3_matches)}")
        delay3 = delay3_matches[0]
        protected_matches = locate_protected_delay3(data, delay3["address"])
        if len(protected_matches) != 1:
            raise ValueError(
                f"expected one ProtectedDelay3 in {release_id}, found {len(protected_matches)}")
        protected = protected_matches[0]
        evidence = {
            "schema_version": 1,
            "axis": "Disassembly",
            "target": {"release": release_id, "sha256": sha256,
                       "status": release.get("status", "candidate")},
            "origin_reference": index == 0,
            "profile": profile_name,
            "source": source_path.as_posix(),
            "source_sha256": common.file_hash(root / source_path),
            "dependency": {"path": delay_summary_path.as_posix(),
                           "sha256": common.file_hash(root / delay_summary_path),
                           "delay_frames_address": delay_frames_address},
            "functions": {"Delay3": delay3, "ProtectedDelay3": protected},
            "semantics": {
                "Delay3": "load C with three and tail-jump to DelayFrames",
                "ProtectedDelay3": "preserve BC while calling Delay3",
                "bg_update_reason": "wait three frames for the three-part background map update",
            },
            "naming_basis": {"repository": profile["repository"],
                             "commit": profile["commit"],
                             "paths": ["home/palettes.asm", "home/text.asm"]},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-delay3.json")
        common.write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id, "language": release["language"],
            "revision": int(release["revision"]),
            "status": release.get("status", "candidate"), "sha256": sha256,
            "origin_reference": index == 0,
            "delay3_address": f"0x{delay3['address']:04X}",
            "protected_delay3_address": f"0x{protected['address']:04X}",
            "delay_frames_target": f"0x{delay_frames_address:04X}",
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "profile": profile_name, "functions": ["Delay3", "ProtectedDelay3"],
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "source": source_path.as_posix(), "dependency": delay_summary_path.as_posix(),
        "releases": records, "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/delay3-summary.json")
    common.write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/delay3-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} Delay3 routines\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} "
        f"cataloged releases ({languages}) contain one `Delay3` tail-call bound to the "
        "previously verified release-specific `DelayFrames` address and one "
        "`ProtectedDelay3` wrapper that preserves BC. Reports retain identities, call "
        "relationships and hashes without ROM bytes; release status is not promoted.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_delay3_reconstruction.py")
    outputs = [catalog_path, delay_summary_path, source_path, summary_path,
               *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    common.write_json(root / "manifests/delay3-reconstruction.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "profile": profile_name, "functions": ["Delay3", "ProtectedDelay3"],
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gen1_delay3.py",
                      "tool_sha256": common.file_hash(Path(__file__))},
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
