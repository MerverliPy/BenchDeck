# Changelog

## Unreleased

### Fixed

- **`publish.yml` now supports both `PYPI_API_TOKEN` and OIDC Trusted Publishing.**
  The first `v0.1.2` tag push failed with
  `Trusted publishing exchange failure: invalid-publisher` because no PyPI
  Trusted Publisher is configured for `MerverliPy/BenchDeck`. The workflow
  now picks the auth mode at runtime: if the `PYPI_API_TOKEN` repository
  secret is set it is used directly; otherwise the OIDC path runs and the
  step summary prints the exact publisher form fields required on PyPI
  (owner `MerverliPy`, repo `BenchDeck`, workflow `publish.yml`, environment
  `pypi`). See `docs/publish.md` for the full setup of both paths.

## 0.1.2 — 2026-06-13

### Added

- **Self-hosted runner setup runbook.** Complete, executable guide for
  provisioning a Windows 11 + WSL2 Ubuntu host with rootless Docker so
  the `.github/workflows/benchdeck-product-test.yml` workflow can run
  end-to-end. The canonical runbook lives at `docs/runner-setup.md`;
  one-line discoverability pointers are at `RUNNER_SETUP.md` (repo
  root) and `.product-test/runner-setup.md` (test-infra tree). The
  runbook covers 9 phases — pre-flight, WSL2 tuning, rootless Docker
  install, system tools, dedicated runner user lockdown, runner
  install + systemd service + auto-update, first end-to-end workflow
  run, polish (daily health cron, disk-pressure watchdog, evidence
  archive to Windows host, logrotate, WSL2 keepalive Task Scheduler
  entry, re-verification), and optional live OpenAI wiring — with
  per-step `<!-- phase-N: status -->` / `<!-- step-N.M: status -->`
  markers and a one-grep resume command for agents resuming work.
  Targets the kit: Windows 11 host, WSL2 Ubuntu, RTX 4070 (unused
  by the workflow), 48 GB RAM, i7-9xxx CPU. Caps WSL2 at 32 GB;
  concurrency at 2; runner user `benchdeck-runner` (UID 1001) with
  sudo restricted to one command.

- **`scripts/benchdeck-runner-smoke-test.sh`.** Executable one-shot
  boundary check that proves the runner's environment matches what
  the workflow's "Verify controlled runner boundary" step asserts:
  docker reachable, rootless mode reported in `docker info`, `jq`
  installed, and a disposable alpine container with
  `--cap-drop=ALL --read-only --network=none` successfully runs the
  (non-root, no docker.sock, no external network) boundary
  assertions. Returns coloured pass/fail output and a non-zero exit
  code on any failure. Designed to be safe to run repeatedly and
  cheap enough to schedule daily.

- **Optional live OpenAI evidence path documented end-to-end.** Phase
  8 of the runbook covers: minting a dedicated test key with a $5
  hard spend cap, adding it as the `BENCHDECK_TEST_OPENAI_API_KEY`
  repo secret, triggering a live workflow run, and confirming via
  grep that the key never appears in the archived evidence (the
  `sandbox_manager.py` redaction rule on `sk-[A-Za-z0-9_-]{10,}`
  makes that a hard guarantee, not a hope). 90-day key rotation
  cadence documented as a calendar reminder.

## 0.1.1 — 2026-06-13

### Fixed

- **Loader ZIP-safety contract (`SEC-004/005/006`, P2).** `load_snapshot()` and
  `_load_zip_snapshot()` silently returned an empty `Snapshot()` for malformed
  ZIP archives (over the 1000-member cap, over the 256 MiB per-member cap,
  duplicate basenames) instead of raising `ValueError`. The security goal was
  met (no data was loaded) but the error signal was wrong, masking hostile
  input from audit callers. Added a new `strict: bool = False` parameter to
  both functions; the inner `_load_zip_bytes()` now `raise ValueError(...)` for
  the three security-relevant violations and the wrapper re-raises when
  `strict=True`. Default behaviour is preserved for the TUI's resilience path
  (empty snapshot returned, dashboard keeps rendering). JSON-decode failures
  keep the silent fallback because they are not security violations. Three new
  regression tests in `tests/test_loader.py` cover the oversize-member,
  duplicate-basename, and over-cap cases for both default and strict modes.
  Tracked as a re-fix of B1 (the 2026-06-11 entry was incomplete).

### Test infrastructure

- Added the full product-test harness under `.opencode/`, `.product-test/`,
  and `.github/workflows/benchdeck-product-test.yml` so the suite can be
  re-run from a fresh clone. The 2026-06-13 full product test (run id
  `20260613T191610Z-a5e38c42`) is the first run under this harness; full
  report archived at `.test-evidence/20260613T191610Z-a5e38c42/` (gitignored).
- The product-test workflow is `workflow_dispatch` only; trigger it manually
  from the Actions tab when you want a full re-run, optionally with a
  dedicated OpenAI test key as a repo secret to close the `BLOCKED` live
  evidence item.
- Excluded `.opencode/` and `.product-test/` from the product ruff config
  (`extend-exclude` in `pyproject.toml`) so the harness scripts can use a
  different style without breaking the product lint/format gates.

### Verification

- 352 tests pass (2 skipped — pre-existing `OPENAI_API_KEY` conditional skips)
- 81% coverage
- `ruff check`, `ruff format --check`, `mypy src/benchdeck/` all clean
- 2026-06-13 product test: 0 P0, 0 P1, 1 P2 (this fix), 5 P3

## 0.1.0 — 2026-06-10

- Initial benchmark runner and live narrow-terminal TUI.
- Atomic artifact checkpoints.
- Explicit 0-4 scoring scale.
- Empty-response retries and raw response diagnostics.
- Separate policy-block and infrastructure-failure accounting.
- Original benchmark bundle included as a regression fixture.

### Known Issues (resolved post-v0.1.0)

- **ZIP duplicate basename silently overwrites (BUG-3).** Two ZIP entries sharing the same
  basename in different directories result in a silent last-one-wins overwrite rather than
  raising an error. See `REMAINING_ISSUES.md` BUG-3. *(resolved in subsequent patch)*
- **Redundant gate-override dead code in runner (DEAD-6).** `runner.py:_judge_case` contains
  a post-hoc gate-fail assignment that the model validator already enforces. See
  `REMAINING_ISSUES.md` DEAD-6. *(resolved in subsequent patch)*
- **`object.__setattr__` on non-frozen model (STYLE-1).** `CaseJudgment._gate_fail_forces_fail`
  uses `object.__setattr__` for a model that is not frozen. See `REMAINING_ISSUES.md`
  STYLE-1. *(resolved in subsequent patch)*
