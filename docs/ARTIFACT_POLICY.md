# Artifact preservation policy

## Rule

GitHub stores every lawful, storable non-ROM work product. The only project
artifacts excluded are ROM images, whether original, modified, patched, rebuilt,
or otherwise derived.

Excluded ROM forms include files with `.gb`, `.gbc`, `.gba`, or `.rom`
extensions, ROMs renamed to another extension, and ROMs embedded in archives.
ROMs must stay outside the repository, preferably in an ignored `roms/`
directory.

## Preserve these artifacts

Commit useful work products rather than reducing them to hashes or descriptions:

- research notes, collected references, reports, documentation, and README files;
- scripts, source code, tools, configuration, logs, and checklists;
- manifests, validation evidence, patches, comparisons, and test fixtures;
- CSV, JSON, YAML, tables, maps, symbols, and other structured data;
- extracted or transformed non-ROM data;
- graphics, sprites, images, palettes, fonts, icons, and tiles;
- reproducible build and analysis outputs that are not ROM images.

Binary non-ROM formats, including `.bin`, are allowed when their origin,
purpose, and reproduction method are documented.

## Visible graphics requirement

Graphics and sprite work must include the actual reviewable PNG output in
addition to encoded graphics data and metadata. A palette, manifest, checksum,
or extraction record alone is not a substitute for a visible result. Keep PNGs
close to the related source data and document the command that generated them.

## Non-artifacts

Credentials, authentication material, editor metadata, Python bytecode, and
machine-local virtual environments are not work products and remain ignored.

Every committed artifact must be lawful to store and must not contain a ROM
image under another name or inside an archive.
