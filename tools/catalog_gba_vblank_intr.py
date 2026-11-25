#!/usr/bin/env python3
"""Disassemble VBlankIntr across Generation III release catalogs."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import disassemble_thumb_cfg

ROM_BASE = 0x08000000
INTR_CHECK = 0x03007FF8
REG_IME = 0x04000208
REG_VCOUNT = 0x04000006
PROFILES = {
    "rs": {"length": 98, "calls": ("LinkVSync", "m4aSoundVSync", "CallVBlankCallback", "m4aSoundMain", "sub_800C35C", "Random"), "repository": "pret/pokeruby", "commit": "5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f"},
    "emerald": {"length": 164, "calls": ("RfuVSync", "LinkVSync", "CallVBlankCallback", "CopyBufferedValuesToGpuRegs", "ProcessDma3Requests", "m4aSoundMain", "TryReceiveLinkBattleData", "Random", "UpdateWirelessStatusIndicatorSprite"), "repository": "pret/pokeemerald", "commit": "fe1d8e51b265851676b65885818b1f5f62586135"},
    "frlg": {"length": 132, "calls": ("RfuVSync", "LinkVSync", "CallVBlankCallback", "CopyBufferedValuesToGpuRegs", "ProcessDma3Requests", "m4aSoundMain", "TryReceiveLinkBattleData", "Random", "UpdateWirelessStatusIndicatorSprite"), "repository": "pret/pokefirered", "commit": "037335f4c725d7c9aecdac87066f2002b4bd7e14"},
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def rom_index(directory: Path) -> dict[str, Path]:
    result = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() == ".gba":
            result.setdefault(file_hash(path), path)
    return result


def source_text(profile: str) -> str:
    common = '''.syntax unified
.thumb

.global VBlankIntr
.type VBlankIntr, %function
VBlankIntr:
    @ Synchronize link/wireless state according to the release profile.
    @ Advance the verified gMain VBlank counters and invoke its callback.
    @ Flush buffered video/DMA state where present, service sound/link data,
    @ advance RNG under the profile guard, then set bit 0 in both interrupt flags.
'''
    bodies = {
        "rs": '''    bl LinkVSync
    bl m4aSoundVSync
    bl CallVBlankCallback
    bl m4aSoundMain
    bl sub_800C35C
    bl Random
''',
        "emerald": '''    bl RfuVSync
    bl LinkVSync
    bl CallVBlankCallback
    bl CopyBufferedValuesToGpuRegs
    bl ProcessDma3Requests
    bl m4aSoundMain
    bl TryReceiveLinkBattleData
    bl Random
    bl UpdateWirelessStatusIndicatorSprite
''',
        "frlg": '''    bl RfuVSync
    bl LinkVSync
    bl CallVBlankCallback
    bl CopyBufferedValuesToGpuRegs
    bl ProcessDma3Requests
    bl m4aSoundMain
    bl TryReceiveLinkBattleData
    bl Random
    bl UpdateWirelessStatusIndicatorSprite
''',
    }
    return common + bodies[profile] + '''    bx lr
.size VBlankIntr, . - VBlankIntr
'''


def dependency_start(root: Path, release_id: str, sha256: str, profile: str) -> tuple[int, Path, str]:
    path = Path(f"analysis/{release_id}-interrupt-init-disassembly.json")
    mapping = json.loads((root / path).read_text(encoding="utf-8"))
    if mapping["target"] != {"release": release_id, "sha256": sha256} or mapping["profile"] != profile:
        raise ValueError(f"interrupt-init dependency mismatch: {release_id}")
    setters = [item for item in mapping["functions"] if item["name"] == "SetSerialCallback"]
    if len(setters) != 1:
        raise ValueError(f"missing SetSerialCallback dependency: {release_id}")
    return int(setters[0]["address"], 16) - ROM_BASE + 12, path, file_hash(root / path)


def literals(data: bytes, offset: int, profile: str) -> tuple[dict[str, str], dict[str, object]]:
    if profile == "rs":
        names = ("gLinkVSyncDisabled", "REG_IME", "gMain", "gPcmDmaCounter", "gSoundInfo", "INTR_CHECK")
        values = struct.unpack_from("<6I", data, offset + 100)
        if values[1] != REG_IME or values[5] != INTR_CHECK:
            raise ValueError("Ruby/Sapphire fixed literal mismatch")
        behavior = {"ime_guarded_sound_vsync": True}
    elif profile == "emerald":
        names = ("gWirelessCommType", "gLinkVSyncDisabled", "gMain", "gTrainerHillVBlankCounter", "gPcmDmaCounter", "gSoundInfo", "inBattleOffset", "gBattleTypeFlags", "battleRngSuppressMask", "INTR_CHECK")
        values = (struct.unpack_from("<I", data, offset + 16)[0],) + struct.unpack_from("<9I", data, offset + 164)
        if values[6] != 0x439 or values[8] != 0x013F0102 or values[9] != INTR_CHECK:
            raise ValueError("Emerald fixed literal mismatch")
        behavior = {"trainer_hill_counter": True, "battle_rng_suppress_mask": "0x013F0102"}
    else:
        names = ("gWirelessCommType", "gLinkVSyncDisabled", "gMain", "gPcmDmaCounter", "gSoundInfo", "sVcountBeforeSound", "REG_VCOUNT", "sVcountAfterSound", "INTR_CHECK")
        values = (struct.unpack_from("<I", data, offset + 16)[0],) + struct.unpack_from("<8I", data, offset + 132)
        if values[6] != REG_VCOUNT or values[8] != INTR_CHECK:
            raise ValueError("FireRed/LeafGreen fixed literal mismatch")
        behavior = {"sound_vcount_samples": True}
    return dict(zip(names, (f"0x{value:08X}" for value in values))), behavior


def build(root: Path, rom_dir: Path, catalog_path: Path, game: str, profile: str) -> dict:
    spec = PROFILES[profile]
    catalog = json.loads((root / catalog_path).read_text(encoding="utf-8"))
    releases = catalog["releases"]
    if not releases or releases[0]["language"] != "Japanese":
        raise ValueError("catalog must begin with the Japanese origin release")
    source_path = Path("src/vblank_intr.s")
    (root / source_path).write_text(source_text(profile), encoding="utf-8", newline="\n")
    source_sha256 = file_hash(root / source_path)
    roms, maps, records = rom_index(rom_dir), [], []
    for index, release in enumerate(releases):
        release_id, sha256 = release["id"], release["sha256"]
        if sha256 not in roms:
            raise ValueError(f"missing catalog ROM: {release_id}")
        data = roms[sha256].read_bytes()
        offset, dependency, dependency_sha256 = dependency_start(root, release_id, sha256, profile)
        length = spec["length"]
        cfg = disassemble_thumb_cfg.trace(data, offset, max_span=length)
        calls = sorted(cfg["calls"], key=lambda item: item["source"])
        if cfg["range_end"] != ROM_BASE + offset + length or len(cfg["returns"]) != 1 or len(calls) != len(spec["calls"]):
            raise ValueError(f"VBlankIntr CFG mismatch: {release_id}")
        named_calls = [{"name": name, "source": f"0x{call['source']:08X}", "target": f"0x{call['target']:08X}"} for name, call in zip(spec["calls"], calls)]
        literal_addresses, behavior = literals(data, offset, profile)
        map_path = Path(f"analysis/{release_id}-vblank-intr-disassembly.json")
        evidence = {"schema_version": 1, "axis": "Disassembly", "target": {"release": release_id, "sha256": sha256}, "profile": profile, "origin_reference": index == 0, "source": source_path.as_posix(), "source_sha256": source_sha256, "function": {"name": "VBlankIntr", "address": f"0x{ROM_BASE + offset:08X}", "range_end_exclusive": f"0x{ROM_BASE + offset + length:08X}", "rom_code_range": {"start_offset": offset, "end_offset_exclusive": offset + length, "length": length, "sha256": digest(data[offset:offset + length]), "raw_bytes_published": False}, "control_flow": {"instruction_halfwords": cfg["instruction_halfwords"], "edge_count": len(cfg["edges"]), "return_count": len(cfg["returns"]), "call_count": len(calls), "canonical_instruction_bytes_sha256": cfg["canonical_instruction_bytes_sha256"], "raw_halfwords_omitted": True}}, "calls": named_calls, "literal_addresses": literal_addresses, "behavior": behavior, "interrupt_flag": "0x0001", "evidence_dependency": {"path": dependency.as_posix(), "sha256": dependency_sha256}, "naming_basis": {"repository": spec["repository"], "commit": spec["commit"], "path": "src/main.c", "match_kind": "independent Thumb CFG, call order, literals and state offsets"}, "raw_rom_bytes_included": False}
        write_json(root / map_path, evidence)
        maps.append(map_path)
        records.append({"id": release_id, "language": release["language"], "revision": release["revision"], "build_kind": release["build_kind"], "sha256": sha256, "origin_reference": index == 0, "address": evidence["function"]["address"], "code_sha256": evidence["function"]["rom_code_range"]["sha256"], "evidence": map_path.as_posix()})
    summary = {"schema_version": 1, "axis": "Disassembly", "game": game, "function": "VBlankIntr", "profile": profile, "origin_reference": releases[0]["id"], "release_count": len(records), "source": source_path.as_posix(), "releases": records, "raw_rom_bytes_included": False}
    summary_path = Path("analysis/vblank-intr-disassembly-summary.json")
    write_json(root / summary_path, summary)
    languages = ", ".join(dict.fromkeys(item["language"] for item in records))
    research_path = Path("research/vblank-intr-disassembly.md")
    (root / research_path).write_text(f"# {game} VBlankIntr disassembly\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) match the `{profile}` VBlank profile. Per-release evidence records verified boundaries, calls, literals, behavior and the interrupt-initialization dependency without ROM bytes or instruction dumps.\n", encoding="utf-8", newline="\n")
    test_path = Path("tests/test_vblank_intr_disassembly.py")
    outputs = [catalog_path, source_path, summary_path, *maps, research_path, test_path]
    missing = [path.as_posix() for path in outputs if not (root / path).is_file()]
    if missing:
        raise ValueError("missing output(s): " + ", ".join(missing))
    write_json(root / "manifests/vblank-intr-disassembly.json", {"schema_version": 1, "axis": "Disassembly", "game": game, "profile": profile, "origin_reference": releases[0]["id"], "release_count": len(records), "generator": {"repository": "SakuraiTsubaki/Disassembly", "tool": "tools/catalog_gba_vblank_intr.py", "tool_sha256": file_hash(Path(__file__))}, "outputs": [{"path": path.as_posix(), "sha256": file_hash(root / path)} for path in outputs], "raw_rom_bytes_included": False})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    args = parser.parse_args()
    try:
        build(args.root, args.rom_dir, args.catalog, args.game, args.profile)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
