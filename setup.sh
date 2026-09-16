#!/usr/bin/env bash
set -euo pipefail

required=(bash git make python3)
missing=()

for tool in "${required[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    missing+=("$tool")
  fi
done

if ((${#missing[@]})); then
  printf 'Missing required tools: %s\n' "${missing[*]}" >&2
  exit 1
fi

echo "Base Disassembly environment is ready."
echo "Target-specific toolchains should be installed from toolchains/ and documented in manifests/tools/."
