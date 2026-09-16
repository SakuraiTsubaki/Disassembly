# Disassembly

A general-purpose repository for binary disassembly, reverse engineering, code reconstruction, documentation, analysis, and reproducible research workflows.

## Purpose

This repository provides a reusable foundation for disassembly projects. It separates target-specific source reconstruction from tooling, analysis, documentation, manifests, tests, and verification so that research can be reproduced and reviewed consistently.

## Repository layout

- `docs/` — methodology, architecture notes, file-format research, memory maps, and references.
- `toolchains/` — reproducible toolchain setup and configuration.
- `emulators/` — emulator configuration and automation used for verification.
- `scripts/` — setup, disassembly, analysis, comparison, verification, and utility scripts.
- `targets/` — target-specific disassembly workspaces.
- `schemas/` — machine-readable schemas for symbols, manifests, and reports.
- `tests/` — shared unit, integration, and regression tests.
- `reports/` — generated or curated analysis, comparison, and verification reports.
- `manifests/` — source provenance, tool versions, and checksum records.
- `.github/` — continuous integration and repository automation.

## Workflow

1. Identify and document the target and public reference material.
2. Configure the required architecture and toolchain.
3. Disassemble and classify code/data regions.
4. Reconstruct labels, symbols, structures, and source organization.
5. Compare reconstructed outputs against documented reference hashes or other reproducible criteria.
6. Record analysis, provenance, tool versions, and verification results.

## Binary policy

Original proprietary binaries and ROM images are not stored in this repository. Publicly distributable source code, scripts, configuration, documentation, metadata, manifests, checksums, and research outputs may be tracked.

## Status

Initial repository framework.
