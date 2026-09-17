#!/usr/bin/env python3
"""Reject ROM images and require PNG previews for encoded graphics work."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROM_SUFFIXES = {".gb", ".gbc", ".gba", ".rom"}
ROM_DIRECTORY_NAMES = {"rom", "roms"}
GRAPHIC_DATA_SUFFIXES = {".2bpp", ".4bpp", ".chr", ".tile", ".tiles"}
SKIP_DIRECTORIES = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def is_rom_path(path: Path) -> bool:
    return path.suffix.lower() in ROM_SUFFIXES or any(
        part.lower() in ROM_DIRECTORY_NAMES for part in path.parts
    )


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    graphics_directories: set[Path] = set()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in SKIP_DIRECTORIES for part in relative.parts):
            continue
        if not path.is_file():
            continue
        if is_rom_path(relative):
            errors.append(f"ROM image is not allowed: {relative.as_posix()}")
        if path.suffix.lower() in GRAPHIC_DATA_SUFFIXES:
            graphics_directories.add(path.parent)
        if path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    for member in archive.namelist():
                        if is_rom_path(Path(member)):
                            errors.append(
                                f"ROM image in archive {relative.as_posix()}: {member}"
                            )
            except zipfile.BadZipFile:
                errors.append(f"invalid ZIP archive: {relative.as_posix()}")
    for directory in sorted(graphics_directories):
        if not any(path.suffix.lower() == ".png" for path in directory.glob("*") if path.is_file()):
            errors.append(
                "encoded graphics require a PNG preview in the same directory: "
                f"{directory.relative_to(root).as_posix()}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("."))
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Artifact policy is satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
