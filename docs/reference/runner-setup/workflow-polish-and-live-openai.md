# Runner setup reference — Phases 6–8 — workflow run, operational polish, and live OpenAI wiring

> Agent context note: this is detailed reference material split out of `docs/runner-setup.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/runner-setup-summary.md` and open this shard only when the specific phase is relevant.

# Phase 6 — First end-to-end workflow run (offline path)

**Marker**: `<!-- phase-6: done -->` (flip to `<!-- phase-6: done -->`)

This validates the entire boundary, including the "Verify controlled runner boundary" step that the existing failures were tripping on.

### Step 6.1 — Trigger the workflow with defaults

<!-- step-6.1: done -->

From **GitHub web UI**:
- Repo → Actions → "BenchDeck Product Test" → "Run workflow"
- Inputs:
  - `python_version`: `3.12` (default)
  - `run_live_openai`: **false** (unchecked, default)
  - `model`: `gpt-4o-mini` (default; ignored when not live)
- Click "Run workflow"

**Verify**: mark `<!-- step-6.1: done -->`.

### Step 6.2 — Watch the run

<!-- step-6.2: done -->

The job should pick up in < 60 s (the runner is already registered and idle). Expected step order:

| # | Step | Expected outcome |
|---|---|---|
| 1 | Checkout exact triggering commit | green |
| 2 | Verify controlled runner boundary | **green** — `docker info` JSON contains "rootless", `jq` found |
| 3 | Create isolated sandbox | green — first run takes ~5-10 min (apt + pip) |
| 4 | Run regression and black-box checks | green — 9 nested calls each exit 0 |
| 5 | Run real PTY smoke validation | green |
| 6 | Archive evidence on controlled runner | green (always runs) |
| 7 | Destroy sandbox | green (always runs) |

Total: 15-25 minutes for the first run (Docker image pull + apt + pip install dominate). Subsequent runs are < 5 minutes because the image is cached.

**Verify**: all 7 steps green. If any fails, the step log will show the exact `docker`/`python` invocation and its output.

**Verify**: mark `<!-- step-6.2: done -->`.

### Step 6.3 — Inspect the archived evidence

<!-- step-6.3: done -->

The workflow's archive step writes to `${RUNNER_TEMP}/benchdeck-product-test-archives/...tar.gz` on the runner host and adds a SHA-256 + a link to the GitHub step summary.

In WSL2, the runner's `_diag` directory has per-job logs. The evidence tarball is under `/home/benchdeck-runner/.cache/...` or wherever the runner's `RUNNER_TEMP` resolves to:
```bash
find /tmp /home/benchdeck-runner -path '*benchdeck-product-test-archives*' -name '*.tar.gz' -mmin -60 2>/dev/null
```

If the archive is missing, the run failed at the archive step — the sandbox state in `/home/benchdeck-runner/.cache/benchdeck-product-test/<repo-hash>/workspaces/<run-id>/` is still there (`.test-evidence/...` and `state.json`).

**Verify**: mark `<!-- step-6.3: done -->`.

---

# Phase 7 — Polish (the "make it last" part)

**Marker**: `<!-- phase-7: done -->` (flip to `<!-- phase-7: done -->`)

Eight items. Each has a check + a 10-minute implementation. All reversible.

### Step 7.1 — Smoke test script

<!-- step-7.1: done -->

The repo already has `scripts/benchdeck-runner-smoke-test.sh` (created alongside this runbook). It does a one-shot check of the full boundary. Run it once now and once a day via cron.

```bash
sudo -u benchdeck-runner -H bash /home/benchdeck-runner/benchdeck-runner/scripts/benchdeck-runner-smoke-test.sh
```

**Expected**: 4 sections all green, exit 0.

**Verify**: mark `<!-- step-7.1: done -->`.

### Step 7.2 — Daily health cron

<!-- step-7.2: done -->

