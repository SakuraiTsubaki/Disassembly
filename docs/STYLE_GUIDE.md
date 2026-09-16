# Documentation Style Guide

The repository should read like one coherent technical project even when many targets and tools are involved.

## Headings

- Use one `#` heading per document.
- Keep section names short and descriptive.
- Prefer stable terminology across targets.

## Technical writing

- Separate observed facts from interpretation.
- Mark uncertain conclusions as **Hypothesis**, **Tentative**, or **Unresolved**.
- Prefer exact identifiers, addresses, versions, hashes, and paths where they are relevant.
- Avoid presenting tool output as a conclusion without explaining what it demonstrates.

## Paths and identifiers

Use backticks for repository paths, symbols, commands, addresses, hashes, filenames, and tool names when used as exact identifiers.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| ⚪ Planned | Registered but not started |
| 🟡 In Progress | Active analysis/reconstruction |
| 🟢 Analyzed | Analysis is documented but final verification may remain |
| 🔵 Verified | Verification criteria are documented and satisfied |
| 🔴 Blocked | Work cannot proceed until a named dependency/evidence gap is resolved |

## Sources

Every source entry should identify, when available:

- title or repository/project name;
- author/organization;
- URL or canonical identifier;
- accessed/retrieved date when useful;
- revision, release, tag, or commit;
- what the source supports.

See `docs/references/README.md` for provenance rules.

## Tables

Use tables for matrices, mappings, status summaries, revision comparisons, and tool/version inventories. Do not use a table when a short paragraph is clearer.

## Diagrams

Prefer Mermaid for architecture and workflow diagrams that benefit from being version-controlled as text.

## Generated material

Generated files must identify the generating script/tool when that relationship is not obvious from the path. Do not manually edit generated output without documenting why.
