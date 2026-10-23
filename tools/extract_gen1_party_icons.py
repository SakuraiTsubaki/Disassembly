#!/usr/bin/env python3
"""Extract and verify the Generation I animated party-icon atlas."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_gb_2bpp


ICON_NAMES = ("bug", "plant", "snake", "quadruped")
FRAME_BYTES = 32
FRAMES_PER_ICON = 2
ICON_BYTES = FRAME_BYTES * FRAMES_PER_ICON
LENGTH = len(ICON_NAMES) * ICON_BYTES
EXPECTED_SOURCE_SHA256 = "7512db31bd72d44a7b5a918167d1e2baad594729fc591b428b86f07fb9ac7453"
LANGUAGES = {"jp": "Japanese", "en": "English", "de": "German", "fr": "French", "it": "Italian", "es": "Spanish"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def release_language(release_id: str) -> str:
    parts = release_id.split("-")
    for part in parts:
        if part in LANGUAGES:
            return LANGUAGES[part]
    raise ValueError(f"cannot determine release language: {release_id}")


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
        raise ValueError(f"expected one party-icon block, found {len(found)}")
    return found[0]


def rom_index(directory: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in (".gb", ".gbc"):
            result.setdefault(file_hash(path), path)
    return result


def split_icons(raw: bytes) -> dict[str, bytes]:
    if len(raw) != LENGTH:
        raise ValueError(f"party-icon block must contain exactly {LENGTH} bytes")
    chunks = [raw[index:index + FRAME_BYTES] for index in range(0, len(raw), FRAME_BYTES)]
    return {
        "bug": chunks[0] + chunks[2],
        "plant": chunks[1] + chunks[3],
        "snake": chunks[4] + chunks[6],
        "quadruped": chunks[5] + chunks[7],
    }


def atlas_tiles(raw: bytes) -> bytes:
    icons = split_icons(raw)
    output = bytearray()
    for tile_row in range(4):
        for name in ICON_NAMES:
            start = tile_row * 16
            output.extend(icons[name][start:start + 16])
    return bytes(output)


def flip_tile_horizontally(tile: bytes) -> bytes:
    if len(tile) != 16:
        raise ValueError("a 2bpp tile must contain 16 bytes")
    return bytes(int(f"{value:08b}"[::-1], 2) for value in tile)


def composed_atlas_tiles(raw: bytes) -> bytes:
    """Expand stored half-icons into the symmetric 16x16 form drawn by OAM."""
    icons = split_icons(raw)
    output = bytearray()
    for tile_row in range(4):
        for name in ICON_NAMES:
            start = tile_row * 16
            tile = icons[name][start:start + 16]
            output.extend(tile)
            output.extend(flip_tile_horizontally(tile))
    return bytes(output)


def build(
    root: Path,
    rom_dir: Path,
    release_report: Path,
    origin_release: str,
    origin_offset: int,
    game: str,
    reference_repository: str,
    reference_commit: str,
) -> dict[str, object]:
    catalog = json.loads((root / release_report).read_text(encoding="utf-8"))
    rows = catalog["releases"]
    by_id = {row["id"]: row for row in rows}
    origin = by_id[origin_release]
    if release_language(rows[0]["id"]) != "Japanese":
        raise ValueError("release report must begin with the Japanese origin family")
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
        raise ValueError(f"unexpected party-icon block hash: {raw_hash}")

    source_png = extract_gb_2bpp.render(atlas_tiles(raw), len(ICON_NAMES), scale=4)
    png = extract_gb_2bpp.render(composed_atlas_tiles(raw), len(ICON_NAMES) * 2, scale=4)
    png_path = Path("graphics/pokemon/party-icons-atlas.png")
    source_png_path = Path("graphics/pokemon/party-icons-source-atlas.png")
    (root / png_path).parent.mkdir(parents=True, exist_ok=True)
    (root / png_path).write_bytes(png)
    (root / source_png_path).write_bytes(source_png)
    assets = []
    for index, name in enumerate(ICON_NAMES):
        assets.append({
            "name": name,
            "logical_rect": {"x": index * 16, "y": 0, "width": 16, "height": 32},
            "png_rect": {"x": index * 64, "y": 0, "width": 64, "height": 128},
            "source_logical_rect": {"x": index * 8, "y": 0, "width": 8, "height": 32},
            "source_png_rect": {"x": index * 32, "y": 0, "width": 32, "height": 128},
            "frames": [
                {"index": 0, "logical_rect": {"x": index * 16, "y": 0, "width": 16, "height": 16}, "png_rect": {"x": index * 64, "y": 0, "width": 64, "height": 64}},
                {"index": 1, "logical_rect": {"x": index * 16, "y": 16, "width": 16, "height": 16}, "png_rect": {"x": index * 64, "y": 64, "width": 64, "height": 64}},
            ],
        })
    layout_path = Path("graphics/pokemon/party-icons-atlas.json")
    write_json(root / layout_path, {
        "schema_version": 1,
        "layout": "four composed icon types in columns; animation frame 1 above frame 2",
        "composition": "each stored 8-pixel-wide half is followed by its horizontal mirror, matching symmetric OAM display",
        "icon_count": len(ICON_NAMES),
        "frames_per_icon": FRAMES_PER_ICON,
        "logical_width": 64,
        "logical_height": 32,
        "source_atlas": {"path": source_png_path.as_posix(), "logical_width": 32, "logical_height": 32},
        "png_scale": 4,
        "icons": assets,
    })

    outputs: list[Path] = [png_path, source_png_path, layout_path]
    records = []
    for row in rows:
        release_id = row["id"]
        sha256 = row["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing release ROM: {release_id}")
        data = roms[sha256].read_bytes()
        offset = origin_offset if sha256 == origin_sha else unique_offset(data, raw)
        if data[offset:offset + LENGTH] != raw:
            raise ValueError(f"party-icon mismatch: {release_id}")
        report = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "asset": {
                "name": "AnimatedPartyIcons",
                "source_offset": offset,
                "source_length": LENGTH,
                "source_sha256": raw_hash,
                "format": "game-boy-2bpp-8x8-tiles",
                "icon_count": len(ICON_NAMES),
                "frames_per_icon": FRAMES_PER_ICON,
                "stored_half_width": 8,
                "logical_icon_width": 16,
                "logical_icon_height": 32,
                "composition": "horizontal mirror",
            },
            "outputs": [
                {"path": png_path.as_posix(), "sha256": digest(png), "width": 256, "height": 128, "scale": 4, "kind": "composed"},
                {"path": source_png_path.as_posix(), "sha256": digest(source_png), "width": 128, "height": 128, "scale": 4, "kind": "stored-halves"},
                {"path": layout_path.as_posix(), "sha256": file_hash(root / layout_path)},
            ],
            "origin_reference": sha256 == origin_sha,
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "engine/gfx/mon_icons.asm",
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
            "language": release_language(release_id),
            "revision": row["header"]["revision"],
            "sha256": sha256,
            "origin_reference": sha256 == origin_sha,
            "source_offset": offset,
            "evidence": evidence_path.as_posix(),
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "asset": "AnimatedPartyIcons",
        "origin_reference": origin_release,
        "release_count": len(records),
        "source_sha256": raw_hash,
        "icon_count": len(ICON_NAMES),
        "frames_per_icon": FRAMES_PER_ICON,
        "png": png_path.as_posix(),
        "source_png": source_png_path.as_posix(),
        "layout": layout_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/party-icons-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)

    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/party-icons.md")
    (root / research_path).write_text(
        f"# {game} animated party icons\n\n"
        f"The Japanese release `{origin_release}` is the origin reference. The complete "
        f"{LENGTH}-byte icon block is byte-identical in all {len(records)} verified releases "
        f"({languages}). It contains two animation frames for Bug, Plant, Snake, and "
        "Quadruped party-menu icon types.\n\n"
        "The source atlas preserves each stored 8-pixel-wide half. The composed atlas mirrors "
        "that half horizontally, matching the symmetric OAM form displayed by the game, and "
        "scales it by four without interpolation. Its JSON companion records named icon and "
        "frame rectangles. Per-release evidence retains ROM identities, offsets, "
        "and hashes without publishing raw ROM bytes. Ordering and names follow "
        f"`{reference_repository}` at `{reference_commit}`, `engine/gfx/mon_icons.asm`.\n",
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
        "asset": "AnimatedPartyIcons",
        "origin_reference": origin_release,
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/extract_gen1_party_icons.py",
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
    parser.add_argument("--release-report", type=Path, required=True)
    parser.add_argument("--origin-release", required=True)
    parser.add_argument("--origin-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--reference-repository", required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.release_report, args.origin_release, args.origin_offset, args.game, args.reference_repository, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
