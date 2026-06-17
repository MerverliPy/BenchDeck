#!/usr/bin/env bash
set -euo pipefail

# tui_iterate.sh — continuous edit-test loop for TUI changes.
# Runs ruff → mypy → targeted tests → headless render.
# Exits 0 on success. On failure, preserves output for inspection.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PASS=true
FIXTURE="${1:-fixtures/original_run.zip}"

echo "=== [1/4] ruff check ==="
python -m ruff check src/benchdeck/tui/ --quiet || { echo "FAILED"; PASS=false; }

echo "=== [2/4] mypy ==="
python -m mypy src/benchdeck/tui/ --no-error-summary 2>&1 | tail -5 || { echo "FAILED"; PASS=false; }

echo "=== [3/4] pytest (TUI unit tests) ==="
python -m pytest -q -p no:cacheprovider tests/test_tui_loading.py tests/test_tui_render.py --tb=short 2>&1 || { echo "FAILED"; PASS=false; }

echo "=== [4/4] headless render ==="
if python -m benchdeck tui --headless "$FIXTURE" > /dev/null 2>&1; then
    echo "Render OK"
else
    echo "FAILED: headless render crashed"
    PASS=false
fi

if $PASS; then
    echo ""
    echo "=== all checks passed ==="
    exit 0
else
    echo ""
    echo "=== some checks FAILED ==="
    exit 1
fi
