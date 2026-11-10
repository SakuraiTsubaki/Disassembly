#!/usr/bin/env python3
"""Reconstruct Generation II ClearSprites and HideSprites across releases."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


CLEAR_LENGTH = 11
HIDE_LENGTH = 16
PAIR_LENGTH = CLEAR_LENGTH + HIDE_LENGTH


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


def decode(data: bytes, offset: int) -> dict | None:
    code = data[offset:offset + PAIR_LENGTH]
    if len(code) != PAIR_LENGTH:
        return None
    if code[0] != 0x21 or code[3:] [:8] != bytes.fromhex("06a0af220520fcc9"):
        return None
    hide = code[CLEAR_LENGTH:]
    if hide[0] != 0x21 or hide[3:] != bytes.fromhex("11040006283ea077190520fbc9"):
        return None
    clear_address = int.from_bytes(code[1:3], "little")
    hide_address = int.from_bytes(hide[1:3], "little")
    if clear_address != hide_address or offset >= 0x4000:
        return None
    return {
        "ClearSprites": {
            "rom_offset": offset,
            "bank": 0,
            "address": offset,
            "range_end_exclusive": offset + CLEAR_LENGTH,
            "length": CLEAR_LENGTH,
            "w_shadow_oam_address": clear_address,
            "byte_count": 160,
            "code_sha256": digest(code[:CLEAR_LENGTH]),
        },
        "HideSprites": {
            "rom_offset": offset + CLEAR_LENGTH,
            "bank": 0,
            "address": offset + CLEAR_LENGTH,
            "range_end_exclusive": offset + PAIR_LENGTH,
            "length": HIDE_LENGTH,
            "w_shadow_oam_y_address": hide_address,
            "object_stride": 4,
            "object_count": 40,
            "hidden_y": 160,
            "code_sha256": digest(hide),
        },
        "combined_sha256": digest(code),
    }


def locate(data: bytes) -> list[dict]:
    return [
        match for offset in range(min(0x4000, len(data)) - PAIR_LENGTH + 1)
        if (match := decode(data, offset)) is not None
    ]


def source_text() -> str:
    return """SECTION "Sprite Clearing Reconstruction", ROM0

ClearSprites::
    ld hl, wShadowOAM
    ld b, wShadowOAMEnd - wShadowOAM
    xor a
.loop
    ld [hli], a
    dec b
    jr nz, .loop
    ret

HideSprites::
    ld hl, wShadowOAMSprite00YCoord
    ld de, OBJ_SIZE
    ld b, OAM_COUNT
    ld a, OAM_YCOORD_HIDDEN
.loop
    ld [hl], a
    add hl, de
    dec b
    jr nz, .loop
    ret
"""


def build(root: Path, rom_dir: Path, game: str, reference_repository: str,
          reference_commit: str) -> dict:
    catalog_path = Path("research/releases.csv")
    releases = load_releases(root / catalog_path)
    roms = rom_index(rom_dir)
    source_path = Path("src/clear_hide_sprites.asm")
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
            raise ValueError(f"expected one sprite-clear pair in {release_id}, found {len(matches)}")
        found = matches[0]
        evidence = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256, "status": release["status"]},
            "origin_reference": index == 0,
            "source": source_path.as_posix(),
            "source_sha256": file_hash(root / source_path),
            "functions": found,
            "semantics": {
                "ClearSprites": "zero all 160 bytes of shadow OAM",
                "HideSprites": "write Y=160 to each of 40 four-byte shadow OAM entries",
                "shared_base": "both routines begin at the same release-specific shadow OAM address",
            },
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "home/clear_sprites.asm",
            },
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{release_id}-clear-hide-sprites.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": int(release["revision"]),
            "status": release["status"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "clear_sprites_address": f"0x{found['ClearSprites']['address']:04X}",
            "hide_sprites_address": f"0x{found['HideSprites']['address']:04X}",
            "w_shadow_oam_address": f"0x{found['ClearSprites']['w_shadow_oam_address']:04X}",
            "combined_sha256": found["combined_sha256"],
            "evidence": map_path.as_posix(),
        })
    summary = {
        "schema_version": 1,
        "game": game,
        "functions": ["ClearSprites", "HideSprites"],
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source": source_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/clear-hide-sprites-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/clear-hide-sprites-reconstruction.md")
    (root / research_path).write_text(
        f"# {game} ClearSprites and HideSprites\n\n"
        f"The Japanese release `{releases[0]['id']}` is the origin reference. "
        f"All {len(records)} cataloged releases ({languages}) contain exactly one "
        "adjacent ROM0 pair. The reports preserve the release-specific shadow OAM "
        "address and routine hashes without ROM bytes. `ClearSprites` clears 160 "
        "bytes; `HideSprites` writes Y=160 to 40 entries with stride four. "
        "Korean precedes English where available, and release status is unchanged.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path("tests/test_clear_hide_sprites_reconstruction.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/clear-hide-sprites-reconstruction.json", {
        "schema_version": 1,
        "game": game,
        "functions": ["ClearSprites", "HideSprites"],
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gen2_clear_hide_sprites.py",
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
