#!/usr/bin/env python3
"""Render all repository JASC palettes as deterministic PNG swatches."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import zlib
from pathlib import Path


LANGUAGES = {
    "jp": "Japanese",
    "ko": "Korean",
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "es": "Spanish",
}
LANGUAGE_PRIORITY = {name: index for index, name in enumerate(LANGUAGES.values())}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def parse_jasc(data: bytes) -> list[tuple[int, int, int]]:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("palette is not ASCII JASC-PAL") from error
    if len(lines) < 3 or lines[0] != "JASC-PAL" or lines[1] != "0100":
        raise ValueError("invalid JASC-PAL header")
    try:
        count = int(lines[2])
        colors = [tuple(map(int, line.split())) for line in lines[3:] if line.strip()]
    except ValueError as error:
        raise ValueError("invalid JASC-PAL numeric field") from error
    if count < 1 or len(colors) != count:
        raise ValueError("JASC-PAL color count mismatch")
    if any(len(color) != 3 or any(channel < 0 or channel > 255 for channel in color) for color in colors):
        raise ValueError("invalid JASC-PAL color")
    return colors


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def render(colors: list[tuple[int, int, int]], columns: int = 16, cell_size: int = 16) -> tuple[bytes, int, int]:
    if columns < 1 or cell_size < 1:
        raise ValueError("columns and cell size must be positive")
    width = min(columns, len(colors)) * cell_size
    rows = math.ceil(len(colors) / columns)
    height = rows * cell_size
    scanlines = []
    for y in range(height):
        palette_row = y // cell_size
        line = bytearray([0])
        for x in range(width):
            index = palette_row * columns + x // cell_size
            color = colors[index] if index < len(colors) else (0, 0, 0)
            line.extend(color)
        scanlines.append(bytes(line))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(b"".join(scanlines), 9))
        + png_chunk(b"IEND", b"")
    )
    return png, width, height


def palette_language(path: Path) -> str:
    stem = path.stem.lower()
    for code, language in LANGUAGES.items():
        if stem.endswith("-" + code):
            return language
    return "Japanese"


def contains_path(value: object, target: str) -> bool:
    if isinstance(value, dict):
        if value.get("path") == target:
            return True
        releases = value.get("releases")
        templates = value.get("path_templates")
        if isinstance(releases, dict) and isinstance(templates, dict):
            for template in templates.values():
                if isinstance(template, str) and "{language}" in template:
                    if any(template.replace("{language}", code) == target for code in releases):
                        return True
        return any(contains_path(item, target) for item in value.values())
    if isinstance(value, list):
        return any(contains_path(item, target) for item in value)
    return False


def provenance_manifests(root: Path, target: str) -> list[dict[str, str]]:
    owners = []
    for path in sorted((root / "manifests").glob("*.json")):
        if path.name == "palette-swatches.json":
            continue
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if contains_path(content, target):
            owners.append({"path": path.relative_to(root).as_posix(), "sha256": file_hash(path)})
    return owners


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def evidence_path(source: Path) -> Path:
    name = "-".join(source.with_suffix("").parts) + ".json"
    return Path("analysis/palette-swatches") / name


def build(root: Path, game: str) -> dict[str, object]:
    palettes = list((root / "graphics").rglob("*.pal"))
    if not palettes:
        raise ValueError("repository has no JASC palettes")
    palettes.sort(
        key=lambda path: (
            LANGUAGE_PRIORITY.get(palette_language(path), len(LANGUAGE_PRIORITY)),
            path.relative_to(root).as_posix(),
        )
    )
    records = []
    outputs: list[Path] = []
    for path in palettes:
        source = path.relative_to(root)
        source_text = source.as_posix()
        source_bytes = path.read_bytes()
        colors = parse_jasc(source_bytes)
        png, width, height = render(colors)
        png_path = source.with_name(source.stem + "-swatch.png")
        (root / png_path).write_bytes(png)
        owners = provenance_manifests(root, source_text)
        if not owners:
            raise ValueError(f"palette has no existing provenance manifest: {source_text}")
        language = palette_language(source)
        evidence = {
            "schema_version": 1,
            "game": game,
            "asset": "JASC palette swatch",
            "language": language,
            "origin_reference": language == "Japanese",
            "source": {
                "path": source_text,
                "sha256": digest(source_bytes),
                "format": "JASC-PAL 0100",
                "color_count": len(colors),
                "provenance_manifests": owners,
            },
            "output": {
                "path": png_path.as_posix(),
                "sha256": digest(png),
                "format": "PNG RGB8",
                "width": width,
                "height": height,
                "columns": min(16, len(colors)),
                "cell_size": 16,
            },
            "raw_rom_bytes_included": False,
        }
        report_path = evidence_path(source)
        write_json(root / report_path, evidence)
        outputs.extend((source, png_path, report_path))
        records.append(
            {
                "language": language,
                "origin_reference": language == "Japanese",
                "source": source_text,
                "source_sha256": digest(source_bytes),
                "color_count": len(colors),
                "png": png_path.as_posix(),
                "png_sha256": digest(png),
                "evidence": report_path.as_posix(),
            }
        )

    summary = {
        "schema_version": 1,
        "game": game,
        "asset": "JASC palette swatches",
        "palette_count": len(records),
        "official_korean_release_available": False,
        "palettes": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/palette-swatch-catalog.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/palette-swatches.md")
    (root / research_path).write_text(
        f"# {game} palette swatches\n\n"
        f"All {len(records)} existing JASC palettes ({languages}) are rendered as deterministic "
        "RGB PNG swatches. Japanese assets remain the origin reference where that asset family "
        "has a Japanese palette; official international palettes remain separate records.\n\n"
        "Each 16x16 cell represents one palette entry without interpolation or color correction. "
        "Evidence links the PNG to the exact palette hash and to the pre-existing ROM-derived "
        "manifest. No ROM bytes are copied into the catalog.\n",
        encoding="utf-8",
        newline="\n",
    )
    outputs.append(research_path)
    test_path = Path("tests/test_palette_swatches.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "game": game,
        "asset": "JASC palette swatches",
        "palette_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/render_jasc_palette_catalog.py",
            "tool_sha256": file_hash(Path(__file__)),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/palette-swatches.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--game", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.game)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
