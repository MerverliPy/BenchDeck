---
name: no-mock-live-validation
description: Prevents mocks, fakes, scripted responses, route interception, or simulated services from being treated as proof of live product behavior
license: MIT
compatibility: opencode
metadata:
  policy: no-mock-product-pass
---

## Rule

Do not create mocks or fabricated service behavior for product-level validation.

Existing tests using mocks/fakes may run and remain valuable, but classify them as `SIMULATED_REGRESSION_EVIDENCE`.

## Live-pass requirements

- CLI: actual installed executable as a subprocess.
- TUI: actual curses process under a PTY.
- Files/artifacts: actual writes and reads in the disposable workspace.
- Provider behavior: actual approved OpenAI request with a dedicated test key.
- Network failure: actual blocked/disconnected path, not a fabricated HTTP response.
- Process failure: actual signal, timeout, malformed input, or unavailable dependency.
- Platform behavior: actual runner for that platform.

## Blocked rule

When a real dependency cannot be provisioned safely, use a precise blocked status. Never replace it with a fake and never imply the feature passed.
