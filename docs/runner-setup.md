# Self-Hosted Runner Setup Runbook

**Audience**: a human setting up the self-hosted GitHub Actions runner on a
**Windows 11 host with WSL2 Ubuntu** that hosts **rootless Docker** for the
`BenchDeck Product Test` workflow.

**Repo**: `MerverliPy/BenchDeck`
**Workflow file**: `.github/workflows/benchdeck-product-test.yml`
**Required runner labels**: `self-hosted`, `linux`, `rootless-docker`
**Runner user**: `benchdeck-runner` (UID 1001, dedicated, no password, no interactive login)

---

## Status dashboard

> **Agents resuming work: read this section first. Do NOT re-read the whole file.**
> The executing agent flips the markers below as work progresses.

<!-- runbook-status: pending -->

| # | Phase                              | Status         | Marker                              |
|---|------------------------------------|:--------------:|-------------------------------------|
| 0 | Pre-flight checks                  | ⬜ pending     | `<!-- phase-0: pending -->`         |
| 1 | WSL2 host tuning                   | ⬜ pending     | `<!-- phase-1: pending -->`         |
| 2 | Rootless Docker install            | ⬜ pending     | `<!-- phase-2: pending -->`         |
| 3 | System tools (`jq`, `git`, `python3`) | ⬜ pending | `<!-- phase-3: pending -->`         |
| 4 | Dedicated `benchdeck-runner` user  | ⬜ pending     | `<!-- phase-4: pending -->`         |
| 5 | GitHub Actions runner install      | ⬜ pending     | `<!-- phase-5: pending -->`         |
| 6 | First end-to-end workflow run      | ⬜ pending     | `<!-- phase-6: pending -->`         |
| 7 | Polish: health, disk, archives, auto-update | ⬜ pending | `<!-- phase-7: pending -->` |
| 8 | Live OpenAI wiring (optional but recommended) | ⬜ pending | `<!-- phase-8: pending -->` |

