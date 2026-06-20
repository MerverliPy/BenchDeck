# Runner setup reference — Phase 5 — GitHub Actions runner install

> Agent context note: this is detailed reference material split out of `docs/runner-setup.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/runner-setup-summary.md` and open this shard only when the specific phase is relevant.

# Phase 5 — GitHub Actions runner install

**Marker**: `<!-- phase-5: done -->` (flip to `<!-- phase-5: done -->`)

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

<!-- step-5.2: done -->

From inside WSL2, as `benchdeck-runner`:
```bash
sudo -iu benchdeck-runner
cd ~
mkdir -p benchdeck-runner && cd benchdeck-runner
# Use the URL GitHub showed (substitute the exact version)
curl -fsSL -o runner.tar.gz "https://github.com/actions/runner/releases/download/v2.332.0/actions-runner-linux-x64-2.332.0.tar.gz"
tar -xzf runner.tar.gz
rm runner.tar.gz
ls -la
exit
```

**Expected**: `run.sh`, `config.sh`, `svc.sh`, `_work/`, `bin/`, etc. all present.

**Verify**: mark `<!-- step-5.2: done -->`.

### Step 5.3 — Configure the runner

<!-- step-5.3: done -->

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

<!-- step-5.4: done -->

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

<!-- step-5.5: done -->

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

### Step 5.6 — Runner isolation model

<!-- step-5.6: done -->

This runner is provisioned as a **persistent systemd service**. It is NOT
configured for JIT/ephemeral one-job registration. After each workflow job:

- The runner process persists and accepts further jobs.
- Host state (cached registrations, Docker images, `_work/` clones) is NOT
  wiped between jobs.
- Repository-controlled Python (`python3 .product-test/scripts/...`) executes
  on the bare host before the disposable Docker sandbox boundary is
  established (see Phase 0 containment).

**Target state (not yet proven):**
- Register the runner as a JIT runner (`./config.sh --jit`) so it accepts
  exactly one job and then de-registers.
- After each job, recreate the WSL2 host from a clean snapshot or a
  pre-built image.

**Current mitigations:**
- The `benchdeck-product-test.yml` workflow is `workflow_dispatch` only
  (not automatic on push/PR).
- The workflow requires a `product-test` environment (requires approval
  if protected-environment rules are configured).
- The sandbox container is created afresh for each run and destroyed
  afterwards (`--purge`), isolating the actual test execution.

**Verify**: mark `<!-- step-5.6: done -->`.

---
