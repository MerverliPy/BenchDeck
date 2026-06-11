.PHONY: install test lint fixture
install:
	python -m pip install -e '.[dev]'

test:
	pytest

lint:
	ruff check .

fixture:
	benchdeck inspect fixtures/original_run.zip
