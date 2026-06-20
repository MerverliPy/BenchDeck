.PHONY: install test lint format format-check typecheck check fixture
install:
	python -m pip install -e '.[dev]'

test:
	python -m pytest --cov=src/benchdeck --cov-report=term-missing

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

typecheck:
	python -m mypy --no-incremental src/benchdeck

check: format-check lint typecheck test
	@echo "All checks passed."

fixture:
	benchdeck inspect fixtures/original_run.zip
