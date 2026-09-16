#!/usr/bin/env python3
"""Print identity metadata for a local binary without copying its contents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> dict[str, object]:
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            size += len(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
    return {
        "path": path.name,
        "size": size,
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    if not args.path.is_file():
        parser.error(f"not a file: {args.path}")
    print(json.dumps(hash_file(args.path), indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
