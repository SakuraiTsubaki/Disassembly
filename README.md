# Disassembly

Shared infrastructure for evidence-driven, reproducible binary disassembly.

This repository owns the methods, schemas, reusable tools, and cross-target
analysis used by the `SakuraiTsubaki/PocketMonsters-*-Disassembly` projects.
Game-specific evidence and utilities stay in the matching target repository.

## What is ready

- a catalog of all twelve target repositories;
- schemas for project metadata, research records, and analysis manifests;
- a local input hashing tool that never copies ROM contents;
- a repository validator with unit tests;
- GitHub Actions validation and contribution templates;
- documented research, evidence, and repository boundaries.

## Start here

1. Read [the repository model](docs/REPOSITORY_MODEL.md).
2. Follow [the research method](docs/RESEARCH_METHOD.md).
3. Hash a local input with `python tools/hash_input.py path/to/input`.
4. Create a study from [the template](research/templates/study.md).
5. Validate the repository with `python tools/validate_repository.py .`.
6. Run tests with `python -m unittest discover -s tests -v`.

## Layout

- `projects/` — authoritative catalog of target repositories;
- `schemas/` — machine-readable evidence contracts;
- `research/` — shared methods and cross-target studies;
- `tools/` — deterministic, reusable utilities;
- `analysis/` — reproducible cross-target results;
- `docs/` — governance, method, and roadmap.

## Boundaries

ROM images, firmware, keys, saves, emulator states, proprietary SDKs, and
generated proprietary binaries are not committed. Store only lawful source,
metadata, hashes, procedures, and independently created analysis.

This foundation intentionally does not migrate earlier experimental work.
