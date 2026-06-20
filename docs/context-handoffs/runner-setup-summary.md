# Runner setup handoff summary

## Purpose

Maintain the BenchDeck self-hosted GitHub Actions runner on Windows 11 + WSL2 Ubuntu with rootless Docker for `.github/workflows/benchdeck-product-test.yml`.

## Current state

| Item | Value |
|---|---|
| Canonical doc | `docs/runner-setup.md` |
| Detailed reference shards | `docs/reference/runner-setup/` |
| Runner user | `benchdeck-runner` |
| Required labels | `self-hosted`, `linux`, `rootless-docker` |
| Docker boundary | `benchdeck-runner` must use rootless Docker through its user socket. |
| Runbook status | Done, including offline and live workflow paths. |

## Operational checks

```bash
systemctl --user -M benchdeck-runner@ status actions.runner.*
sudo -u benchdeck-runner -H bash -c 'docker info | grep -i rootless'
sudo -u benchdeck-runner -H bash /home/benchdeck-runner/benchdeck-runner/scripts/benchdeck-runner-smoke-test.sh
```

## Reference routing

| Need | Open |
|---|---|
| WSL2/systemd/hardware/Docker pre-flight | `docs/reference/runner-setup/preflight.md` |
| `.wslconfig`, WSL lifecycle safety | `docs/reference/runner-setup/wsl2-host-tuning.md` |
| Rootless Docker package/install/service setup | `docs/reference/runner-setup/rootless-docker.md` |
| `jq`/`git`/`python3`, sudo lockdown, environment | `docs/reference/runner-setup/system-tools-and-user-lockdown.md` |
| GitHub runner registration, service, isolation | `docs/reference/runner-setup/github-actions-runner.md` |
| Workflow run, cron health, disk watchdog, evidence archival, live OpenAI | `docs/reference/runner-setup/workflow-polish-and-live-openai.md` |
| Known fixes and decisions recap | `docs/reference/runner-setup/troubleshooting-and-decisions.md` |

## Safety rules

- Preserve the rootless Docker boundary check.
- Preserve unrelated rootful Docker volumes when dual-mode Docker is used.
- Run WSL lifecycle commands from Windows PowerShell, not from inside WSL2.
- Keep evidence/log inspection bounded; do not paste large evidence trees into agent context.
- Keep `RUNNER_SETUP.md` and `.product-test/runner-setup.md` as pointers to `docs/runner-setup.md`.
