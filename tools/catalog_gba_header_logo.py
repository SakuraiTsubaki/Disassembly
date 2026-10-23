#!/usr/bin/env python3
"""Extend an existing GBA header-logo extraction across a release catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_gba_header_logo


EXPECTED_LOGO_SHA256 = "08a0153cfd6b0ea54b938f7d209933fa849da0d56f5a34c481060c9ff2fad818"
EXPECTED_PNG_SHA256 = "f07daf6e489d64b7e2bbf80c7f23104dece36e88e706ee8a779790f6e8377a8b"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def rom_index(directory: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() == ".gba":
            result.setdefault(file_hash(path), path)
    return result


def release_report(extracted: dict, release: dict, origin_reference: bool, png_path: Path) -> dict:
    return {
        "schema_version": 1,
        "target": {
            "release": release["id"],
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": release["sha256"],
        },
        "asset": {
            "name": "GbaHeaderNintendoLogo",
            "source_offset": extracted["source_offset"],
            "source_length": extracted["source_length"],
            "source_sha256": extracted["source_bytes_sha256"],
            "format": extracted["format"],
            "logical_width": extracted["width"],
            "logical_height": extracted["height"],
        },
        "output": {
            "path": png_path.as_posix(),
            "sha256": extracted["png_sha256"],
            "width": extracted["png_width"],
            "height": extracted["png_height"],
            "nearest_neighbor_scale": extracted["nearest_neighbor_scale"],
        },
        "origin_reference": origin_reference,
        "standard_location": "GBA cartridge header 0x000004..0x00009F",
        "raw_rom_bytes_included": False,
    }


def build(
    root: Path,
    rom_dir: Path,
    catalog_path: Path,
    origin_evidence_path: Path,
    png_path: Path,
    game: str,
) -> dict[str, object]:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    existing_png = (root / png_path).read_bytes()
    if digest(existing_png) != EXPECTED_PNG_SHA256:
        raise ValueError("existing header-logo PNG is not the canonical decoded output")
    roms = rom_index(rom_dir)
    outputs: list[Path] = [png_path, catalog_path]
    records = []
    for index, release in enumerate(releases):
        release_id = release["id"]
        sha256 = release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        png, extracted = extract_gba_header_logo.extract(roms[sha256].read_bytes(), sha256)
        if extracted["source_bytes_sha256"] != EXPECTED_LOGO_SHA256:
            raise ValueError(f"unexpected header logo: {release_id}")
        if png != existing_png or extracted["png_sha256"] != EXPECTED_PNG_SHA256:
            raise ValueError(f"decoded PNG mismatch: {release_id}")
        evidence_path = origin_evidence_path if index == 0 else Path(f"analysis/{release_id}-header-logo.json")
        write_json(root / evidence_path, release_report(extracted, release, index == 0, png_path))
        outputs.append(evidence_path)
        records.append({
            "id": release_id,
            "language": release["language"],
            "revision": release["revision"],
            "build_kind": release["build_kind"],
            "sha256": sha256,
            "origin_reference": index == 0,
            "source_sha256": extracted["source_bytes_sha256"],
            "png_sha256": extracted["png_sha256"],
            "evidence": evidence_path.as_posix(),
        })

    summary = {
        "schema_version": 1,
        "game": game,
        "asset": "GbaHeaderNintendoLogo",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "source_sha256": EXPECTED_LOGO_SHA256,
        "png": png_path.as_posix(),
        "png_sha256": EXPECTED_PNG_SHA256,
        "releases": records,
        "raw_rom_bytes_included": False,
    }
    summary_path = Path("analysis/header-logo-catalog-summary.json")
    write_json(root / summary_path, summary)
    outputs.append(summary_path)

    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/header-logo-catalog.md")
    (root / research_path).write_text(
        f"# {game} GBA header logo release catalog\n\n"
        f"The existing Japanese extraction is retained as the origin artifact. Every one of "
        f"the {len(records)} cataloged releases ({languages}) has the same 156-byte Nintendo "
        "logo payload at GBA header offset `0x04`. BIOS Huffman and cumulative decoding "
        "reproduces the existing 104x16 logical image and its 4x nearest-neighbor PNG "
        "byte-for-byte.\n\n"
        "Per-release reports link exact ROM identities to the shared payload and rendered "
        "asset. No duplicate PNG and no raw ROM bytes are published.\n",
        encoding="utf-8",
        newline="\n",
    )
    outputs.append(research_path)
    test_path = Path("tests/test_header_logo_catalog.py")
    outputs.append(test_path)
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    manifest = {
        "schema_version": 1,
        "game": game,
        "asset": "GbaHeaderNintendoLogo",
        "origin_reference": releases[0]["id"],
        "release_count": len(records),
        "generator": {
            "repository": "SakuraiTsubaki/Disassembly",
            "tool": "tools/catalog_gba_header_logo.py",
            "tool_sha256": file_hash(Path(__file__)),
            "decoder": "tools/extract_gba_header_logo.py",
            "decoder_sha256": file_hash(Path(__file__).with_name("extract_gba_header_logo.py")),
        },
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    }
    write_json(root / "manifests/header-logo-catalog.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--origin-evidence", type=Path, required=True)
    parser.add_argument("--png", type=Path, default=Path("graphics/header/nintendo-logo-jp.png"))
    parser.add_argument("--game", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.origin_evidence, args.png, args.game)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
