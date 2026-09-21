# Disassembly

Shared infrastructure for evidence-driven, reproducible binary disassembly.

This repository owns the methods, schemas, reusable tools, and cross-target
analysis used by the `SakuraiTsubaki/PocketMonsters-*-Disassembly` projects.
Game-specific evidence and utilities stay in the matching target repository.

## What is ready

- a catalog of all twelve target repositories;
- schemas for project metadata, research records, and analysis manifests;
- local input hashing, Game Boy/Game Boy Advance ROM inspectors, deterministic ROM-bank fingerprinting, and artifact-policy validation tools;
- a repository validator with unit tests;
- GitHub Actions validation and contribution templates;
- documented research, evidence, repository, and artifact boundaries.

## Artifact policy

ROM binaries are the only project artifacts excluded from GitHub. Original,
modified, patched, and rebuilt ROM images must never be committed.

All lawful, storable non-ROM work products are preserved: analysis, collected
research, reports, documentation, README files, scripts, source code, tools,
configuration, logs, manifests, checklists, comparisons, CSV/JSON/YAML,
graphics, sprites, images, palettes, fonts, icons, tiles, converted data,
patches, and verification evidence.

Graphics and sprite work must include actual reviewable PNG output alongside
encoded data and metadata. See [the artifact policy](docs/ARTIFACT_POLICY.md).

## Start here

1. Read [the repository model](docs/REPOSITORY_MODEL.md).
2. Follow [the research method](docs/RESEARCH_METHOD.md).
3. Hash a local input with `python tools/hash_input.py path/to/input`.
4. Create a study from [the template](research/templates/study.md).
5. Validate with `python tools/validate_repository.py .`.
6. Check artifacts with `python tools/verify_artifacts.py .`.
7. Run tests with `python -m unittest discover -s tests -v`.

## Layout

- `projects/` — authoritative catalog of target repositories;
- `schemas/` — machine-readable evidence contracts;
- `research/` — shared methods and cross-target studies;
- `tools/` — deterministic, reusable utilities;
- `analysis/` — reproducible cross-target results;
- `docs/` — governance, method, artifact policy, and roadmap.

This foundation intentionally does not migrate earlier experimental work.
