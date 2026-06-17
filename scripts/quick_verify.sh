#!/usr/bin/env bash
set -euo pipefail

# quick_verify.sh — fast preflight for TUI editor/tester workflow.
# Runs ruff + mypy + targeted TUI tests.  Exits 0 on success, 1 on failure.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== ruff check ==="
python -m ruff check src/benchdeck/ --quiet || { echo "FAILED: ruff check"; exit 1; }

echo "=== mypy ==="
python -m mypy src/benchdeck/ --no-error-summary 2>&1 | tail -5 || { echo "FAILED: mypy"; exit 1; }

echo "=== pytest (TUI) ==="
python -m pytest -q -p no:cacheprovider tests/test_tui_loading.py tests/test_tui_render.py --tb=short 2>&1 | tail -10 || { echo "FAILED: TUI tests"; exit 1; }

echo ""
echo "=== all checks passed ==="
