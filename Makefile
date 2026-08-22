PYTHON ?= python
RUFF ?= ruff

.PHONY: wheels release test lint format

wheels:
	$(PYTHON) -m build --wheel

release:
	twine upload dist/*

test:
	$(PYTHON) -m unittest discover -s tests

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) check . --fix
	$(RUFF) format .
