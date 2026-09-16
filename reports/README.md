# Reports

This directory contains human-readable research output produced from disassembly, comparison, and verification work.

## Sections

- `analysis/` — findings, classifications, recovered structures, unresolved questions.
- `comparison/` — target/revision/tool/output comparisons.
- `verification/` — reproducible verification summaries and evidence.

## Report header

Use this metadata block near the top of substantial reports:

```yaml
status: draft | reviewed | verified
target: <TARGET>
date: YYYY-MM-DD
sources:
  - source identifier or public URL
tools:
  - tool and version
verification:
  - method or criterion
```

## Writing rules

- State what was observed before stating what it implies.
- Keep hypotheses visibly marked.
- Link source records and manifests when available.
- Include exact tool versions when output may vary by version.
- Put machine-readable data in `manifests/`, `schemas/`, or target data directories and link it from the report rather than duplicating large datasets in prose.

## Publishing

The repository Pages portal in `site/` provides an entry point for reports. Reports remain version-controlled here as the source of truth.
