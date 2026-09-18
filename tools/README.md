# Tools

- `hash_input.py` records size, SHA-1, and SHA-256 without copying an input.
- `validate_repository.py` checks the common repository contract.
- `inspect_gb_rom.py` reports SHA-1/SHA-256 and validates Game Boy logo and checksums without retaining ROM bytes.

Tools use the Python standard library so the foundation remains dependency-free.
Target-specific tools stay in the relevant target repository until reusable.
