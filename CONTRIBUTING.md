# Contributing to Disassembly

Thanks for improving the research base. Contributions should make the repository easier to reproduce, review, and verify.

## Core principles

- Keep target-specific work under `targets/`.
- Document public sources and provenance.
- Do not commit proprietary ROM images or private source binaries.
- Prefer reproducible scripts over undocumented manual steps.
- Record tool versions when behavior depends on them.
- Keep analysis claims tied to evidence.
- Add or update verification material when reconstructed output changes.
- Preserve a clear distinction between source material, interpretation, reconstruction, and generated output.

## Contribution types

| Type | Typical location |
| --- | --- |
| Target reconstruction | `targets/<TARGET>/` |
| Architecture research | `docs/architectures/` |
| File-format research | `docs/file-formats/` |
| Memory maps | `docs/memory-maps/` |
| Tooling | `toolchains/`, `scripts/` |
| Emulator automation | `emulators/` |
| Schemas | `schemas/` |
| Reports | `reports/` |
| Provenance/checksums | `manifests/` |

## Before committing

1. Explain the purpose of the change.
2. Follow `docs/STYLE_GUIDE.md` and the naming conventions.
3. Keep generated output separate from hand-maintained source where practical.
4. Run the relevant build, test, and verification commands.
5. Update documentation, manifests, checksums, or reports when required.
6. Avoid unrelated formatting churn in technical changes.

## Pull requests

A pull request should answer four questions:

- **What changed?**
- **Why did it change?**
- **How was it verified?**
- **Which sources or tool versions matter?**

Use the pull-request template and keep changes focused enough to review.

## Analysis quality

When a conclusion is not fully verified, mark it clearly as a hypothesis, tentative mapping, or unresolved item. Do not silently promote assumptions into established symbols, structures, or facts.

## Verification

A reconstruction is not considered verified solely because it assembles. Verification should use the strongest reproducible evidence available: deterministic output, hashes, structural comparisons, test vectors, emulator behavior, or documented equivalence criteria.
