# Contributing

## Quick start

1. Fork and clone the repository.
2. Create a focused branch.
3. Install with `pip install -e '.[dev]'`.
4. Run `ruff check . && ruff format --check . && mypy src/benchdeck/ tests/ && pytest`.
5. Keep artifact formats backward-compatible or document the migration.
6. Add a regression test for every defect fixed.
7. Open a pull request using the [PR template](.github/PULL_REQUEST_TEMPLATE.md).

## Governance

See [GOVERNANCE.md](GOVERNANCE.md) for decision-making, maintainership,
and how to report security vulnerabilities.

## Code of Conduct

All participants must follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Development conventions

### Python

- Python 3.11+ required.
- Lint with `ruff check .`, format with `ruff format .`, type-check with `mypy src/benchdeck/`.
- Tests live in `tests/` and use pytest.
- `pytest -m "not slow"` skips build-metadata tests.

### Commit messages

- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `refactor:`.
- Reference related issues.

### Release process

See [docs/publish.md](docs/publish.md) for the release workflow and
[GOVERNANCE.md](GOVERNANCE.md) for the tag-and-approve process.
