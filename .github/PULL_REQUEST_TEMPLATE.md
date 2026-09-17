## Scope

Which shared method, schema, tool, artifact, or cross-target analysis changes?

## Evidence and reproduction

List ROM inputs by hash only. Include exact commands, tool versions, and expected
outputs. Commit all lawful non-ROM results needed to inspect or reproduce the
work.

## Verification

- [ ] `python tools/validate_repository.py .`
- [ ] `python tools/verify_artifacts.py .`
- [ ] `python -m unittest discover -s tests -v`
- [ ] No original, modified, patched, rebuilt, renamed, or archived ROM was added
- [ ] Useful non-ROM results are committed rather than represented only by hashes
- [ ] Graphics or sprite work includes actual PNG output
- [ ] Target-specific work remains in its target repository
