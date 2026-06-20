# Runner setup reference — Phases 3–4 — system tools and runner-user lockdown

> Agent context note: this is detailed reference material split out of `docs/runner-setup.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/runner-setup-summary.md` and open this shard only when the specific phase is relevant.

# Phase 3 — System tools

**Marker**: `<!-- phase-3: done -->` (flip to `<!-- phase-3: done -->`)

### Step 3.1 — Install `jq` and confirm `git` / `python3`

<!-- step-3.1: done -->

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

**Marker**: `<!-- phase-4: done -->` (flip to `<!-- phase-4: done -->`)

The runner user needs **only**:
- to run the GitHub Actions runner binary
- to run the rootless dockerd
- to read/write its own home + the evidence directory

It should **not** be able to modify the host system, install packages, or run as root. The earlier `usermod -aG sudo` is a deliberate choice — we add it to the `sudo` group, then immediately restrict `sudo` to one specific command (the cron-driven disk-pressure watchdog from Phase 7), passwordless.

### Step 4.1 — Restrict `sudo` for the runner user

<!-- step-4.1: done -->

```bash
echo 'benchdeck-runner ALL=(ALL) NOPASSWD: /usr/sbin/loginctl' | sudo tee /etc/sudoers.d/benchdeck-runner
sudo chmod 0440 /etc/sudoers.d/benchdeck-runner
sudo -u benchdeck-runner sudo -ln | head -10
```

**Expected**: list shows `(ALL) NOPASSWD: /usr/sbin/loginctl` only.

If the list shows `ALL` or anything else, undo with `sudo rm /etc/sudoers.d/benchdeck-runner` and re-try.

**Verify**: mark `<!-- step-4.1: done -->`.

### Step 4.2 — Trim the runner user's environment

<!-- step-4.2: done -->

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
