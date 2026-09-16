# Disassembly

Shared research, tooling, and analysis for reproducible binary disassembly.

This repository is the common, target-neutral workspace for the
`SakuraiTsubaki/PocketMonsters-*-Disassembly` projects. Target-specific source,
assets, manifests, and findings belong in their respective repositories.

## Scope

- document reusable disassembly methods and evidence standards;
- develop deterministic tools that apply to more than one target;
- publish cross-target analysis that can be reproduced from documented inputs.

## Layout

- [`research/`](research/) — methods, references, and research notes;
- [`tools/`](tools/) — reusable scripts and utilities;
- [`analysis/`](analysis/) — reproducible cross-target results.

## Ground rules

- Do not commit ROM images, firmware, keys, save data, or other copyrighted
  binary inputs.
- Record input identity with hashes and release metadata; keep the inputs local.
- Prefer deterministic commands and machine-readable outputs.
- Keep target-specific work in the matching target repository.

This is a clean foundation. No previous experimental work was migrated.
