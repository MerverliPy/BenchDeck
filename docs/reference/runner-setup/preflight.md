# Runner setup reference — Phase 0 — pre-flight checks

> Agent context note: this is detailed reference material split out of `docs/runner-setup.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/runner-setup-summary.md` and open this shard only when the specific phase is relevant.

# Phase 0 — Pre-flight checks

**Marker**: `<!-- phase-0: done -->` (flip to `<!-- phase-0: done -->`)

Read-only checks. Failures here mean a higher-phase fix is impossible; address first.

### Step 0.1 — Confirm WSL2 distro, version, kernel, systemd

<!-- step-0.1: done -->

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

<!-- step-0.2: done -->

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

<!-- step-0.3: done -->

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

### Step 0.3a — Deviation: dual-mode Docker (rootful kept for unrelated volumes)

<!-- step-0.3a: done -->

If the host has **named volumes owned by an unrelated project** (e.g. `pia-minio-data`,
`pia-postgres-data`, `pia-redis-data` from a sibling repo) under rootful Docker's
`/var/lib/docker/volumes/`, the runbook's "uninstall rootful" action will make
those volumes inaccessible. The volumes themselves stay on disk, but the daemon
to mount them is gone.

In that case, use the **dual-mode** approach instead of uninstalling:

1. **Stop and disable** the rootful service so it does not race the rootless
   daemon on iptables / network namespaces at boot. The packages stay
   installed; the `docker` group stays in place; the data on
   `/var/lib/docker/volumes/` is preserved.
   ```bash
   sudo systemctl disable --now docker docker.socket containerd.service
   sudo systemctl status docker --no-pager | head -3   # expect: inactive (dead)
   ```
2. Install rootless Docker for `benchdeck-runner` (Phase 2). It uses
   **completely separate storage** at `~/.local/share/docker/`, so it does not
   see the rootful volumes and vice versa. No data collision.
3. **Per-user `DOCKER_HOST`** is the routing key. Phase 4.2 sets
   `DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock` for `benchdeck-runner`,
   which makes that user's `docker` CLI hit the rootless daemon. Do **not**
   set `DOCKER_HOST` in the host user's shell, so the host user's `docker` CLI
   defaults to rootful's `/var/run/docker.sock` and continues to work when
   rootful is up.
4. Provide toggle helpers for the host user so starting/stopping the rootful
   daemon is one command:
   ```bash
   sudo install -d -m 0755 /usr/local/bin
   sudo tee /usr/local/bin/pia-docker-up   >/dev/null <<'EOF'
   #!/usr/bin/env bash
   set -euo pipefail
   exec sudo systemctl start docker docker.socket containerd.service
   EOF
   sudo tee /usr/local/bin/pia-docker-down >/dev/null <<'EOF'
   #!/usr/bin/env bash
   set -euo pipefail
   exec sudo systemctl stop docker docker.socket containerd.service
   EOF
   sudo chmod 0755 /usr/local/bin/pia-docker-up /usr/local/bin/pia-docker-down
   ```
   Usage: `pia-docker-up` before working on PIA, `pia-docker-down` after.

**Safety notes**:
- The two daemons can run at the same time, but the rootful daemon should be
  stopped when not in use so it does not hold `iptables` chains the rootless
  daemon might collide with. The cron in Phase 7.3 will not stop the rootful
  daemon because it does not know whether a PIA session is in progress.
- The rootless workflow's `grep -qi rootless` boundary check is per-user; it
  reads `docker info` from the runner user's socket, which is the rootless
  one. It will pass regardless of whether rootful is up or down.
- Volume data on `/var/lib/docker/volumes/` is preserved across the entire
  dual-mode setup. It is **not** deleted by `pia-docker-down` or by Phase 2.
- This deviation is also recorded in Appendix B ("Decisions recap").

**Verify**:
```bash
sudo systemctl is-active docker   # expect: inactive
sudo -u benchdeck-runner -H docker info --format '{{json .SecurityOptions}}' | head -c 200
# expect: JSON containing "rootless" (after Phase 2)
```

**Verify**: mark `<!-- step-0.3a: done -->`.

---
