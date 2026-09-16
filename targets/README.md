# Targets

`targets/` contains target-specific disassembly workspaces.

## Standard layout

```text
targets/<TARGET>/
├─ README.md
├─ config/
├─ include/
├─ src/
├─ data/
├─ symbols/
├─ maps/
├─ analysis/
├─ references/
├─ tests/
└─ verification/
```

## Registry

| Target | Architecture | Status | Verification | Notes |
| --- | --- | :---: | :---: | --- |
| `_template` | — | ⚪ Template | — | Copy the structure when registering a real target |

## Status model

| Status | Meaning |
| --- | --- |
| ⚪ Planned | Target is registered but analysis has not started |
| 🟡 In Progress | Active disassembly or reconstruction |
| 🟢 Analyzed | Major structures are documented; verification may remain |
| 🔵 Verified | Defined verification criteria are satisfied |
| 🔴 Blocked | A documented dependency or evidence gap prevents progress |

## Registering a target

1. Create `targets/<TARGET>/` using the standard layout.
2. Fill in the target `README.md` with identity, architecture, public sources, tool requirements, and scope.
3. Add the target to the registry above.
4. Record required tool versions in `manifests/tools/` when relevant.
5. Keep raw observations and hypotheses in `analysis/` until they are established enough to become reconstructed source/symbols/data.
6. Define verification criteria before marking the target as verified.

## Target README minimum

Every target README should include:

- target name and identity;
- architecture/platform;
- scope and exclusions;
- public reference sources;
- toolchain requirements;
- current status;
- reconstruction progress;
- verification method;
- unresolved questions.