```bash
sudo -iu benchdeck-runner
mkdir -p ~/bin ~/logs
# Wrapper that captures stdout+stderr to a per-day log
cat > ~/bin/benchdeck-runner-daily.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
LOG="$HOME/logs/health-$(date -u +%Y%m%d).log"
{
  echo "=== health run $(date -u +%FT%TZ) ==="
  bash "$HOME/benchdeck-runner/scripts/benchdeck-runner-smoke-test.sh" || true
  echo
  echo "=== docker df ==="
  docker system df
  echo
  echo "=== df / ==="
  df -h / | head -2
  echo
  echo "=== runner service ==="
  systemctl --user is-active "actions.runner.*" || true
} >> "$LOG" 2>&1
# rotate: keep last 14 days
find "$HOME/logs" -name 'health-*.log' -mtime +14 -delete
EOF
chmod +x ~/bin/benchdeck-runner-daily.sh

# Schedule at 04:17 UTC daily (off-peak)
( crontab -l 2>/dev/null | grep -v benchdeck-runner-daily ; echo "17 4 * * * $HOME/bin/benchdeck-runner-daily.sh" ) | crontab -
crontab -l | grep benchdeck-runner
exit
```

**Verify**: mark `<!-- step-7.2: done -->`.

### Step 7.3 — Disk pressure watchdog

<!-- step-7.3: done -->

A second daily cron that prunes Docker build cache and old evidence if the disk is over 80% full. Conservative by design — only prunes what is provably safe.

```bash
sudo -iu benchdeck-runner
cat > ~/bin/benchdeck-runner-disk-watchdog.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
LOG="$HOME/logs/disk-watchdog-$(date -u +%Y%m%d).log"
{
  echo "=== disk watchdog run $(date -u +%FT%TZ) ==="
  USED=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
  echo "disk used: ${USED}%"
  if [ "$USED" -ge 80 ]; then
    echo "pruning docker builder cache (keep last 24h)"
    docker builder prune -af --filter "until=24h" || true
  fi
  if [ "$USED" -ge 90 ]; then
    echo "pruning docker images (untagged + older than 7d)"
    docker image prune -af --filter "until=168h" || true
    echo "deleting .test-evidence/ runs older than 30 days"
    find "$HOME/.cache/benchdeck-product-test" -path '*.test-evidence*' -depth -mtime +30 -type d -exec rm -rf {} + 2>/dev/null || true
  fi
  echo "after prune:"
  df -h / | head -2
  docker system df
} >> "$LOG" 2>&1
EOF
chmod +x ~/bin/benchdeck-runner-disk-watchdog.sh

( crontab -l 2>/dev/null | grep -v disk-watchdog ; echo "47 4 * * * $HOME/bin/benchdeck-runner-disk-watchdog.sh" ) | crontab -
crontab -l | grep disk-watchdog
exit
```

**Verify**: mark `<!-- step-7.3: done -->`.

### Step 7.4 — Evidence archival to Windows host

<!-- step-7.4: done -->

The `.test-evidence/` directory lives inside the WSL2 vhdx; a vhdx corruption would lose all product-test history. Mirror the latest run to a Windows folder so it survives a WSL2 reinstall.

