#!/usr/bin/env python3
"""Catalog the Generation II SpeechTextbox entry across release sets."""
from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_gen2_clear_screen as common

ROUTINE_LENGTH = 10

def digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def file_hash(path: Path) -> str: return digest(path.read_bytes())
def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")

def decode_candidate(data: bytes, offset: int, textbox_address: int) -> dict | None:
    code = data[offset:offset + ROUTINE_LENGTH]
    if len(code) != ROUTINE_LENGTH:
        return None
    if not (code[0] == 0x21 and code[3:7] == bytes.fromhex("06040e12")
            and code[7] == 0xC3 and int.from_bytes(code[8:10], "little") == textbox_address):
        return None
    pointer = int.from_bytes(code[1:3], "little")
    if not 0xC000 <= pointer <= 0xDFFF:
        return None
    return {"offset": offset, "length": ROUTINE_LENGTH, "tilemap_pointer": pointer,
            "inner_height": 4, "inner_width": 18,
            "textbox_address": textbox_address, "transfer": "tail-jump"}

def locate(data: bytes, textbox_address: int) -> list[dict]:
    return [item for offset in range(0x150, min(0x4000, len(data)) - ROUTINE_LENGTH + 1)
            if (item := decode_candidate(data, offset, textbox_address)) is not None]

def source_text() -> str:
    return '''SECTION "SpeechTextbox Reconstruction", ROM0

SpeechTextbox::
    hlcoord TEXTBOX_X, TEXTBOX_Y
    ld b, TEXTBOX_INNERH
    ld c, TEXTBOX_INNERW
    jp Textbox
'''

def build(root: Path, rom_dir: Path, game: str, profile_name: str) -> dict:
    profile = common.PROFILES[profile_name]
    catalog_path = Path("research/releases.csv")
    releases = common.load_releases(root / catalog_path)
    source_path = Path("src/speech_textbox.asm")
    (root / source_path).write_text(source_text(), encoding="utf-8", newline="\n")
    roms = common.rom_index(rom_dir)
    maps, records = [], []
    for index, release in enumerate(releases):
        rid, sha256 = release["id"], release["sha256"]
        if sha256 not in roms: raise ValueError(f"missing catalog ROM: {rid}")
        textbox_path = Path(f"analysis/{rid}-textbox.json")
        textbox = json.loads((root / textbox_path).read_text(encoding="utf-8"))
        if textbox["target"]["sha256"] != sha256: raise ValueError(f"Textbox identity differs: {rid}")
        textbox_address = textbox["functions"]["Textbox"]["address"]
        data = roms[sha256].read_bytes()
        matches = locate(data, textbox_address)
        if len(matches) != 1: raise ValueError(f"expected one SpeechTextbox in {rid}, found {len(matches)}")
        match = matches[0]; start = match["offset"]; end = start + ROUTINE_LENGTH
        evidence = {
            "schema_version": 1, "axis": "Disassembly", "profile": profile_name,
            "target": {"release": rid, "sha256": sha256,
                       "status": release.get("status", "candidate")},
            "origin_reference": index == 0, "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "function": {"name": "SpeechTextbox", "rom_offset": start, "bank": 0,
                         "address": start, "range_end_exclusive": end,
                         "length": ROUTINE_LENGTH, "code_sha256": digest(data[start:end]),
                         "raw_bytes_published": False},
            "verified_behavior": {"tilemap_pointer": match["tilemap_pointer"],
                                  "inner_height": 4, "inner_width": 18,
                                  "height_register": "B", "width_register": "C",
                                  "textbox_transfer": {"kind": "tail-jump",
                                                       "address": textbox_address}},
            "cross_reference": {"textbox_map": textbox_path.as_posix(),
                                "textbox_map_sha256": file_hash(root / textbox_path)},
            "naming_basis": {"repository": profile["repository"],
                             "commit": profile["commit"], "path": profile["path"]},
            "raw_rom_bytes_included": False}
        map_path = Path(f"analysis/{rid}-speech-textbox.json")
        write_json(root / map_path, evidence); maps.append(map_path)
        records.append({"id": rid, "language": release["language"],
                        "revision": int(release["revision"]),
                        "status": release.get("status", "candidate"), "sha256": sha256,
                        "origin_reference": index == 0, "address": f"0x{start:04X}",
                        "tilemap_pointer": f"0x{match['tilemap_pointer']:04X}",
                        "textbox_address": f"0x{textbox_address:04X}",
                        "evidence": map_path.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game,
               "function": "SpeechTextbox", "profile": profile_name,
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "source": source_path.as_posix(), "releases": records,
               "raw_rom_bytes_included": False}
    summary_path = Path("analysis/speech-textbox-summary.json"); write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(x["language"] for x in records))
    research_path = Path("research/speech-textbox-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} SpeechTextbox disassembly\n\n`{releases[0]['id']}` is the Japanese "
        f"origin reference. All {len(records)} cataloged releases ({languages}) contain one "
        "10-byte entry that loads the release-specific textbox tilemap pointer, sets a 4-by-18 "
        "interior, and tail-jumps to the independently verified Textbox entry. Candidate status "
        "is retained; evidence contains hashes and decoded operands, not ROM bytes.\n",
        encoding="utf-8", newline="\n")
    test_path = Path("tests/test_speech_textbox_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [p.as_posix() for p in outputs if not (root / p).is_file()]
    if missing: raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/speech-textbox-reconstruction.json", {
        "schema_version": 1, "axis": "Disassembly", "game": game,
        "function": "SpeechTextbox", "profile": profile_name,
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_gen2_speech_textbox.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": p.as_posix(), "sha256": file_hash(root / p)} for p in outputs],
        "raw_rom_bytes_included": False})
    return summary

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True); p.add_argument("--rom-dir", type=Path, required=True)
    p.add_argument("--game", required=True); p.add_argument("--profile", choices=sorted(common.PROFILES), required=True)
    a = p.parse_args()
    try: build(a.root, a.rom_dir, a.game, a.profile)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as e: p.error(str(e))
    return 0
if __name__ == "__main__": raise SystemExit(main())

