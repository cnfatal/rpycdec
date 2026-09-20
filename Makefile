PYTHON ?= python
RUFF ?= ruff

.PHONY: wheels release test test-corpus lint format

wheels:
	$(PYTHON) -m build --wheel

release:
	twine upload dist/*

test:
	$(PYTHON) -m unittest discover -s tests

# decompile and recompile every script the SDKs ship, needs sdks/ and a while
test-corpus:
	RPYCDEC_CORPUS=1 $(PYTHON) -m unittest tests.test_corpus -v

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) check . --fix
	$(RUFF) format .
