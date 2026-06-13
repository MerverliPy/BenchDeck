# `.product-test`

Runtime and policy files for the BenchDeck OpenCode product tester.

## Host tools

OpenCode custom tools call:

- `scripts/sandbox_manager.py`
- `scripts/pty_runner.py`
- `scripts/live_benchdeck_run.py`
- `scripts/evidence.py`

## Isolation model

The manager creates an isolated local clone outside the repository, overlays current non-ignored working-tree files, excludes sensitive paths, builds a Python sandbox image, and starts a non-root container on an internal Docker network.

The general container has no internet path. Package installation and live OpenAI testing start a temporary allowlist proxy connected to both the internal network and Docker's external bridge. The product container itself remains internal-only.

## State

Runtime state is stored under:

```text
${BENCHDECK_PRODUCT_TEST_RUNTIME:-$XDG_CACHE_HOME/benchdeck-product-test/<repo-hash>}
```

Evidence is stored under `.test-evidence/` in the source repository so it is easy to review. The supplied gitignore snippet excludes it from commits.

## Direct manual commands

```bash
python3 .product-test/scripts/sandbox_manager.py repo-state
python3 .product-test/scripts/sandbox_manager.py create --python-version 3.12 --install-dependencies
python3 .product-test/scripts/sandbox_manager.py status
python3 .product-test/scripts/sandbox_manager.py exec --command 'pytest -q'
python3 .product-test/scripts/sandbox_manager.py patch
python3 .product-test/scripts/sandbox_manager.py destroy
```
