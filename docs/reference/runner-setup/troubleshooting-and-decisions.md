# Runner setup reference — Appendices — troubleshooting, decisions, and operational contacts

> Agent context note: this is detailed reference material split out of `docs/runner-setup.md` during Cycle 7A. For routine agent context, start with `docs/context-handoffs/runner-setup-summary.md` and open this shard only when the specific phase is relevant.

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
| Rootful Docker disposition | kept installed but stopped+disabled; `pia-*` volumes preserved; toggle helpers `pia-docker-up` / `pia-docker-down` | 2026-06-13 deviation, Phase 0.3a |
| WSL2 shutdown safety | never run `wsl --shutdown` from inside a WSL2 distro; always from Windows PowerShell, or use `wsl.exe --terminate <distro>` to kill a single distro | 2026-06-13 safety note, Phase 1.2a |
| Keepalive tasks | pre-existing `WSL2 Keepalive` task (runs `sleep infinity`, for SSH access) preserved; new `WSL2 systemd revive` task added separately, does not clobber the existing one | 2026-06-13 deviation, Phase 7.6 |
| Step 2.1 — Docker apt repo format | host already had the repo configured in the modern deb822 format (`/etc/apt/sources.list.d/docker.sources` + `/etc/apt/keyrings/docker.asc`); runbook's legacy `docker.list` + `docker.gpg` was a no-op + conflict; left the host's existing pair in place | 2026-06-13 deviation, Phase 2.1 |
| Step 2.2 — `sudo` group policy | `benchdeck-runner` is **not** added to the `sudo` group; Phase 4.1 will write only the `NOPASSWD: /usr/sbin/loginctl` sudoers entry. Avoids a window of full passwordless sudo between Phase 2.2 and 4.1. | 2026-06-13 deviation, Phase 2.2 |
| Step 2.3 — rootless setuptool env | first invocation (`sudo -iu bash -c '...'`) failed with "systemd not detected" because the inner bash did not export `XDG_RUNTIME_DIR=/run/user/1001`; re-ran with the env exported explicitly and the user manager became reachable. **Phase 4.2 must set `XDG_RUNTIME_DIR=/run/user/$(id -u)` and `DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock` in `~/.bashrc` so the daemon auto-starts in subsequent sessions.** | 2026-06-13 deviation, Phase 2.3 |
| Step 4.1 — `loginctl` path | runbook specifies `/usr/sbin/loginctl`; on Ubuntu 24.04 (and 22.04) the actual path is `/usr/bin/loginctl`. Sudoers entry updated to the correct path. The semantic intent (allow only `loginctl`, deny everything else) is preserved; the smoke test (`sudo -n /usr/bin/loginctl show-user benchdeck-runner`) and negative tests (`/usr/bin/apt-get`, `/usr/bin/systemctl` both denied) all pass. | 2026-06-13 deviation, Phase 4.1 |
| Step 5.2 — runner version | runbook pins v2.319.1; only **v2.332.0** registers successfully on github.com in 2026. v2.319.1, v2.330.0, v2.332.0, v2.335.1 all hit the same `POST /actions/runner-registration` 404 (a known open bug, actions/runner #4217); the difference is that v2.332.0 has a fallback path that succeeds with a short-lived registration token. Pinned to v2.332.0. | 2026-06-13 deviation, Phase 5.2 |
| Step 5.3 — token strategy | runbook says pass a fine-grained PAT to `./config.sh --token`. That fails (the fine-grained PAT must have "Administration: Read and write" repo permission, not "Actions: Read and write", per GitHub's REST docs). Workaround that worked: use the user's existing `gh`-authenticated classic-PAT to fetch a **short-lived registration token** from `POST /repos/MerverliPy/BenchDeck/actions/runners/registration-token`, then pass that short-lived token (not the PAT) to the runner. The same token must be used within ~1 hour. | 2026-06-13 deviation, Phase 5.3 |
| Step 5.4 — service level | runbook's `sudo -iu benchdeck-runner && ./svc.sh install` approach fails: `svc.sh` writes the unit to `/etc/systemd/system/` (system-level, requires root) and refuses to run as non-root. The verify step's `systemctl --user -M benchdeck-runner@.host status actions.runner.*` therefore does not match the actual install. Correct approach: `cd /home/benchdeck-runner/benchdeck-runner && sudo ./svc.sh install benchdeck-runner && sudo ./svc.sh start`. Status check is `systemctl status 'actions.runner.*'` (system-level). Requires the runner home to be world-traversable (`chmod 0755 /home/benchdeck-runner`) so `cd` works. | 2026-06-13 deviation, Phase 5.4 |
| Step 5.5 — update-freedom | runbook uses `./config.sh --update-freedom self`; that fails with "runner is already configured". Workaround: write `ACTIONS_RUNNER_UPDATE_FREEDOM=self` to the runner's `.env` file. The runner reads this env var on each startup. | 2026-06-13 deviation, Phase 5.5 |
| Phase 6 — workflow fix | The repo's `benchdeck-product-test.yml` had `${{ runner.temp }}` in the job-level `env:` block, which is invalid (the `runner` context is only available at step level). Every push and dispatch failed at parse time with HTTP 422. Fix: move `PRODUCT_TEST_ARCHIVE_DIR` to the "Archive evidence" step's `env:` block. Also: the runner's `.env` must set `DOCKER_HOST=unix:///run/user/1001/docker.sock` and `XDG_RUNTIME_DIR=/run/user/1001` with **hardcoded UID 1001** (the Node.js dotenv parser does not shell-expand `$(id -u)`). The dockerd-rootless-setuptool's "rootless" docker context points at the fallback path `/home/benchdeck-runner/.docker/run/docker.sock`, not the systemd-managed `/run/user/1001/docker.sock`, so an explicit `DOCKER_HOST` is required. | 2026-06-13 fix, Phase 6 |
| Phase 6 — pytest failure (separate repo issue) | The regression step (9 commands total) reached `pytest --cov=src/benchdeck --cov-report=term-missing --cov-report=json` and crashed with `RuntimeError: Could not determine home directory.` from `src/benchdeck/config.py:20`'s `Path.home()`. The previous 5 commands (`python --version`, `python -m pip check`, `ruff check .`, `ruff format --check .`, `mypy src/benchdeck/`) had passed; the 3 `benchdeck` CLI smoke commands (`--help`, `inspect`, `inspect --json`) were skipped because the regression step `raise SystemExit(1)`s on the first failure. The 2 failing tests (`test_main_run_missing_api_key`, `test_main_run_returns_2_on_planner_failure_with_invalid_key`) use `patch.dict(os.environ, {}, clear=True)` which clears HOME, and the CLI's `load_config()` did not handle the missing-HOME case. This is **not** a runner-setup issue — the runner is fully functional. **Resolution applied (Phase 6 follow-up + Phase 8 prerequisite)**: `src/benchdeck/config.py:load_config` now wraps the `Path.home()` call in `contextlib.suppress(RuntimeError)` so a missing HOME is treated as "no home-dir config file" rather than a crash. Re-run shows all 9 regression commands pass. | 2026-06-13 known issue, Phase 6 |
| Phase 7.1 — smoke test script | The script's `docker info` and `docker run` calls use the user's default Docker context, but the dockerd-rootless-setuptool's "rootless" context points at the fallback path `/home/<user>/.docker/run/docker.sock` rather than the actual `/run/user/<uid>/docker.sock`. Also, the disposable container assertion's `docker run` invocation omits `--user`, so alpine starts as root and fails the script's own non-root boundary check. Both fixed in `scripts/benchdeck-runner-smoke-test.sh`: export `XDG_RUNTIME_DIR` and `DOCKER_HOST` explicitly with hardcoded UID (Node.js dotenv does not shell-expand `$(id -u)`); add `--user 1000:1000` to the disposable container invocation. Smoke test now exits 0. | 2026-06-13 fix, Phase 7.1 |
| Phase 8 — live OpenAI wiring | **Historical incident record; do not reproduce these controls.** An earlier WSL2 experiment temporarily used `OPENAI_API_KEY` in the container environment and permissive host modes to work around 9P bind behavior. Those measures are superseded. The current design keeps the host key file owner-only, streams it over `docker exec -i` standard input into a private in-container `/run/secrets` tmpfs, exposes only `OPENAI_API_KEY_FILE`, uses a private `/evidence` tmpfs, and copies evidence out after execution. The no-request canary boundary check must pass before live execution. | 2026-06-13 history; superseded by 2026-06-17 hardening |
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

---

_Last reviewed: 2026-06-13. This runbook is a living document — when you deviate from a step (e.g. the 13 rows in Appendix B), update the deviation row in the same change. The `<!-- runbook-status: pending -->` marker is for the **executor** to flip during a run; the human-readable "Last reviewed" line above is for **future readers** (the next agent or maintainer) to know when the doc was last walked end-to-end against the actual host._
