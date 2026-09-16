# Repository model

## Shared repository

`SakuraiTsubaki/Disassembly` contains only target-neutral methods, schemas,
tools, and comparisons that benefit more than one target.

## Target repositories

Each `PocketMonsters-*-Disassembly` repository owns its title-specific release
matrix, architecture notes, tools, address maps, symbols, and findings.

## Promotion rule

A target tool may be promoted here after its interface is independent of a
single title, its behavior is tested on at least two targets, and its input and
output contracts are documented.

## Evidence rule

Repository contents must distinguish:

- **observed** — directly measured from an identified input;
- **derived** — reproducibly computed from observations;
- **inferred** — a reasoned interpretation with stated confidence;
- **unknown** — not yet established.

No completeness or byte-exactness claim is made without automated evidence.
