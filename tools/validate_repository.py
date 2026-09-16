#!/usr/bin/env python3
"""Validate the shared Disassembly repository foundation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_PATHS = (
    "README.md",
    "CONTRIBUTING.md",
    "projects/catalog.json",
    "schemas/project.schema.json",
    "schemas/research-record.schema.json",
    "schemas/analysis-manifest.schema.json",
    "research/README.md",
    "tools/README.md",
    "analysis/README.md",
)
PROJECT_FIELDS = {
    "id", "repository", "title", "platform", "cpu",
    "architecture", "family", "status",
}
ARCHITECTURES = {"gb-sm83", "gba-arm7tdmi"}
STATUSES = {"foundation", "baseline", "analysis", "reconstruction"}


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")

    for path in sorted(root.rglob("*.json")):
        try:
            load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON {path.relative_to(root)}: {exc}")

    catalog_path = root / "projects/catalog.json"
    if not catalog_path.is_file():
        return errors

    catalog = load_json(catalog_path)
    if not isinstance(catalog, dict) or catalog.get("schema_version") != 1:
        errors.append("projects/catalog.json: schema_version must be 1")
        return errors
    projects = catalog.get("projects")
    if not isinstance(projects, list):
        errors.append("projects/catalog.json: projects must be an array")
        return errors
    if len(projects) != 12:
        errors.append(f"projects/catalog.json: expected 12 projects, got {len(projects)}")

    seen_ids: set[str] = set()
    seen_repositories: set[str] = set()
    for index, project in enumerate(projects):
        label = f"projects[{index}]"
        if not isinstance(project, dict):
            errors.append(f"{label}: must be an object")
            continue
        missing = sorted(PROJECT_FIELDS - project.keys())
        if missing:
            errors.append(f"{label}: missing {', '.join(missing)}")
        project_id = project.get("id")
        repository = project.get("repository")
        if project_id in seen_ids:
            errors.append(f"{label}: duplicate id {project_id}")
        if repository in seen_repositories:
            errors.append(f"{label}: duplicate repository {repository}")
        if isinstance(project_id, str):
            seen_ids.add(project_id)
        if isinstance(repository, str):
            seen_repositories.add(repository)
        if project.get("architecture") not in ARCHITECTURES:
            errors.append(f"{label}: unsupported architecture")
        if project.get("status") not in STATUSES:
            errors.append(f"{label}: unsupported status")
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
    print("Repository foundation is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
