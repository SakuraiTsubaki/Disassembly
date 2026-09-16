# Toolchains

This directory contains reproducible installation, configuration, and version-tracking material for tools used by disassembly targets.

## Matrix

| Tool | Role | Typical use | Version policy |
| --- | --- | --- | --- |
| `rgbds/` | Game Boy / Game Boy Color assembler toolchain | Assemble, link, inspect RGBDS-based targets | Pin per target when behavior matters |
| `binutils/` | GNU binary utilities | Object inspection, disassembly, linking utilities | Record exact package/tool version |
| `llvm/` | LLVM binary/compiler utilities | Disassembly, object inspection, architecture tooling | Record exact major/minor version |
| `ghidra/` | Static reverse-engineering suite | Function/data analysis, cross-references, structures | Record release/build used for analysis |
| `radare2/` | Scriptable binary-analysis suite | CLI analysis, automation, comparison | Record exact release/commit when relevant |

## Rules

1. Tool setup must be reproducible from repository-tracked instructions or scripts.
2. Version-sensitive results must identify the exact tool version that produced them.
3. Target-specific overrides belong with the target configuration when they are not globally applicable.
4. Do not vendor third-party binaries unless redistribution terms are explicitly compatible.
5. Prefer checksums for downloaded archives and installers when automated setup is added.

## Target manifests

When a target depends on a particular tool version, record that dependency in `manifests/tools/` and reference it from the target README.

## Status

The toolchain directories currently define the repository slots and documentation model. Installation automation can be added incrementally without changing the top-level layout.