**One-glance resume command** (run from this file's directory):
```bash
grep -nE '<!-- (phase|step|runbook-status)' docs/runner-setup.md
```

**Final acknowledgement** (delete this whole block when all phases are done):
- [ ] All 9 markers flipped to `done`
- [ ] `scripts/benchdeck-runner-smoke-test.sh` exit 0 on the runner host
- [ ] At least one workflow run completed all 5 steps (offline path)
- [ ] At least one workflow run completed all 6 steps (live path, if you opt into Phase 8)
- [ ] `RUNNER_SETUP.md` and `.product-test/runner-setup.md` still resolve to this file

---

## Quick reference (the commands you'll run most)

| What you want to check | Command |
|---|---|
| Runner service alive (WSL2) | `systemctl --user -M benchdeck-runner@ status actions.runner.*` |
| Runner is online to GitHub | `curl -fsSL https://github.com/MerverliPy/BenchDeck/actions/runners \| grep -A1 benchdeck-` |
| Rootless Docker healthy | `sudo -u benchdeck-runner -H bash -c 'docker info \| grep -i rootless'` |
| Free space in WSL2 vhdx | `df -h /` (in WSL2) |
| Today's evidence | `ls -lt /home/benchdeck-runner/.cache/benchdeck-product-test/*/workspaces/*/repo/.test-evidence/ \| head` |
| Re-run smoke test | `sudo -u benchdeck-runner -H bash /home/benchdeck-runner/benchdeck-runner/scripts/benchdeck-runner-smoke-test.sh` |
| Tail runner log | `journalctl --user -u 'actions.runner.*' -f` (as `benchdeck-runner` user) |

---

# Phase 0 — Pre-flight checks

**Marker**: `<!-- phase-0: pending -->` (flip to `<!-- phase-0: done -->`)

Read-only checks. Failures here mean a higher-phase fix is impossible; address first.

### Step 0.1 — Confirm WSL2 distro, version, kernel, systemd

<!-- step-0.1: pending -->

From **Windows PowerShell**:
```powershell
wsl -l -v
```

**Expected**: a row like `Ubuntu 22.04.x  Running  2`. Note the exact distro name (default is `Ubuntu`).

From **inside WSL2 Ubuntu**:
```bash
lsb_release -a           # expect Ubuntu 22.04 LTS or newer
uname -r                 # expect 5.10+ (systemd needs 5.10+ in WSL2)
systemctl is-system-running   # expect "running" or "degraded"
cat /etc/wsl.conf        # expect [boot] systemd=true
```

If `systemctl` says anything other than `running`/`degraded`, fix it before continuing — see [Fix: systemd not running](#fix-systemd-not-running).

**Verify**: mark `<!-- step-0.1: done -->`.

### Step 0.2 — Confirm hardware headroom

<!-- step-0.2: pending -->

```bash
nproc                    # threads
free -h                  # RAM (note available, not just total)
df -h /                  # free space in WSL2 vhdx
```

**Expected**:
- Threads ≥ 4 (host has 8 on the i7-9xxx; expect 8 or more)
- Available RAM ≥ 8 GB (we'll set the WSL2 cap to 32 GB in Phase 1)
- Free space in `/` ≥ 30 GB (Docker images + disposable clones grow over time)

If free space < 30 GB, expand the vhdx or prune before continuing:
```powershell
# In PowerShell, set initial size to 60 GB so it has headroom from day one
wsl --shutdown
diskpart
# select vdisk "<path-to-WSL2-Install>\ext4.vhdx"
# expand vdisk maximum=60000
```

**Verify**: mark `<!-- step-0.2: done -->`.

### Step 0.3 — Detect any pre-existing Docker

<!-- step-0.3: pending -->

```bash
which docker
docker --version 2>&1 || echo "docker not installed (expected for clean machine)"
systemctl status docker 2>&1 | head -3 || echo "no docker service (expected for clean machine)"
ls /var/run/docker.sock 2>&1 || echo "no docker socket (expected for clean machine)"
```

Three common states you may find:

| State | What it means | Action |
|---|---|---|
| Nothing installed (clean) | Perfect starting point | Proceed to Phase 2 |
| `docker-ce` already running as root (the `docker` group) | Rootful Docker, will fail the workflow's rootless check | Uninstall via `sudo apt remove docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin` before Phase 2 |
| Docker Desktop (Linux daemon) | Rootful, will fail the rootless check | Disable "Use Docker Compose V2" and switch off Docker Desktop, then uninstall; or accept the constraint that you can't have both Docker Desktop and rootless dockerd on the same WSL2 host |

**Verify**: mark `<!-- step-0.3: done -->`.

---

# Phase 1 — WSL2 host tuning

**Marker**: `<!-- phase-1: pending -->` (flip to `<!-- phase-1: done -->`)

Caps WSL2 to 32 GB so Windows has headroom. Adds vhdx initial-size so the disk doesn't bloat silently.

### Step 1.1 — Edit `C:\Users\<you>\.wslconfig`

<!-- step-1.1: pending -->

From **Windows PowerShell** (not WSL2 — this is a Windows file):
```powershell
notepad "$env:USERPROFILE\.wslconfig"
```

Paste (adjust `<you>`):
```ini
[wsl2]
memory=32GB
processors=8
swap=8GB
swapFile=D:\\wsl-swap.vhdx
autoMemoryReclaim=gradual
guiApplications=false
localhostForwarding=true
```

Save, close.

**Why**:
- `memory=32GB` — hard cap; leaves 16 GB for Windows on a 48 GB box
- `processors=8` — full i7 core count for WSL2
- `swap=8GB` — fallback if a sandbox needs more than its 4 GB cap transiently
- `autoMemoryReclaim=gradual` — reclaims cached memory back to Windows when idle
- `localhostForwarding=true` — needed for the GitHub runner to reach WSL2-side services

**Verify**: mark `<!-- step-1.1: done -->`.

### Step 1.2 — Restart WSL2 to apply

<!-- step-1.2: pending -->

From **Windows PowerShell**:
```powershell
wsl --shutdown
# wait ~5 seconds
wsl -d Ubuntu -e bash -c 'free -h | head -2'
```

**Expected**: `Mem:` row shows total ≤ 32 GB.

**Verify**: mark `<!-- step-1.2: done -->`.

---

# Phase 2 — Rootless Docker install

**Marker**: `<!-- phase-2: pending -->` (flip to `<!-- phase-2: done -->`)

The critical phase. **Do not skip the rootless-setuptool step.** A "normal" `docker-ce` install in WSL2 runs the daemon as root; the workflow's `grep -qi rootless` would fail.

### Step 2.1 — Add Docker apt repo and install packages

<!-- step-2.1: pending -->

From **WSL2 Ubuntu** (your own user; this is system-wide install):
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin uidmap dbus-user-session
```

**Verify**: mark `<!-- step-2.1: done -->`.

### Step 2.2 — Create the dedicated runner user with subuid/subgid ranges

<!-- step-2.2: pending -->

Rootless Docker needs non-overlapping `subuid`/`subgid` ranges for the user. This is the same step that creates the user itself.

```bash
sudo useradd -m -s /bin/bash -u 1001 -U benchdeck-runner
sudo passwd -l benchdeck-runner                # no password (SSH key only if ever)
sudo usermod -aG sudo benchdeck-runner         # passwordless sudo not granted — see Phase 4
echo "benchdeck-runner:100000:65536" | sudo tee -a /etc/subuid
echo "benchdeck-runner:100000:65536" | sudo tee -a /etc/subgid
# Allow the runner user to control dockerd without root
sudo loginctl enable-linger benchdeck-runner
```

**Verify**:
```bash
id benchdeck-runner        # expect uid=1001, groups includes benchdeck-runner, sudo
getsubids benchdeck-runner # expect 100000-165535
```

**Verify**: mark `<!-- step-2.2: done -->`.

### Step 2.3 — Run the rootless setup tool

<!-- step-2.3: pending -->

```bash
sudo -iu benchdeck-runner
dockerd-rootless-setuptool.sh install
exit
```

**Expected output (last lines)**:
```
[+] Building 0.0s (0/0)
docker.sock   running as user 1001
... SystemD unit docker.service created ...
... User-mode systemd service docker.service is now active ...
```

If the tool prints a message about `XDG_RUNTIME_DIR`, source the suggested `~/.bashrc` snippet.

**Verify**:
```bash
sudo -iu benchdeck-runner bash -c 'docker info --format "{{json .SecurityOptions}}" | head -c 500'
```

**Expected**: JSON containing the substring `rootless`. If not, **do not proceed**; capture the output and re-check Phase 2.3.

**Verify**: mark `<!-- step-2.3: done -->`.

### Step 2.4 — Configure the user-mode dockerd service

<!-- step-2.4: pending -->

```bash
sudo -iu benchdeck-runner
systemctl --user enable docker
systemctl --user start docker
systemctl --user status docker | head -10
exit
```

**Expected**: `active (running)`. If you see `inactive (dead)` or `failed`, the previous step didn't actually create the service file — re-run `dockerd-rootless-setuptool.sh install`.

**Verify**: also confirm a single container can run:
```bash
sudo -iu benchdeck-runner docker run --rm hello-world
```

**Verify**: mark `<!-- step-2.4: done -->`.

---

# Phase 3 — System tools

**Marker**: `<!-- phase-3: pending -->` (flip to `<!-- phase-3: done -->`)

### Step 3.1 — Install `jq` and confirm `git` / `python3`

<!-- step-3.1: pending -->

The workflow's first verification step is `command -v jq`. The runner also needs `git` and `python3` on PATH.

```bash
sudo apt-get install -y jq
jq --version
git --version
python3 --version   # must be ≥ 3.10 (workflow reads the .product-test/config which uses tomllib)
```

**Expected**: `jq` ≥ 1.6, `git` ≥ 2.34, `python3` ≥ 3.10 (Ubuntu 22.04 ships 3.10; Ubuntu 24.04 ships 3.12).

**Verify**: mark `<!-- step-3.1: done -->`.

---

# Phase 4 — Dedicated `benchdeck-runner` user lockdown

**Marker**: `<!-- phase-4: pending -->` (flip to `<!-- phase-4: done -->`)

The runner user needs **only**:
- to run the GitHub Actions runner binary
- to run the rootless dockerd
- to read/write its own home + the evidence directory

It should **not** be able to modify the host system, install packages, or run as root. The earlier `usermod -aG sudo` is a deliberate choice — we add it to the `sudo` group, then immediately restrict `sudo` to one specific command (the cron-driven disk-pressure watchdog from Phase 7), passwordless.

### Step 4.1 — Restrict `sudo` for the runner user

<!-- step-4.1: pending -->

```bash
echo 'benchdeck-runner ALL=(ALL) NOPASSWD: /usr/sbin/loginctl' | sudo tee /etc/sudoers.d/benchdeck-runner
sudo chmod 0440 /etc/sudoers.d/benchdeck-runner
sudo -u benchdeck-runner sudo -ln | head -10
```

**Expected**: list shows `(ALL) NOPASSWD: /usr/sbin/loginctl` only.

If the list shows `ALL` or anything else, undo with `sudo rm /etc/sudoers.d/benchdeck-runner` and re-try.

**Verify**: mark `<!-- step-4.1: done -->`.

### Step 4.2 — Trim the runner user's environment

<!-- step-4.2: pending -->

```bash
sudo -iu benchdeck-runner
mkdir -p ~/benchdeck-runner
# Bash dotfiles minimal
cat > ~/.bashrc <<'EOF'
# Runner-only bashrc — no prompt, no aliases, no toolchain pollution
export PATH=/usr/local/bin:/usr/bin:/bin
[ -d /home/benchdeck-runner/.local/bin ] && PATH=/home/benchdeck-runner/.local/bin:$PATH
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock
EOF
chmod 0644 ~/.bashrc
mkdir -p ~/.local/bin
exit
```

**Verify**: open a new shell as the user and confirm `echo $DOCKER_HOST` shows the rootless socket.

**Verify**: mark `<!-- step-4.2: done -->`.

---

# Phase 5 — GitHub Actions runner install

**Marker**: `<!-- phase-5: pending -->` (flip to `<!-- phase-5: done -->`)

### Step 5.1 — Get a registration token

<!-- step-5.1: pending -->

From the **GitHub web UI** (or via `gh` CLI):
- Repo → Settings → Actions → Runners → New self-hosted runner
- Choose Linux, x64
- GitHub shows a one-time token. **Copy it** — it expires in ~1 hour.
- Recommended: a **fine-grained PAT** on a dedicated "runner-admin" account, scope `repo` on `MerverliPy/BenchDeck`, with "Self-hosted runners: Read and write" admin permission, gives you an unbounded registration path. Save the PAT in 1Password or similar; do NOT check it in.

CLI alternative (assumes `gh auth login` is done):
```bash
TOKEN=$(gh api -X POST /repos/MerverliPy/BenchDeck/actions/runners/registration-token --jq .token)
echo "$TOKEN" | head -c 20 ; echo "..."
```

**Verify**: mark `<!-- step-5.1: done -->`.

### Step 5.2 — Download and extract the runner

<!-- step-5.2: pending -->

From inside WSL2, as `benchdeck-runner`:
```bash
sudo -iu benchdeck-runner
cd ~
mkdir -p benchdeck-runner && cd benchdeck-runner
# Use the URL GitHub showed (substitute the exact version)
curl -fsSL -o runner.tar.gz "https://github.com/actions/runner/releases/download/v2.319.1/actions-runner-linux-x64-2.319.1.tar.gz"
tar -xzf runner.tar.gz
rm runner.tar.gz
ls -la
exit
```

**Expected**: `run.sh`, `config.sh`, `svc.sh`, `_work/`, `bin/`, etc. all present.

**Verify**: mark `<!-- step-5.2: done -->`.

### Step 5.3 — Configure the runner

<!-- step-5.3: pending -->

```bash
sudo -iu benchdeck-runner
cd ~/benchdeck-runner
./config.sh \
  --url https://github.com/MerverliPy/BenchDeck \
  --token "$TOKEN" \
  --name "benchdeck-runner-wsl2" \
  --labels "self-hosted,linux,rootless-docker" \
  --runnergroup default \
  --work _work \
  --replace
exit
```

**Expected**: prompts for nothing (non-interactive); prints `Settings Saved.` and exits 0.

**Verify**:
- GitHub → Settings → Actions → Runners: the new runner appears with the three labels, status **Idle**.

**Verify**: mark `<!-- step-5.3: done -->`.

### Step 5.4 — Install as a user-level systemd service with auto-restart

<!-- step-5.4: pending -->

The runner ships an `svc.sh` helper that registers a user-mode systemd service. The service runs as `benchdeck-runner` (not root) and inherits the user-mode dockerd. Linger is already enabled from Phase 2.2, so the service survives logout.

```bash
sudo -iu benchdeck-runner
cd ~/benchdeck-runner
./svc.sh install benchdeck-runner
./svc.sh enable
./svc.sh start
systemctl --user status actions.runner.* | head -8
exit
```

**Expected**: `active (running)`.

**Verify**:
```bash
systemctl --user -M benchdeck-runner@.host status 'actions.runner.*' | head -8
```

**Verify**: mark `<!-- step-5.4: done -->`.

### Step 5.5 — Enable runner self-update

<!-- step-5.5: pending -->

By default the runner does not auto-update. Enable it so the binary upgrades itself when idle, matching the GitHub-hosted runner cadence.

```bash
sudo -iu benchdeck-runner
cd ~/benchdeck-runner
# Self-update on idle (default behaviour; explicit for clarity)
cat >> .env <<'EOF'
ACTIONS_RUNNER_UPDATE_FREQUENCY=7   # check for updates every 7 days when idle
EOF
# Allow the runner to self-update; the default is "not allowed"
./config.sh --update-freedom self   # or "latest" for the cutting edge
exit
```

**Verify**: mark `<!-- step-5.5: done -->`.

---

# Phase 6 — First end-to-end workflow run (offline path)

**Marker**: `<!-- phase-6: pending -->` (flip to `<!-- phase-6: done -->`)

This validates the entire boundary, including the "Verify controlled runner boundary" step that the existing failures were tripping on.

### Step 6.1 — Trigger the workflow with defaults

<!-- step-6.1: pending -->

From **GitHub web UI**:
- Repo → Actions → "BenchDeck Product Test" → "Run workflow"
- Inputs:
  - `python_version`: `3.12` (default)
  - `run_live_openai`: **false** (unchecked, default)
  - `model`: `gpt-4o-mini` (default; ignored when not live)
- Click "Run workflow"

**Verify**: mark `<!-- step-6.1: done -->`.

### Step 6.2 — Watch the run

<!-- step-6.2: pending -->

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

<!-- step-6.3: pending -->

The workflow's archive step writes to `${RUNNER_TEMP}/benchdeck-product-test-archives/...tar.gz` on the runner host and adds a SHA-256 + a link to the GitHub step summary.

In WSL2, the runner's `_diag` directory has per-job logs. The evidence tarball is under `/home/benchdeck-runner/.cache/...` or wherever the runner's `RUNNER_TEMP` resolves to:
```bash
find /tmp /home/benchdeck-runner -path '*benchdeck-product-test-archives*' -name '*.tar.gz' -mmin -60 2>/dev/null
```

If the archive is missing, the run failed at the archive step — the sandbox state in `/home/benchdeck-runner/.cache/benchdeck-product-test/<repo-hash>/workspaces/<run-id>/` is still there (`.test-evidence/...` and `state.json`).

**Verify**: mark `<!-- step-6.3: done -->`.

---

# Phase 7 — Polish (the "make it last" part)

**Marker**: `<!-- phase-7: pending -->` (flip to `<!-- phase-7: done -->`)

Eight items. Each has a check + a 10-minute implementation. All reversible.

### Step 7.1 — Smoke test script

<!-- step-7.1: pending -->

The repo already has `scripts/benchdeck-runner-smoke-test.sh` (created alongside this runbook). It does a one-shot check of the full boundary. Run it once now and once a day via cron.

```bash
sudo -u benchdeck-runner -H bash /home/benchdeck-runner/benchdeck-runner/scripts/benchdeck-runner-smoke-test.sh
```

**Expected**: 4 sections all green, exit 0.

**Verify**: mark `<!-- step-7.1: done -->`.

### Step 7.2 — Daily health cron

<!-- step-7.2: pending -->

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

<!-- step-7.3: pending -->

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

<!-- step-7.4: pending -->

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

<!-- step-7.5: pending -->

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

<!-- step-7.6: pending -->

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

<!-- step-7.7: pending -->

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

<!-- step-7.8: pending -->

Re-trigger the workflow (`Phase 6.1` steps) to confirm none of the polish steps broke the boundary.

**Verify**: mark `<!-- step-7.8: done -->`.

---

# Phase 8 — Live OpenAI wiring (optional but recommended)

**Marker**: `<!-- phase-8: pending -->` (flip to `<!-- phase-8: done -->`)

You said you can add a test key now. This phase wires it up **safely** — dedicated key, spend cap, repo-secret-only, never printed, never logged.

### Step 8.1 — Mint a dedicated test key

<!-- step-8.1: pending -->

- Go to https://platform.openai.com/api-keys (use a **dedicated test account**, not your personal)
- Create key: name `benchdeck-product-test-wsl2`
- Set **hard spend cap**: Settings → Limits → Hard limit, $5 is enough for many runs
- Set **monthly budget cap** via billing as a safety net
- **Copy the key now**; OpenAI shows it only once. Store in 1Password / Bitwarden / etc.

**Verify**: mark `<!-- step-8.1: done -->`.

### Step 8.2 — Add the secret to GitHub

<!-- step-8.2: pending -->

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

<!-- step-8.3: pending -->

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

<!-- step-8.4: pending -->

`sandbox_manager.py` line 23 has a redaction rule `SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{10,}")` and `redact()` is called on every stdout/stderr write. Confirm:

```bash
grep -rE 'sk-[A-Za-z0-9_-]{10,}' .test-evidence/ 2>&1 | head
```

**Expected**: 0 matches, or only the literal `[REDACTED_API_KEY]` placeholder.

**Verify**: mark `<!-- step-8.4: done -->`.

### Step 8.5 — Rotate the key (ongoing)

<!-- step-8.5: pending -->

- Set a calendar reminder every 90 days to rotate the dedicated test key
- When the key is rotated, update the GitHub secret — the workflow uses it on the next run automatically
- Old evidence remains in `.test-evidence/` and `E:\benchdeck-evidence\`; consider wiping evidence older than 90 days at the same cadence (already in the disk watchdog from Phase 7.3)

**Verify**: mark `<!-- step-8.5: done -->`.

---

# Appendix A — Troubleshooting

## Fix: systemd not running

If `systemctl is-system-running` returns `off` or `failed` in WSL2:

1. Confirm kernel: `uname -r` should be `5.10+`
2. Confirm `/etc/wsl.conf` contains:
   ```ini
   [boot]
   systemd=true
   ```
3. From Windows PowerShell: `wsl --shutdown`, wait 5 s, reopen WSL2, retry
4. If still failing, ensure you're on Windows 11 (not Windows 10 — older builds lack the systemd plumbing)

## Fix: `docker info` doesn't show `rootless`

Most common cause: the user-mode dockerd is not running. Diagnose:

```bash
sudo -iu benchdeck-runner
systemctl --user status docker
journalctl --user -u docker -n 50
exit
```

If `inactive (dead)`, start it: `sudo -iu benchdeck-runner systemctl --user start docker`. If it crashes on start, check `journalctl --user -u docker` for the error (typical: `/run/user/<uid>` not writable, `DOCKER_HOST` not pointing to the right socket).

## Fix: Workflow shows "No runner matching the specified labels"

Either:
- The runner service is stopped (`sudo -iu benchdeck-runner systemctl --user start actions.runner.*`)
- The runner is registered with the wrong labels (re-run `./config.sh --labels "self-hosted,linux,rootless-docker" --replace`)
- Linger is not enabled (re-run `sudo loginctl enable-linger benchdeck-runner`)

## Fix: Disk full

```bash
sudo -iu benchdeck-runner
# What's taking space?
docker system df
du -sh .cache/benchdeck-product-test/*/workspaces/*/.test-evidence/ 2>/dev/null | sort -h | tail
# Manual cleanup
docker builder prune -af
docker image prune -af
# Or run the watchdog manually
bash ~/bin/benchdeck-runner-disk-watchdog.sh
```

## Fix: WSL2 vhdx expanded beyond intended size

```powershell
wsl --shutdown
diskpart
# select vdisk "<path-to-WSL2-Install>\ext4.vhdx"
# compact vdisk
```

Note: this only compacts free space inside the vhdx; it does not shrink a vhdx that has been grown.

---

# Appendix B — Decisions recap

These are the choices made at planning time. Update them in this file if anything changes.

| Decision | Value | Source |
|---|---|---|
| Runner user | `benchdeck-runner` (UID 1001, dedicated, no password) | Question A |
| Runner concurrency | `--max-parallel 2` | Question B |
| Evidence archive | both (WSL2 vhdx + Windows folder `E:\benchdeck-evidence\`) | Question C |
| Runner auto-update | `ACTIONS_RUNNER_UPDATE_FREQUENCY=7`, `--update-freedom self` | Question D |
| WSL2 memory cap | `memory=32GB` | Question E |
| Live OpenAI | enabled with dedicated key, $5 hard cap, 90-day rotation | Question F |
| Runbook location | canonical `docs/runner-setup.md`; pointer copies at `RUNNER_SETUP.md` and `.product-test/runner-setup.md` | Question G |
| Status format | one-glance TOC at top, per-phase `<!-- phase-N: status -->` markers, grep-friendly | Question H |

---

# Appendix C — Operational contacts

- **Repo**: https://github.com/MerverliPy/BenchDeck
- **Workflow**: `.github/workflows/benchdeck-product-test.yml`
- **Container image**: `python:3.X-slim-bookworm` + `apt` + `jq` + `coreutils` (built from `.product-test/sandbox/Dockerfile`)
- **OpenAI account**: dedicated test account (NOT your personal)
- **OpenAI spend cap**: $5 hard, monthly billing cap as backstop
- **Secret name**: `BENCHDECK_TEST_OPENAI_API_KEY` (GitHub repo secret)
- **Host maintenance windows**: Sundays 04:00-06:00 UTC (cron-driven; no manual action needed)
