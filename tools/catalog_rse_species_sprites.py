#!/usr/bin/env python3
"""Discover and extract a species sprite set from RSE ROM tables."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROM_BASE = 0x08000000
ENTRY_SIZE = 8
FRONT_TO_BACK = 0x14A0
BACK_TO_PALETTE = 0x0DC0
LANGUAGE_CODES = {"j": "jp", "e": "en", "d": "de", "f": "fr", "i": "it", "s": "es"}
REFERENCES = {
    "Ruby": ("pret/pokeruby", "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f"),
    "Sapphire": ("pret/pokeruby", "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f"),
    "Emerald": ("pret/pokeemerald", "fe1d8e51b265851676b65885818b1f5f62586135"),
}


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LZ4 = load_tool("extract_gba_lz77_4bpp")
LZPAL = load_tool("extract_gba_lz77_palette")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def rom_index(directory: Path) -> dict[str, Path]:
    result = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() == ".gba":
            result.setdefault(file_hash(path), path)
    return result


def decoded_length(data: bytes, source_offset: int) -> int:
    if not 0 <= source_offset + 4 <= len(data) or data[source_offset] != 0x10:
        return -1
    return int.from_bytes(data[source_offset + 1:source_offset + 4], "little")


def candidate_entries(data: bytes, species: int) -> tuple[list[dict], list[dict]]:
    sprites, palettes = [], []
    for entry_offset in range(0, len(data) - ENTRY_SIZE, 4):
        pointer = int.from_bytes(data[entry_offset:entry_offset + 4], "little")
        source_offset = pointer - ROM_BASE
        table_offset = entry_offset - species * ENTRY_SIZE
        if table_offset < 0:
            continue
        first = int.from_bytes(data[entry_offset + 4:entry_offset + 6], "little")
        second = int.from_bytes(data[entry_offset + 6:entry_offset + 8], "little")
        length = decoded_length(data, source_offset)
        if first == 0x800 and second == species and length == 0x800:
            sprites.append({"entry_offset": entry_offset, "table_offset": table_offset,
                            "source_offset": source_offset, "size": first, "tag": second})
        if first == species and second == 0 and length == 32:
            palettes.append({"entry_offset": entry_offset, "table_offset": table_offset,
                             "source_offset": source_offset, "tag": first})
    return sprites, palettes


def locate_tables(data: bytes, species: int) -> tuple[dict, dict, dict]:
    sprites, palette_candidates = candidate_entries(data, species)
    pairs = [(front, back) for front in sprites for back in sprites
             if back["table_offset"] - front["table_offset"] == FRONT_TO_BACK]
    if len(pairs) != 1:
        raise ValueError(f"expected one front/back species-table pair, found {len(pairs)}")
    front, back = pairs[0]
    palettes = [item for item in palette_candidates
                if item["table_offset"] - back["table_offset"] == BACK_TO_PALETTE]
    if len(palettes) != 1:
        raise ValueError(f"expected one normal species-palette table, found {len(palettes)}")
    return front, back, palettes[0]


def release_prefix(game: str, release: dict) -> tuple[str, str]:
    parts = release["id"].split("-")
    if len(parts) < 2 or parts[1] not in LANGUAGE_CODES:
        raise ValueError(f"unsupported release id: {release['id']}")
    language = LANGUAGE_CODES[parts[1]]
    build = "-debug" if release["build_kind"] == "debug" else ""
    return f"{game.lower()}-{language}-rev{release['revision']}{build}", language


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str,
          species: int, species_name: str) -> dict:
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path(f"src/{species_name}_species_sprite_tables.asm")
    source = (root / source_path).read_text(encoding="utf-8")
    for token in (species_name.upper(), str(species), "CompressedSpriteSheet", "CompressedSpritePalette"):
        if token not in source:
            raise ValueError(f"species-table source is missing token: {token}")
    repository, commit = REFERENCES[game]
    roms = rom_index(rom_dir)
    maps, assets, records = [], [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        front, back, palette = locate_tables(data, species)
        stem, language = release_prefix(game, release)
        suffix = f"rev{release['revision']}" + ("-debug" if release["build_kind"] == "debug" else "") + f"-{language}"
        palette_path = Path(f"graphics/pokemon/{species_name}-{suffix}.pal")
        front_path = Path(f"graphics/pokemon/{species_name}-front-{suffix}.png")
        back_path = Path(f"graphics/pokemon/{species_name}-back-{suffix}.png")
        palette_bytes, palette_report = LZPAL.extract(data, palette["source_offset"], sha256)
        front_png, front_report = LZ4.extract(data, front["source_offset"], 8, sha256, palette_bytes)
        back_png, back_report = LZ4.extract(data, back["source_offset"], 8, sha256, palette_bytes)
        for path, payload in ((palette_path, palette_bytes), (front_path, front_png), (back_path, back_png)):
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_bytes(payload)
            assets.append(path)
        evidence = {
            "schema_version": 1, "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0, "species": {"id": species, "name": species_name},
            "discovery": {"front_to_back_table_delta": FRONT_TO_BACK,
                          "back_to_palette_table_delta": BACK_TO_PALETTE,
                          "front": front, "back": back, "palette": palette},
            "outputs": [
                {"path": front_path.as_posix(), "sha256": digest(front_png), "extraction": front_report},
                {"path": back_path.as_posix(), "sha256": digest(back_png), "extraction": back_report},
                {"path": palette_path.as_posix(), "sha256": digest(palette_bytes), "extraction": palette_report},
            ],
            "naming_basis": {"repository": repository, "commit": commit,
                             "paths": ["src/data/pokemon_graphics/front_pic_table.h",
                                       "src/data/pokemon_graphics/back_pic_table.h",
                                       "src/data/pokemon_graphics/palette_table.h"]},
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{stem}-{species_name}-sprite-set.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": release_id, "language": release["language"],
                        "revision": release["revision"], "build_kind": release["build_kind"],
                        "sha256": sha256, "origin_reference": index == 0,
                        "evidence": map_path.as_posix(), "front": front_path.as_posix(),
                        "back": back_path.as_posix(), "palette": palette_path.as_posix()})

    summary = {"schema_version": 1, "game": game,
               "species": {"id": species, "name": species_name},
               "origin_reference": releases[0]["id"], "release_count": len(records),
               "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path(f"analysis/{species_name}-sprite-set-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path(f"research/{species_name}-sprite-set.md")
    (root / research_path).write_text(
        f"# {game} {species_name.title()} sprite set\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. Across all {len(records)} "
        f"cataloged releases ({languages}), a unique front/back pair is selected by the "
        f"`0x{FRONT_TO_BACK:X}` table delta and its normal palette by the `0x{BACK_TO_PALETTE:X}` "
        "delta. LZ77 compressed, decoded, and output hashes are retained without ROM bytes.\n",
        encoding="utf-8", newline="\n")
    test_path = Path(f"tests/test_{species_name}_sprite_set.py")
    outputs = [catalog_path, source_path, summary_path, *maps, *assets, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / f"manifests/{species_name}-sprite-set.json", {
        "schema_version": 1, "game": game, "species": {"id": species, "name": species_name},
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_rse_species_sprites.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--game", choices=sorted(REFERENCES), required=True)
    parser.add_argument("--species", type=int, required=True)
    parser.add_argument("--species-name", required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.species, args.species_name)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
