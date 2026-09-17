# Contributing

## Preservation rule

Commit every lawful, useful non-ROM work product, including scripts, source,
logs, structured data, patches, graphics, transformed data, reports, and
validation evidence. Do not replace a useful artifact with only a checksum or
description.

ROM images are prohibited whether original, modified, patched, rebuilt, renamed,
or archived. Graphics and sprite work must include a visible PNG result with the
encoded data and metadata.

Credentials, authentication material, editor metadata, caches, and virtual
environments are machine-local and are not work products.

## Research quality

- Keep cross-target work here and target-specific work in its target repository.
- Record hashes rather than redistributing ROM inputs.
- Separate observed facts from hypotheses and label confidence.
- Make tools deterministic and document their input and output contracts.

## Required checks

```sh
python tools/validate_repository.py .
python tools/verify_artifacts.py .
python -m unittest discover -s tests -v
python -m compileall -q tools tests
```

Choosing a repository license remains an owner decision.
