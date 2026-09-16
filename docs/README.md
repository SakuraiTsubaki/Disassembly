# Documentation

Technical documentation for the `Disassembly` repository is organized by purpose rather than by target.

## Navigation

| Section | Purpose |
| --- | --- |
| `methodology/` | End-to-end workflow, reverse-engineering practice, naming, verification |
| `architectures/` | CPU/ISA/platform architecture notes |
| `file-formats/` | Binary and container format research |
| `memory-maps/` | Address spaces, banks, sections, and memory-layout research |
| `references/` | Public sources and provenance records |
| `WORKFLOW.md` | Repository-wide process diagram and stage gates |
| `STYLE_GUIDE.md` | Writing, status, evidence, and formatting conventions |

## Principle

Shared knowledge belongs here. Target-specific findings belong under `targets/<TARGET>/` unless they are generalized into reusable documentation.

## Evidence flow

A typical research result should be traceable from public reference → analysis → reconstructed artifact → comparison/verification → report/manifests.
