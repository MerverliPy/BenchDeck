# Self-Hosted Runner Setup Runbook

> Agent context note: this file is now the concise routing document. Use `docs/context-handoffs/runner-setup-summary.md` for agent handoffs. Open the reference shards below only when changing or troubleshooting the runner host.

**Audience**: a human setting up or maintaining the self-hosted GitHub Actions runner on a **Windows 11 host with WSL2 Ubuntu** that hosts **rootless Docker** for the `BenchDeck Product Test` workflow.

**Repo**: `MerverliPy/BenchDeck`
**Workflow file**: `.github/workflows/benchdeck-product-test.yml`
**Required runner labels**: `self-hosted`, `linux`, `rootless-docker`
**Runner user**: `benchdeck-runner` (UID 1001, dedicated, no password, no interactive login)

---

## Current status

<!-- runbook-status: done -->

| Area | Status | Notes |
|---|:---:|---|
| Pre-flight checks | ✅ done | WSL2/systemd, hardware headroom, Docker state verified. |
| Dual-mode Docker deviation | ✅ done | Rootful Docker may be retained for unrelated volumes, but runner Docker must route to rootless socket. |
| WSL2 host tuning | ✅ done | `.wslconfig` memory/disk guardrails applied. |
| Rootless Docker install | ✅ done | `benchdeck-runner` owns the rootless daemon and socket. |
| Runner user lockdown | ✅ done | Dedicated user, narrow sudo profile, controlled environment. |
| GitHub Actions runner install | ✅ done | User-level service, self-update behavior, isolation model documented. |
| Offline workflow run | ✅ done, partial | Offline path completed all expected runner-boundary and sandbox checks. |
| Operational polish | ✅ done | Smoke test, health cron, disk watchdog, evidence archival, log rotation, WSL keepalive. |
| Live OpenAI wiring | ✅ done | Live path completed with model-quality failure verdict, not runner setup failure. |

## Start here

| Task | File |
|---|---|
| Agent-facing handoff | [`context-handoffs/runner-setup-summary.md`](context-handoffs/runner-setup-summary.md) |
| Pre-flight checks | [`reference/runner-setup/preflight.md`](reference/runner-setup/preflight.md) |
| WSL2 host tuning | [`reference/runner-setup/wsl2-host-tuning.md`](reference/runner-setup/wsl2-host-tuning.md) |
| Rootless Docker install | [`reference/runner-setup/rootless-docker.md`](reference/runner-setup/rootless-docker.md) |
| System tools and runner-user lockdown | [`reference/runner-setup/system-tools-and-user-lockdown.md`](reference/runner-setup/system-tools-and-user-lockdown.md) |
| GitHub Actions runner install | [`reference/runner-setup/github-actions-runner.md`](reference/runner-setup/github-actions-runner.md) |
| First workflow run, polish, and live OpenAI wiring | [`reference/runner-setup/workflow-polish-and-live-openai.md`](reference/runner-setup/workflow-polish-and-live-openai.md) |
| Troubleshooting and decisions recap | [`reference/runner-setup/troubleshooting-and-decisions.md`](reference/runner-setup/troubleshooting-and-decisions.md) |

## Quick reference

| What to check | Command |
|---|---|
| Runner service alive in WSL2 | `systemctl --user -M benchdeck-runner@ status actions.runner.*` |
| Runner online in GitHub | `curl -fsSL https://github.com/MerverliPy/BenchDeck/actions/runners | grep -A1 benchdeck-` |
| Rootless Docker healthy | `sudo -u benchdeck-runner -H bash -c 'docker info | grep -i rootless'` |
| Free space in WSL2 vhdx | `df -h /` |
| Latest product-test evidence | `ls -lt /home/benchdeck-runner/.cache/benchdeck-product-test/*/workspaces/*/repo/.test-evidence/ | head` |
| Re-run runner smoke test | `sudo -u benchdeck-runner -H bash /home/benchdeck-runner/benchdeck-runner/scripts/benchdeck-runner-smoke-test.sh` |
| Tail runner service log | `journalctl --user -u 'actions.runner.*' -f` as `benchdeck-runner` |

## Safety invariants

- Do not weaken the rootless Docker boundary check; `benchdeck-runner` must resolve `docker` to the rootless socket.
- Do not delete unrelated rootful Docker volumes when using the documented dual-mode deviation.
- Do not run `wsl --shutdown` from inside WSL2; issue WSL lifecycle commands from Windows PowerShell.
- Keep generated product-test evidence outside prompt-critical context unless a bounded excerpt is needed.
- Keep `RUNNER_SETUP.md` and `.product-test/runner-setup.md` as pointers to this canonical doc.

## Validation command

```bash
grep -nE '<!-- (phase|step|runbook-status)' docs/reference/runner-setup/*.md
sudo -u benchdeck-runner -H bash /home/benchdeck-runner/benchdeck-runner/scripts/benchdeck-runner-smoke-test.sh
```
