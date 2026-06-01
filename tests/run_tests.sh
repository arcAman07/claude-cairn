#!/usr/bin/env bash
# Run the full Cairn unit suite. Tests are stdlib-only (no pytest needed).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
echo "Running Cairn unit tests (python3 -m unittest)…"
python3 -m unittest discover -s "$HERE" -p "test_*.py" -v
