#!/usr/bin/env python3
"""Extract and verify the complete Generation II party-icon atlas."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_gb_2bpp


ICON_NAMES = (
    "poliwag", "jigglypuff", "diglett", "pikachu", "staryu", "fish",
    "bird", "monster", "clefairy", "oddish", "bug", "ghost", "lapras",
    "humanshape", "fox", "equine", "shell", "blob", "serpent", "voltorb",
    "squirtle", "bulbasaur", "charmander", "caterpillar", "unown",
    "geodude", "fighter", "egg", "jellyfish", "moth", "bat", "snorlax",
    "ho_oh", "lugia", "gyarados", "slowpoke", "sudowoodo", "bigmon",
)
ICON_WIDTH = 16
ICON_HEIGHT = 32
TILES_PER_ICON = 8
BYTES_PER_ICON = TILES_PER_ICON * 16
LENGTH = len(ICON_NAMES) * BYTES_PER_ICON
ICONS_PER_ROW = 8
EXPECTED_SOURCE_SHA256 = "c06b31c95d7bd0c80b17ca9d1a7e7d55c1cb0f2f4f0eb302e5c1d7547f755c77"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def unique_offset(data: bytes, signature: bytes) -> int:
    found: list[int] = []
    start = 0
    while True:
        offset = data.find(signature, start)
        if offset < 0:
            break
        found.append(offset)
        start = offset + 1
    if len(found) != 1:
        raise ValueError(f"expected one party-icon table, found {len(found)}")
    return found[0]


def rom_index(directory: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in (".gb", ".gbc"):
            result.setdefault(file_hash(path), path)
    return result


def atlas_tiles(raw: bytes) -> bytes:
    """Reorder icon-local 2x4 tile blocks into an 8-icon-wide atlas."""
    if len(raw) != LENGTH:
        raise ValueError(f"party-icon table must contain exactly {LENGTH} bytes")
    rows = math.ceil(len(ICON_NAMES) / ICONS_PER_ROW)
    blank = bytes(BYTES_PER_ICON)
    icons = [raw[i:i + BYTES_PER_ICON] for i in range(0, len(raw), BYTES_PER_ICON)]
    icons.extend([blank] * (rows * ICONS_PER_ROW - len(icons)))
    output = bytearray()
    for icon_row in range(rows):
        for tile_row in range(4):
            for icon_column in range(ICONS_PER_ROW):
                icon = icons[icon_row * ICONS_PER_ROW + icon_column]
                start = tile_row * 2 * 16
                output.extend(icon[start:start + 2 * 16])
    return bytes(output)


def build(
    root: Path,
    rom_dir: Path,
    origin_release: str,
    origin_offset: int,
    game: str,
    reference_repository: str,
    reference_commit: str,
) -> dict[str, object]:
    with (root / "research/releases.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["id"]: row for row in rows}
    origin = by_id[origin_release]
    roms = rom_index(rom_dir)
    origin_sha = origin["sha256"]
    if origin_sha not in roms:
        raise ValueError("origin ROM is missing")

    origin_data = roms[origin_sha].read_bytes()
    raw = origin_data[origin_offset:origin_offset + LENGTH]
    if len(raw) != LENGTH:
        raise ValueError("origin range leaves ROM")
    raw_hash = digest(raw)
    if raw_hash != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"unexpected party-icon table hash: {raw_hash}")

    arranged = atlas_tiles(raw)
    png = extract_gb_2bpp.render(arranged, ICONS_PER_ROW * 2, scale=2)
    png_path = Path("graphics/pokemon/party-icons-atlas.png")
    (root / png_path).parent.mkdir(parents=True, exist_ok=True)
    (root / png_path).write_bytes(png)

    atlas_rows = math.ceil(len(ICON_NAMES) / ICONS_PER_ROW)
    icons = []
    for index, name in enumerate(ICON_NAMES):
        x = (index % ICONS_PER_ROW) * ICON_WIDTH
        y = (index // ICONS_PER_ROW) * ICON_HEIGHT
        icons.append({
            "index": index,
            "name": name,
            "logical_rect": {"x": x, "y": y, "width": ICON_WIDTH, "height": ICON_HEIGHT},
            "png_rect": {"x": x * 2, "y": y * 2, "width": ICON_WIDTH * 2, "height": ICON_HEIGHT * 2},
        })
    layout_path = Path("graphics/pokemon/party-icons-atlas.json")
    write_json(root / layout_path, {
        "schema_version": 1,
        "layout": "8 icons per row; each icon is a 2x4 Game Boy tile block",
        "icon_count": len(ICON_NAMES),
        "icons_per_row": ICONS_PER_ROW,
        "logical_width": ICONS_PER_ROW * ICON_WIDTH,
        "logical_height": atlas_rows * ICON_HEIGHT,
        "png_scale": 2,
        "icons": icons,
    })

    outputs: list[Path] = [png_path, layout_path]
    records = []
    for row in rows:
        sha = row["sha256"]
        release_id = row["id"]
        if sha not in roms:
            raise ValueError(f"missing release ROM: {release_id}")
        target = roms[sha].read_bytes()
        offset = origin_offset if sha == origin_sha else unique_offset(target, raw)
        if target[offset:offset + LENGTH] != raw:
            raise ValueError(f"party-icon mismatch: {release_id}")
        report = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha},
            "asset": {
                "name": "PartyIcons",
                "source_offset": offset,
                "source_length": LENGTH,
                "source_sha256": raw_hash,
                "format": "game-boy-2bpp-8x8-tiles",
                "icon_count": len(ICON_NAMES),
                "icon_width": ICON_WIDTH,
                "icon_height": ICON_HEIGHT,
                "tiles_per_icon": TILES_PER_ICON,
            },
            "outputs": [
                {"path": png_path.as_posix(), "sha256": digest(png), "width": 256, "height": 320, "scale": 2},
                {"path": layout_path.as_posix(), "sha256": file_hash(root / layout_path)},
            ],
            "origin_reference": sha == origin_sha,
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "gfx/icons.asm",
                "asset_directory": "gfx/icons",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        evidence_path = Path(f"analysis/{release_id}-party-icons.json")
        write_json(root / evidence_path, report)
        outputs.append(evidence_path)
        records.append({
            "id": release_id,
            "language": row["language"],
            "revision": int(row["revision"]),
            "sha256": sha,
            "origin_reference": sha == origin_sha,
            "evidence": evidence_path.as_posix(),
            "source_offset": offset,
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "asset": "PartyIcons",
        "origin_reference": origin_release,
        "release_count": len(records),
        "source_sha256": raw_hash,
        "icon_count": len(ICON_NAMES),
        "png": png_path.as_posix(),
        "layout": layout_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/party-icons-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)

    research_path = Path("research/party-icons.md")
    languages = ", ".join(dict.fromkeys(record["language"] for record in records))
    (root / research_path).write_text(
        f"# {game} party icons\n\n"
        f"The Japanese release `{origin_release}` is the origin reference. The complete "
        f"{LENGTH:,}-byte party-icon table is byte-identical in all {len(records)} verified "
        f"releases ({languages}), including Korean where officially available. It contains "
        f"{len(ICON_NAMES)} icon types, each stored as an uncompressed 16x32 2bpp image.\n\n"
        "`graphics/pokemon/party-icons-atlas.png` is regenerated directly from the verified "
        "ROM range. Its JSON companion maps every named icon to logical and scaled PNG "
        "rectangles. Per-release evidence preserves identities, offsets, and hashes without "
        "publishing raw ROM bytes. Naming and storage order follow "
        f"`{reference_repository}` at `{reference_commit}`, `gfx/icons.asm`.\n",
        encoding="utf-8",
        newline="\n",
    )
    outputs.append(research_path)

    test_path = Path("tests/test_party_icons.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))

    manifest = {
        "schema_version": 1,
        "game": game,
        "asset": "PartyIcons",
        "origin_reference": origin_release,
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/extract_gen2_party_icons.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/party-icons.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--origin-release", required=True)
    parser.add_argument("--origin-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(
            args.root,
            args.rom_dir,
            args.origin_release,
            args.origin_offset,
            args.game,
            args.reference_repository,
            args.reference_commit,
        )
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
