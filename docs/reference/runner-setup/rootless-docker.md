# Runner setup reference — Phase 2 — rootless Docker install

> Agent context note: this is detailed reference material split out of `docs/runner-setup.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/runner-setup-summary.md` and open this shard only when the specific phase is relevant.

# Phase 2 — Rootless Docker install

**Marker**: `<!-- phase-2: done -->` (flip to `<!-- phase-2: done -->`)

The critical phase. **Do not skip the rootless-setuptool step.** A "normal" `docker-ce` install in WSL2 runs the daemon as root; the workflow's `grep -qi rootless` would fail.

### Step 2.1 — Add Docker apt repo and install packages

<!-- step-2.1: done -->

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

<!-- step-2.2: done -->

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

<!-- step-2.3: done -->

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

<!-- step-2.4: done -->

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
