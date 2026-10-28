#!/usr/bin/env python3
"""Extract a species sprite set from verified FRLG species tables."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROM_BASE = 0x08000000
ENTRY_SIZE = 8
ANCHOR_SPECIES = 410
LANGUAGE_CODES = {"j": "jp", "e": "en", "d": "de", "f": "fr", "i": "it", "s": "es"}


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


def table_entry(data: bytes, table_offset: int, species: int, sprite: bool) -> dict:
    offset = table_offset + species * ENTRY_SIZE
    if offset < 0 or offset + ENTRY_SIZE > len(data):
        raise ValueError("species table entry is outside the ROM")
    pointer = int.from_bytes(data[offset:offset + 4], "little")
    source_offset = pointer - ROM_BASE
    if not 0 <= source_offset < len(data) or data[source_offset] != 0x10:
        raise ValueError("species table does not point to a GBA LZ77 stream")
    if sprite:
        size = int.from_bytes(data[offset + 4:offset + 6], "little")
        tag = int.from_bytes(data[offset + 6:offset + 8], "little")
        if tag != species or size != 0x800:
            raise ValueError("species sprite entry metadata differs")
        return {"entry_offset": offset, "table_offset": table_offset,
                "source_offset": source_offset, "size": size, "tag": tag}
    tag = int.from_bytes(data[offset + 4:offset + 6], "little")
    padding = int.from_bytes(data[offset + 6:offset + 8], "little")
    if tag != species or padding != 0:
        raise ValueError("species palette entry metadata differs")
    return {"entry_offset": offset, "table_offset": table_offset,
            "source_offset": source_offset, "tag": tag}


def palette_table_offset(data: bytes, anchor_source_offset: int) -> int:
    pointer = (ROM_BASE + anchor_source_offset).to_bytes(4, "little")
    matches = []
    cursor = 0
    while True:
        cursor = data.find(pointer, cursor)
        if cursor < 0:
            break
        if (cursor + ENTRY_SIZE <= len(data)
                and int.from_bytes(data[cursor + 4:cursor + 6], "little") == ANCHOR_SPECIES
                and int.from_bytes(data[cursor + 6:cursor + 8], "little") == 0):
            base = cursor - ANCHOR_SPECIES * ENTRY_SIZE
            if base >= 0:
                matches.append(base)
        cursor += 1
    if len(set(matches)) != 1:
        raise ValueError(f"expected one anchored palette table, found {len(set(matches))}")
    return matches[0]


def prefix(game: str, release_id: str, revision: int) -> tuple[str, str]:
    parts = release_id.split("-")
    if len(parts) < 2 or parts[1] not in LANGUAGE_CODES:
        raise ValueError(f"unsupported release id: {release_id}")
    language = LANGUAGE_CODES[parts[1]]
    return f"{game.lower()}-{language}-rev{revision}", language


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
    roms = rom_index(rom_dir)
    maps, assets, records = [], [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        stem, language = prefix(game, release_id, release["revision"])
        front_anchor_path = Path(f"analysis/{stem}-deoxys-front-table.json")
        back_anchor_path = Path(f"analysis/{stem}-deoxys-back-table.json")
        palette_anchor_path = Path(f"analysis/{stem}-deoxys-palette.json")
        front_anchor = json.loads((root / front_anchor_path).read_text(encoding="utf-8"))
        back_anchor = json.loads((root / back_anchor_path).read_text(encoding="utf-8"))
        palette_anchor = json.loads((root / palette_anchor_path).read_text(encoding="utf-8"))
        for anchor in (front_anchor, back_anchor):
            if anchor["source_sha256"] != sha256 or anchor["species"] != ANCHOR_SPECIES:
                raise ValueError(f"sprite anchor identity differs: {release_id}")
        if palette_anchor["rom_sha256"] != sha256:
            raise ValueError(f"palette anchor identity differs: {release_id}")
        front_base = front_anchor["entries"][0]["table_offset"]
        back_base = back_anchor["entries"][0]["table_offset"]
        palette_base = palette_table_offset(data, palette_anchor["source_offset"])
        front = table_entry(data, front_base, species, True)
        back = table_entry(data, back_base, species, True)
        palette = table_entry(data, palette_base, species, False)

        suffix = f"rev{release['revision']}-{language}"
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
            "schema_version": 1,
            "target": {"release": release_id, "sha256": sha256},
            "origin_reference": index == 0,
            "species": {"id": species, "name": species_name},
            "tables": {"front": front, "back": back, "palette": palette},
            "anchor_evidence": [
                {"path": path.as_posix(), "sha256": file_hash(root / path)}
                for path in (front_anchor_path, back_anchor_path, palette_anchor_path)
            ],
            "outputs": [
                {"path": front_path.as_posix(), "sha256": digest(front_png), "extraction": front_report},
                {"path": back_path.as_posix(), "sha256": digest(back_png), "extraction": back_report},
                {"path": palette_path.as_posix(), "sha256": digest(palette_bytes), "extraction": palette_report},
            ],
            "raw_rom_bytes_included": False,
        }
        map_path = Path(f"analysis/{stem}-{species_name}-sprite-set.json")
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({
            "id": release_id, "language": release["language"],
            "revision": release["revision"], "sha256": sha256,
            "origin_reference": index == 0, "evidence": map_path.as_posix(),
            "front": front_path.as_posix(), "back": back_path.as_posix(),
            "palette": palette_path.as_posix(),
        })

    summary = {
        "schema_version": 1, "game": game, "species": {"id": species, "name": species_name},
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "releases": records, "raw_rom_bytes_included": False,
    }
    summary_path = Path(f"analysis/{species_name}-sprite-set-summary.json")
    write_json(root / summary_path, summary)
    research_path = Path(f"research/{species_name}-sprite-set.md")
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    (root / research_path).write_text(
        f"# {game} {species_name.title()} sprite set\n\n"
        f"`{releases[0]['id']}` is the Japanese origin reference. For all {len(records)} "
        f"cataloged releases ({languages}), the front, back, and palette entries are "
        "resolved from species tables anchored by the already verified Deoxys entry. "
        "Each LZ77 stream is decoded to a rendered PNG or JASC palette with compressed, "
        "decoded, and output hashes; no ROM bytes are published.\n",
        encoding="utf-8", newline="\n",
    )
    test_path = Path(f"tests/test_{species_name}_sprite_set.py")
    outputs = [catalog_path, source_path, summary_path, *maps, *assets, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / f"manifests/{species_name}-sprite-set.json", {
        "schema_version": 1, "game": game, "species": {"id": species, "name": species_name},
        "origin_reference": releases[0]["id"], "release_count": len(records),
        "generator": {"repository": "SakuraiTsubaki/Disassembly",
                      "tool": "tools/catalog_frlg_species_sprites.py",
                      "tool_sha256": file_hash(Path(__file__))},
        "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs],
        "raw_rom_bytes_included": False,
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--game", required=True)
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
