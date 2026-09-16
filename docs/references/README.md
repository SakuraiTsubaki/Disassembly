# References & Provenance

This directory documents public references used during disassembly and reverse-engineering research.

## What belongs here

- public repositories and source trees;
- official technical documentation;
- architecture manuals and datasheets;
- file-format documentation;
- public research notes and analyses;
- release notes, changelogs, symbols, maps, or metadata that materially support a conclusion.

## Source record

A source record should capture enough information for another researcher to locate the same material:

```yaml
title: Example Source
author: Example Author
url: https://example.invalid/source
revision: v1.2.3
retrieved: YYYY-MM-DD
supports:
  - description of the claim, mapping, or artifact supported by this source
notes: optional context
```

For Git repositories, prefer a commit SHA, tag, or release over a floating branch when the exact revision matters.

## Evidence levels

- **Primary** — official documentation, original public source, authoritative specification.
- **Secondary** — established analysis, disassembly, decompilation, or technical research derived from primary material.
- **Supporting** — discussions, issue threads, experiments, emulator behavior, or other evidence useful for cross-checking.

The label describes source role, not automatic correctness. Conflicting evidence should be recorded rather than silently resolved.

## Linking analysis to sources

Target analysis should cite the specific source record or canonical public URL supporting a claim. When a conclusion depends on several sources, record all material inputs.

## Binary policy

Do not place proprietary ROM images or private source binaries here. Record identifiers, hashes, version metadata, or public documentation instead when those are sufficient for reproducibility.
