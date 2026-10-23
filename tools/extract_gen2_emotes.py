#!/usr/bin/env python3
"""Extract and verify Generation II overworld emotes and field effects."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_gb_2bpp


EMOTE_NAMES = ("shock", "question", "happy", "sad", "heart", "bolt", "sleep", "fish")
EFFECTS = (
    ("shadow", 8, 8, 16),
    ("fishing_rod", 8, 16, 32),
    ("boulder_dust", 8, 16, 32),
    ("grass_rustle", 8, 8, 16),
)
EMOTE_BYTES = 64
EMOTE_LENGTH = len(EMOTE_NAMES) * EMOTE_BYTES
LENGTH = EMOTE_LENGTH + sum(item[3] for item in EFFECTS)
EXPECTED_SOURCE_SHA256 = "24108a3d88e346484161dc651c67df97f0ff2e0eaacdc1d3d53e7bc815e32b6d"


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
        raise ValueError(f"expected one emote/effect block, found {len(found)}")
    return found[0]


def rom_index(directory: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in (".gb", ".gbc"):
            result.setdefault(file_hash(path), path)
    return result


def arrange_emotes(raw: bytes) -> bytes:
    """Reorder eight icon-local 2x2 tile blocks into a four-icon-wide atlas."""
    if len(raw) != EMOTE_LENGTH:
        raise ValueError(f"emote table must contain exactly {EMOTE_LENGTH} bytes")
    icons = [raw[index:index + EMOTE_BYTES] for index in range(0, len(raw), EMOTE_BYTES)]
    arranged = bytearray()
    for icon_row in range(2):
        for tile_row in range(2):
            for icon_column in range(4):
                icon = icons[icon_row * 4 + icon_column]
                start = tile_row * 32
                arranged.extend(icon[start:start + 32])
    return bytes(arranged)


def arrange_effects(raw: bytes) -> bytes:
    """Place four one-tile-wide effects into a two-tile-high atlas."""
    if len(raw) != LENGTH - EMOTE_LENGTH:
        raise ValueError("effect table has an unexpected length")
    chunks = []
    cursor = 0
    for _, _, _, size in EFFECTS:
        chunks.append(raw[cursor:cursor + size])
        cursor += size
    blank = bytes(16)
    return b"".join((chunks[0][:16], chunks[1][:16], chunks[2][:16], chunks[3][:16], blank, chunks[1][16:], chunks[2][16:], blank))


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
        raise ValueError(f"unexpected emote/effect block hash: {raw_hash}")

    emote_png = extract_gb_2bpp.render(arrange_emotes(raw[:EMOTE_LENGTH]), 8, scale=2)
    effect_png = extract_gb_2bpp.render(arrange_effects(raw[EMOTE_LENGTH:]), 4, scale=2)
    emote_path = Path("graphics/overworld/emotes-atlas.png")
    effect_path = Path("graphics/overworld/effects-atlas.png")
    (root / emote_path).parent.mkdir(parents=True, exist_ok=True)
    (root / emote_path).write_bytes(emote_png)
    (root / effect_path).write_bytes(effect_png)

    assets = []
    source_cursor = 0
    for index, name in enumerate(EMOTE_NAMES):
        x, y = (index % 4) * 16, (index // 4) * 16
        assets.append({
            "name": name,
            "category": "emote",
            "source_offset": source_cursor,
            "source_length": EMOTE_BYTES,
            "logical_rect": {"x": x, "y": y, "width": 16, "height": 16},
            "png_rect": {"x": x * 2, "y": y * 2, "width": 32, "height": 32},
        })
        source_cursor += EMOTE_BYTES
    for index, (name, width, height, size) in enumerate(EFFECTS):
        assets.append({
            "name": name,
            "category": "field_effect",
            "source_offset": source_cursor,
            "source_length": size,
            "logical_rect": {"x": index * 8, "y": 0, "width": width, "height": height},
            "png_rect": {"x": index * 16, "y": 0, "width": width * 2, "height": height * 2},
        })
        source_cursor += size
    layout_path = Path("graphics/overworld/emotes-effects-atlas.json")
    write_json(root / layout_path, {
        "schema_version": 1,
        "source_length": LENGTH,
        "emotes": {"path": emote_path.as_posix(), "count": len(EMOTE_NAMES), "logical_width": 64, "logical_height": 32, "png_scale": 2},
        "field_effects": {"path": effect_path.as_posix(), "count": len(EFFECTS), "logical_width": 32, "logical_height": 16, "png_scale": 2},
        "assets": assets,
    })

    outputs: list[Path] = [emote_path, effect_path, layout_path]
    records = []
    for row in rows:
        sha = row["sha256"]
        release_id = row["id"]
        if sha not in roms:
            raise ValueError(f"missing release ROM: {release_id}")
        target = roms[sha].read_bytes()
        offset = origin_offset if sha == origin_sha else unique_offset(target, raw)
        if target[offset:offset + LENGTH] != raw:
            raise ValueError(f"emote/effect mismatch: {release_id}")
        report = {
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha},
            "asset": {
                "name": "OverworldEmotesAndEffects",
                "source_offset": offset,
                "source_length": LENGTH,
                "source_sha256": raw_hash,
                "format": "game-boy-2bpp-8x8-tiles",
                "emote_count": len(EMOTE_NAMES),
                "field_effect_count": len(EFFECTS),
            },
            "outputs": [
                {"path": emote_path.as_posix(), "sha256": digest(emote_png), "width": 128, "height": 64, "scale": 2},
                {"path": effect_path.as_posix(), "sha256": digest(effect_png), "width": 64, "height": 32, "scale": 2},
                {"path": layout_path.as_posix(), "sha256": file_hash(root / layout_path)},
            ],
            "origin_reference": sha == origin_sha,
            "naming_basis": {
                "repository": reference_repository,
                "commit": reference_commit,
                "path": "gfx/emotes.asm",
                "raw_rom_bytes_published": False,
            },
            "raw_rom_bytes_included": False,
        }
        evidence_path = Path(f"analysis/{release_id}-emotes-effects.json")
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
        "asset": "OverworldEmotesAndEffects",
        "origin_reference": origin_release,
        "release_count": len(records),
        "source_sha256": raw_hash,
        "emote_count": len(EMOTE_NAMES),
        "field_effect_count": len(EFFECTS),
        "emotes_png": emote_path.as_posix(),
        "effects_png": effect_path.as_posix(),
        "layout": layout_path.as_posix(),
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/emotes-effects-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)

    research_path = Path("research/emotes-effects.md")
    languages = ", ".join(dict.fromkeys(record["language"] for record in records))
    (root / research_path).write_text(
        f"# {game} overworld emotes and effects\n\n"
        f"The Japanese release `{origin_release}` is the origin reference. Its complete "
        f"{LENGTH}-byte block is byte-identical in all {len(records)} verified releases "
        f"({languages}), including Korean where officially available. The block contains "
        "eight 16x16 emotes followed by shadow, fishing-rod, boulder-dust, and grass-rustle "
        "field graphics.\n\n"
        "The two PNG atlases are regenerated directly from verified local ROM ranges; the "
        "layout JSON retains each asset's source-relative range and rendered rectangle. "
        "Per-release evidence records identities, absolute offsets, and hashes without "
        "publishing raw ROM bytes. Names and ordering follow "
        f"`{reference_repository}` at `{reference_commit}`, `gfx/emotes.asm`.\n",
        encoding="utf-8",
        newline="\n",
    )
    outputs.append(research_path)

    test_path = Path("tests/test_emotes_effects.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "game": game,
        "asset": "OverworldEmotesAndEffects",
        "origin_reference": origin_release,
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/extract_gen2_emotes.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/emotes-effects.json", manifest)
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
        build(args.root, args.rom_dir, args.origin_release, args.origin_offset, args.game, args.reference_repository, args.reference_commit)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
