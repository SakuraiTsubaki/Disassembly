#!/usr/bin/env python3
"""Materialize a retail GBA release baseline from an observed release catalog."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path


LANGUAGE_CODES = {
    "Japanese": "jp",
    "English": "en",
    "German": "de",
    "French": "fr",
    "Italian": "it",
    "Spanish": "es",
}


def retail_releases(catalog: dict) -> list[dict]:
    releases = [item for item in catalog["releases"] if item.get("build_kind") == "retail"]
    if not releases:
        raise ValueError("catalog has no retail releases")
    return releases


def canonical_id(prefix: str, release: dict) -> str:
    try:
        language = LANGUAGE_CODES[release["language"]]
    except KeyError as exc:
        raise ValueError(f"unsupported language: {release.get('language')}") from exc
    return f"{prefix}-{language}-rev{release['revision']}"


def materialize(catalog: dict, project: dict, existing_report: dict, prefix: str, generated_at: str):
    selected = retail_releases(catalog)
    old_project = {item["id"]: item for item in project.get("releases", [])}
    project_releases = []
    report_releases = []
    for source in selected:
        release_id = canonical_id(prefix, source)
        previous = old_project.get(release_id)
        if previous and previous["sha256"] != source["sha256"]:
            raise ValueError(f"SHA-256 mismatch for existing release {release_id}")
        project_releases.append(
            previous
            or {
                "id": release_id,
                "region": source["market"],
                "language": source["language"],
                "revision": str(source["revision"]),
                "status": "candidate",
                "size": source["size"],
                "sha1": source["sha1"],
                "sha256": source["sha256"],
            }
        )
        report_item = {
            "id": release_id,
            "size": source["size"],
            "sha1": source["sha1"],
            "sha256": source["sha256"],
            "observed_filenames": source.get("observed_filenames", []),
            "header": source["header"],
            "validation": source["validation"],
        }
        report_releases.append(report_item)

    updated_project = dict(project)
    updated_project["releases"] = project_releases
    updated_report = {
        "schema_version": existing_report.get("schema_version", 1),
        "generated_at": generated_at,
        "generator": existing_report["generator"],
        "observed_files": sum(len(item["observed_filenames"]) for item in report_releases),
        "unique_identities": len(report_releases),
        "releases": report_releases,
    }
    return updated_project, updated_report


def csv_text(project: dict, report: dict) -> str:
    report_by_id = {item["id"]: item for item in report["releases"]}
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("id", "region", "language", "revision", "status", "size", "sha1", "sha256", "notes"))
    for release in project["releases"]:
        header = report_by_id[release["id"]]["header"]
        writer.writerow(
            (
                release["id"], release["region"], release["language"], release["revision"],
                release["status"], release["size"], release["sha1"], release["sha256"],
                f"Title {header['title']}; game code {header['game_code']}; checksum 0x{header['header_checksum']:02x}",
            )
        )
    return stream.getvalue()


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    project = json.loads(args.project.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    project, report = materialize(catalog, project, report, args.prefix, args.generated_at)
    report_data = json_bytes(report)
    manifest["inputs"] = [
        {"size": item["size"], "sha256": item["sha256"]} for item in report["releases"]
    ]
    manifest["outputs"] = [
        {"path": args.report.as_posix(), "sha256": hashlib.sha256(report_data).hexdigest()}
    ]
    # Repository-relative output paths are preserved from the existing manifest.
    if json.loads(args.manifest.read_text(encoding="utf-8")).get("outputs"):
        manifest["outputs"][0]["path"] = json.loads(args.manifest.read_text(encoding="utf-8"))["outputs"][0]["path"]

    args.project.write_bytes(json_bytes(project))
    args.report.write_bytes(report_data)
    args.csv.write_text(csv_text(project, report), encoding="utf-8", newline="")
    args.manifest.write_bytes(json_bytes(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