```bash
# Decide on a Windows path. E:\ is usually a separate drive; D:\ is common.
# If you only have C:\, use a folder under it — the goal is "outside the vhdx".
WIN_EVIDENCE='/mnt/e/benchdeck-evidence'      # adjust
mkdir -p "$WIN_EVIDENCE"

sudo -iu benchdeck-runner
cat > ~/bin/benchdeck-runner-archive.sh <<EOF
#!/usr/bin/env bash
set -euo pipefail
WIN_EVIDENCE="$WIN_EVIDENCE"
LOG="\$HOME/logs/archive-\$(date -u +%Y%m%d).log"
{
  echo "=== archive run \$(date -u +%FT%TZ) ==="
  mkdir -p "\$WIN_EVIDENCE"
  for d in "\$HOME/.cache/benchdeck-product-test"/*/workspaces/*/repo/.test-evidence/*/; do
    [ -d "\$d" ] || continue
    runid=\$(basename "\$d")
    # Skip if already mirrored and unchanged
    src_size=\$(du -sb "\$d" 2>/dev/null | cut -f1)
    dst="\$WIN_EVIDENCE/\$runid"
    if [ -f "\$dst/.size" ] && [ "\$(cat "\$dst/.size")" = "\$src_size" ]; then
      continue
    fi
    echo "mirroring \$d -> \$dst"
    rm -rf "\$dst"
    cp -a "\$d" "\$dst"
    echo "\$src_size" > "\$dst/.size"
  done
  # Prune the Windows mirror of runs older than 90 days
  find "\$WIN_EVIDENCE" -mindepth 1 -maxdepth 1 -mtime +90 -exec rm -rf {} +
  echo "Windows mirror now contains: \$(ls "\$WIN_EVIDENCE" | wc -l) runs"
} >> "\$LOG" 2>&1
EOF
chmod +x ~/bin/benchdeck-runner-archive.sh

# Daily at 05:30 UTC
( crontab -l 2>/dev/null | grep -v benchdeck-runner-archive ; echo "30 5 * * * \$HOME/bin/benchdeck-runner-archive.sh" ) | crontab -
crontab -l | grep archive
exit
```

