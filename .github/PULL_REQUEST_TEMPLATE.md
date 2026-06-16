## What changed

Brief description of the change and why.

## Checklist

- [ ] Tests added or updated for the change
- [ ] All existing tests pass (`pytest tests/ -q`)
- [ ] Lint and type checks pass (`ruff check .`, `ruff format --check .`, `mypy src/benchdeck/ tests/`)
- [ ] Documentation updated if needed (`docs/`, `README.md`, `CHANGELOG.md`)
- [ ] Security impact assessed:
  - No new credential paths introduced
  - No confidential data in logs or outputs
  - Configuration changes do not silently weaken constraints
- [ ] Backward compatibility:
  - CLI commands and flags unchanged unless documented
  - Artifact format unchanged unless migration documented
  - TUI behavior unchanged for default invocation
- [ ] Evidence attached (test output, coverage diff, manual verification notes)
- [ ] Release implications documented (version bump, migration note, feature flag)
