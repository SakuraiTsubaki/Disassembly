# Contributing

## Before opening a change

- Keep cross-target work here and target-specific work in its target repository.
- Do not commit ROMs or other proprietary binary inputs.
- Record hashes rather than redistributing inputs.
- Separate observed facts from hypotheses and label confidence.
- Make tools deterministic and document their input and output contracts.

## Required checks

```sh
python tools/validate_repository.py .
python -m unittest discover -s tests -v
python -m compileall -q tools tests
```

A pull request must explain its evidence, reproduction commands, affected
targets, and known limitations. Choosing a repository license remains an owner
decision and is deliberately outside this foundation change.