**Verify**: trigger a workflow run, wait 30 min, then `ls -la /mnt/e/benchdeck-evidence/` from WSL2 (or open `E:\benchdeck-evidence\` in Windows Explorer) to confirm the run is mirrored.

**Verify**: mark `<!-- step-7.4: done -->`.

### Step 7.5 — Log rotation for the runner diagnostics

<!-- step-7.5: done -->

The runner writes per-job logs to `~/actions-runner/_diag/`. These grow indefinitely. Add a logrotate rule.

```bash
sudo tee /etc/logrotate.d/benchdeck-runner-diag <<'EOF'
/home/benchdeck-runner/actions-runner/_diag/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
# The runner's own logfile under .service is rotated by journald
# but the job-scoped logs above are not.
```

**Verify**: mark `<!-- step-7.5: done -->`.

### Step 7.6 — Windows Task Scheduler: ensure WSL2 stays alive

<!-- step-7.6: done -->

A small Windows-side task that pings WSL2 every 10 min. This catches the (rare) case where WSL2's init daemon dies and won't come back without a `wsl --shutdown` + restart.

From **Windows PowerShell as Administrator**:
```powershell
$Action  = New-ScheduledTaskAction -Execute 'wsl.exe' -Argument '-d Ubuntu -e bash -c "systemctl is-system-running >/dev/null 2>&1 || sudo /usr/bin/systemctl reboot"'
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings= New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName 'WSL2 Keepalive' -Action $Action -Trigger $Trigger -Settings $Settings -User 'SYSTEM' -RunLevel Highest
```

If `SYSTEM` can't see `wsl.exe` (PATH issue), substitute the full path `C:\Windows\System32\wsl.exe`.

**Verify**: `Get-ScheduledTask -TaskName 'WSL2 Keepalive' | Select State` shows `Ready`.

**Verify**: mark `<!-- step-7.6: done -->`.

### Step 7.7 — Confirm the pointer docs resolve

<!-- step-7.7: done -->

The two pointer files (`RUNNER_SETUP.md` at the repo root, `.product-test/runner-setup.md` at the test-infra location) should each be a single sentence pointing here. This is the only step that lives in the repo, not the host.

```bash
cd /path/to/BenchDeck
cat RUNNER_SETUP.md
cat .product-test/runner-setup.md
# both should be 1-line pointers
```

The pointers are committed alongside this runbook; you do not need to edit them.

**Verify**: mark `<!-- step-7.7: done -->`.

### Step 7.8 — Smoke-test one full end-to-end run post-polish

<!-- step-7.8: done -->

Re-trigger the workflow (`Phase 6.1` steps) to confirm none of the polish steps broke the boundary.

**Verify**: mark `<!-- step-7.8: done -->`.

---

# Phase 8 — Live OpenAI wiring (optional but recommended)

**Marker**: `<!-- phase-8: done -->` (flip to `<!-- phase-8: done -->`)

You said you can add a test key now. This phase wires it up **safely** — dedicated key, spend cap, repo-secret-only, never printed, never logged.

### Step 8.1 — Mint a dedicated test key

<!-- step-8.1: done -->

- Go to https://platform.openai.com/api-keys (use a **dedicated test account**, not your personal)
- Create key: name `benchdeck-product-test-wsl2`
- Set **hard spend cap**: Settings → Limits → Hard limit, $5 is enough for many runs
- Set **monthly budget cap** via billing as a safety net
- **Copy the key now**; OpenAI shows it only once. Store in 1Password / Bitwarden / etc.

**Verify**: mark `<!-- step-8.1: done -->`.

### Step 8.2 — Add the secret to GitHub

<!-- step-8.2: done -->

- Repo → Settings → Secrets and variables → Actions → New repository secret
- Name: **`BENCHDECK_TEST_OPENAI_API_KEY`** (must match exactly what `.github/workflows/benchdeck-product-test.yml` line 117 references)
- Value: paste the dedicated key
- Click "Add secret"

**Verify**: in the actions workflow source, line 117 reads:
```yaml
BENCHDECK_TEST_OPENAI_API_KEY: ${{ secrets.BENCHDECK_TEST_OPENAI_API_KEY }}
```
Confirm the secret name matches. The workflow wraps this in `test -n "${BENCHDECK_TEST_OPENAI_API_KEY:-}"` so an unset secret skips the step rather than failing the whole job.

**Verify**: mark `<!-- step-8.2: done -->`.

### Step 8.3 — Trigger a live run

<!-- step-8.3: done -->

From **GitHub web UI**:
- Actions → "BenchDeck Product Test" → "Run workflow"
- Inputs:
  - `python_version`: `3.12`
  - `run_live_openai`: **true** (ticked)
  - `model`: `gpt-4o-mini`
- Click "Run workflow"

The "Run approved live OpenAI validation" step now runs. Expected wall-clock: 3-8 minutes (depends on API latency and the run's planner/agent/judge latency). The step is budget-bounded:
- `--max-logical-requests 30`
- `--max-http-attempts 45`
- `--max-total-input-tokens 120000`
- `--max-total-output-tokens 30000`
- `--timeout 90`

Even if the API is slow, the run cannot exceed these.

**Verify**: step exits 0 (or a documented `BudgetExhausted` exit code with an evidence record).

**Verify**: mark `<!-- step-8.3: done -->`.

### Step 8.4 — Confirm the key never appears in evidence

<!-- step-8.4: done -->

`sandbox_manager.py` line 23 has a redaction rule `SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{10,}")` and `redact()` is called on every stdout/stderr write. Confirm:

```bash
grep -rE 'sk-[A-Za-z0-9_-]{10,}' .test-evidence/ 2>&1 | head
```

**Expected**: 0 matches, or only the literal `[REDACTED_API_KEY]` placeholder.

**Verify**: mark `<!-- step-8.4: done -->`.

### Step 8.5 — Rotate the key (ongoing)

<!-- step-8.5: done -->

- Set a calendar reminder every 90 days to rotate the dedicated test key
- When the key is rotated, update the GitHub secret — the workflow uses it on the next run automatically
- Old evidence remains in `.test-evidence/` and `E:\benchdeck-evidence\`; consider wiping evidence older than 90 days at the same cadence (already in the disk watchdog from Phase 7.3)

**Verify**: mark `<!-- step-8.5: done -->`.

---
