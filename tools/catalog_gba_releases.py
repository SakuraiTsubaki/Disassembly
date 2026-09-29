#!/usr/bin/env python3
"""Build a reproducible, deduplicated GBA release-identity catalog."""
from __future__ import annotations

import argparse
import importlib.util
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("inspect_gba_rom", HERE / "inspect_gba_rom.py")
_inspect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_inspect)

MARKETS = {
    "J": ("Japan", "Japanese", 0),
    "E": ("USA/Europe", "English", 1),
    "D": ("Germany", "German", 2),
    "F": ("France", "French", 3),
    "I": ("Italy", "Italian", 4),
    "S": ("Spain", "Spanish", 5),
}


def build_catalog(paths: list[Path], game_code_prefix: str) -> dict:
    observed = [_inspect.inspect_file(path) for path in paths]
    mismatches = [item["filename"] for item in observed if not item["header"]["game_code"].startswith(game_code_prefix)]
    if mismatches:
        raise ValueError(f"game-code prefix mismatch: {', '.join(mismatches)}")
    invalid = [item["filename"] for item in observed if not all(
        item["validation"][key] for key in
        ("nintendo_logo_valid", "fixed_value_valid", "reserved_area_valid", "header_checksum_valid")
    )]
    if invalid:
        raise ValueError(f"invalid GBA header: {', '.join(invalid)}")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in observed:
        grouped[item["sha256"]].append(item)

    releases = []
    for group in grouped.values():
        item = group[0]
        code = item["header"]["game_code"]
        market, language, order = MARKETS.get(code[-1], ("Unknown", "Unknown", 99))
        revision = item["header"]["software_version"]
        filenames = sorted(entry["filename"] for entry in group)
        build_kind = "debug" if any("debug" in name.lower() for name in filenames) else "retail"
        releases.append({
            "id": f"{game_code_prefix.lower()}-{code[-1].lower()}-rev{revision}-{build_kind}",
            "market": market,
            "language": language,
            "revision": revision,
            "build_kind": build_kind,
            "size": item["size"],
            "sha1": item["sha1"],
            "sha256": item["sha256"],
            "observed_filenames": filenames,
            "header": item["header"],
            "validation": item["validation"],
            "_sort": (order, revision, build_kind, item["sha256"]),
        })
    releases.sort(key=lambda item: item.pop("_sort"))
    return {
        "schema_version": 1,
        "game_code_prefix": game_code_prefix,
        "observed_files": len(observed),
        "unique_identities": len(releases),
        "language_priority": ["Japanese", "English", "German", "French", "Italian", "Spanish"],
        "releases": releases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-code-prefix", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("roms", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        catalog = build_catalog(args.roms, args.game_code_prefix)
        args.output.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8", newline="\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
