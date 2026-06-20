# Screenshot Evidence Handoff

**Filed by:** screenshot review agent (2026-06-20)
**Branch:** `main`
**Source:** Review of `assets/screenshots/`, `scripts/generate_demo_screens.py`, `scripts/_capture_screens.py`, `README.md:17-39`

---

## Review Summary

| Finding | Severity | Status |
|---------|----------|--------|
| README caption claims live-run source; actual source is synthetic | P3 (docs) | Fix below |
| `*-w80.png` files are byte-identical duplicates of un-suffixed files | P3 (cleanup) | Fix below |
| Compare tab (dual-agent) has no committed screenshots | P4 (coverage) | Deferred |
| Phase 2 feature states (filter, sort, log tail) not represented | P4 (coverage) | Deferred |

---

## Fix 1: Correct README Caption (docs)

**File:** `README.md:39`

**Current (incorrect):**
```
*Captured from a live benchmark run (`gpt-4o-mini`, 8 cases, repository-integrity-agent). Regenerate with `scripts/generate_demo_screens.py --run-dir benchmark_out/<run_id>`.*
```

**Replace with:**
```
*Generated from synthetic demo data (12 cases). Regenerate with `scripts/generate_demo_screens.py --widths 32,80 --format png --font-size 15`.*
```

**Rationale:** The committed screenshots were produced by `generate_demo_screens.py` with its default `_build_demo_snapshot()` synthetic data — 12 cases, no live API calls. The real-run capture script `_capture_screens.py` outputs `*_real.png` which is gitignored. The live-run caption is factually wrong.

**Validation:**
```bash
grep "Generated from synthetic" README.md
```

---

## Fix 2: Remove Byte-Duplicate w80 Files (cleanup)

**Files to remove:**
```
assets/screenshots/overview-w80.png
assets/screenshots/cases-w80.png
assets/screenshots/detail-w80.png
assets/screenshots/help-w80.png
```

**Evidence:** All four files are byte-identical (same MD5) to their un-suffixed counterparts. The README references un-suffixed files only. No code, test, or CI path references the `-w80` suffix.

**Command:**
```bash
git rm assets/screenshots/overview-w80.png assets/screenshots/cases-w80.png \
       assets/screenshots/detail-w80.png assets/screenshots/help-w80.png
```

**Validation:**
```bash
# After removal, un-suffixed files still exist
ls assets/screenshots/overview.png assets/screenshots/cases.png \
   assets/screenshots/detail.png assets/screenshots/help.png
# All README <img> tags still resolve
grep -oP 'assets/screenshots/[^"]+' README.md | while read f; do test -f "$f" || echo "MISSING: $f"; done
```

---

## Fix 3: Regenerate Screenshots from Current Source

**Command:**
```bash
python scripts/generate_demo_screens.py \
    -o assets/screenshots/ \
    --widths 32,80 \
    -f png \
    --font-size 15
```

**Rationale:** The TUI source has changed since screenshots were last generated (ellipsis truncation fix, Phase 1-2 cosmetic changes). The `_offset` behavior in `_case_list` changed at commit `a26a283` (Phase 1 display offset fix). Regenerating ensures screenshots match current render output.

**Expected output files (8):**
```
assets/screenshots/overview.png         # 80-col
assets/screenshots/overview-w32.png     # 32-col
assets/screenshots/cases.png            # 80-col
assets/screenshots/cases-w32.png        # 32-col
assets/screenshots/detail.png           # 80-col
assets/screenshots/detail-w32.png       # 32-col
assets/screenshots/help.png             # 80-col
assets/screenshots/help-w32.png         # 32-col
```

**Validation:**
```bash
ls -la assets/screenshots/*.png | grep -v golden
# 8 files expected (4 un-suffixed + 4 w32), no w80 duplicates
```

---

## Fix 4: Update Golden Baselines

**Command:**
```bash
cp assets/screenshots/overview.png assets/screenshots/golden/overview.png
cp assets/screenshots/cases.png    assets/screenshots/golden/cases.png
cp assets/screenshots/detail.png   assets/screenshots/golden/detail.png
cp assets/screenshots/help.png     assets/screenshots/golden/help.png
```

**Rationale:** Goldens must match the 80-col screenshots. CI visual-regression compares `assets/screenshots/ci/` output against `assets/screenshots/golden/`. If screenshots are regenerated, goldens must be updated in the same commit to keep CI passing.

**Validation:**
```bash
# All 80-col screenshots match their golden copies
for t in overview cases detail help; do
    diff assets/screenshots/$t.png assets/screenshots/golden/$t.png && echo "$t: OK" || echo "$t: MISMATCH"
done
```

---

## Complete Execution Script

```bash
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== Fix 1: Correct README caption ==="
# Manual edit required — see Fix 1 above for replacement text

echo "=== Fix 2: Remove byte-duplicate w80 files ==="
git rm -f assets/screenshots/overview-w80.png 2>/dev/null || rm -f assets/screenshots/overview-w80.png
git rm -f assets/screenshots/cases-w80.png    2>/dev/null || rm -f assets/screenshots/cases-w80.png
git rm -f assets/screenshots/detail-w80.png   2>/dev/null || rm -f assets/screenshots/detail-w80.png
git rm -f assets/screenshots/help-w80.png     2>/dev/null || rm -f assets/screenshots/help-w80.png

echo "=== Fix 3: Regenerate screenshots ==="
python scripts/generate_demo_screens.py \
    -o assets/screenshots/ \
    --widths 32,80 \
    --format png \
    --font-size 15

# Multi-width mode produces suffixed files. Copy 80-col to un-suffixed for README:
for t in overview cases detail help; do
    cp "assets/screenshots/${t}-w80.png" "assets/screenshots/${t}.png"
done
rm -f assets/screenshots/overview-w80.png assets/screenshots/cases-w80.png \
      assets/screenshots/detail-w80.png assets/screenshots/help-w80.png

echo "=== Fix 4: Update golden baselines ==="
mkdir -p assets/screenshots/golden
cp assets/screenshots/overview.png assets/screenshots/golden/overview.png
cp assets/screenshots/cases.png    assets/screenshots/golden/cases.png
cp assets/screenshots/detail.png   assets/screenshots/golden/detail.png
cp assets/screenshots/help.png     assets/screenshots/golden/help.png

echo "=== Validation ==="
# Expected: 8 committed screenshot files (4 un-suffixed + 4 w32), 4 goldens
ls -la assets/screenshots/*.png assets/screenshots/golden/*.png
echo ""
echo "Done. Review git diff before committing."
```

---

## Deferred

| Item | Reason |
|------|--------|
| Compare tab screenshots | Dual-agent mode needs product-story decision before adding to README |
| Phase 2 feature screenshots (filter, sort, log tail) | All default-off; screenshots would advertise hidden behavior |
| Light/github theme screenshots | Cosmetic variant; dark theme covers the primary use case |
| `_capture_screens.py` real-run output | Gitignored by design (`*_real.png`); no committed asset needed |

---

## Approval Gates

| Gate | Status |
|------|--------|
| README caption edit | Requires approval to modify docs |
| Remove `-w80` duplicates | Requires approval to delete tracked files |
| Regenerate screenshots | Requires approval to overwrite committed binary assets |
| Update golden baselines | Must accompany screenshot regeneration to keep CI green |
| Git commit | Requires explicit approval to commit |
