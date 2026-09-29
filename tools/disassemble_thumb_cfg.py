#!/usr/bin/env python3
"""Build a byte-exact conservative Thumb-1 reachable disassembly from a ROM."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

ROM_BASE = 0x08000000


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def trace(data: bytes, start_offset: int, max_span: int = 0x4000) -> dict:
    if start_offset < 0 or start_offset % 2:
        raise ValueError("start offset must be nonnegative and halfword-aligned")
    limit = min(len(data), start_offset + max_span)
    queue = [start_offset]
    visited: set[int] = set()
    instructions: dict[int, dict] = {}
    edges, calls, returns = [], [], []

    def add_edge(source: int, target: int, kind: str) -> None:
        if not start_offset <= target < limit or target % 2:
            raise ValueError(f"{kind} target leaves disassembly scan window")
        edges.append({"source": ROM_BASE + source, "target": ROM_BASE + target, "kind": kind})
        queue.append(target)

    while queue:
        offset = queue.pop()
        while offset not in visited:
            if offset == limit:
                break
            if not start_offset <= offset <= limit - 2:
                raise ValueError("control flow leaves disassembly scan window")
            visited.add(offset)
            raw = data[offset:offset + 2]
            halfword = struct.unpack("<H", raw)[0]
            address = ROM_BASE + offset
            item = {"address": address, "source_offset": offset, "halfword": halfword, "bytes_le": raw.hex(), "kind": "other"}
            instructions[offset] = item
            if halfword & 0xFF00 == 0xBD00 or halfword == 0x4770:
                item["kind"] = "return"
                returns.append(address)
                break
            if halfword & 0xF800 == 0xF000:
                if offset + 4 > len(data):
                    raise ValueError("truncated Thumb BL")
                suffix_raw = data[offset + 2:offset + 4]
                suffix = struct.unpack("<H", suffix_raw)[0]
                if suffix & 0xF800 != 0xF800:
                    raise ValueError("unsupported Thumb long-branch prefix")
                visited.add(offset + 2)
                instructions[offset + 2] = {"address": address + 2, "source_offset": offset + 2, "halfword": suffix, "bytes_le": suffix_raw.hex(), "kind": "bl-suffix"}
                delta = sign_extend(((halfword & 0x7FF) << 12) | ((suffix & 0x7FF) << 1), 23)
                target = address + 4 + delta
                item.update({"kind": "call", "target": target})
                calls.append({"source": address, "target": target})
                offset += 4
                continue
            if halfword & 0xF800 == 0xE000:
                target = offset + 4 + (sign_extend(halfword & 0x7FF, 11) << 1)
                item.update({"kind": "branch", "target": ROM_BASE + target})
                add_edge(offset, target, "branch")
                break
            if halfword & 0xF000 == 0xD000 and halfword & 0x0F00 != 0x0F00:
                target = offset + 4 + (sign_extend(halfword & 0xFF, 8) << 1)
                item.update({"kind": "conditional-branch", "target": ROM_BASE + target})
                add_edge(offset, target, "conditional-taken")
                edges.append({"source": address, "target": address + 2, "kind": "conditional-fallthrough"})
                offset += 2
                continue
            offset += 2
    ordered = [instructions[index] for index in sorted(instructions)]
    canonical = b"".join(bytes.fromhex(item["bytes_le"]) for item in ordered)
    return {
        "schema_version": 1,
        "rom_base": ROM_BASE,
        "start_offset": start_offset,
        "start_address": ROM_BASE + start_offset,
        "scan_limit_address": ROM_BASE + limit,
        "instruction_halfwords": len(ordered),
        "canonical_instruction_bytes_sha256": hashlib.sha256(canonical).hexdigest(),
        "range_start": ordered[0]["address"],
        "range_end": ordered[-1]["address"] + 2,
        "return_observed": bool(returns),
        "instructions": ordered,
        "edges": edges,
        "calls": calls,
        "returns": sorted(returns),
    }


def analyze(data: bytes, start_offset: int, expected_sha256: str | None = None, max_span: int = 0x4000) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError("ROM SHA-256 mismatch")
    result = trace(data, start_offset, max_span)
    result.update({"source_size": len(data), "source_sha256": digest})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--start-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--max-span", type=lambda value: int(value, 0), default=0x4000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = analyze(args.rom.read_bytes(), args.start_offset, args.expected_sha256, args.max_span)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
