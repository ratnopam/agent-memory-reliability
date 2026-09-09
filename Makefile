# One command from a fresh clone: make reproduce.
#
# Every target is a thin wrapper over the `amr` command line, which is the real interface:
# nothing in this repository can only be done by GNU make. See src/amr/__main__.py.
#
# Requires Python 3.11+ and pip. Nothing is vendored. The suite itself needs pytest and
# nothing else; the MCP server needs the official mcp package (the [mcp] extra) and is
# not on the path of any target except `make mcp-test`.
#
# If the ambient interpreter already has pytest, every target uses it and nothing is
# installed or downloaded. Otherwise a local .venv is created on demand, which keeps a
# system Python that refuses installs (PEP 668) from being a problem and never writes
# outside this directory.

PYTHON ?= python3
VENV := .venv
VENV_PY := $(VENV)/bin/python
PY := $(shell if [ -x $(VENV_PY) ]; then echo $(VENV_PY); \
	elif $(PYTHON) -c 'import pytest' >/dev/null 2>&1; then echo $(PYTHON); \
	else echo $(VENV_PY); fi)
SOURCES := src/amr properties systems scenarios examples taxonomy mcp conftest.py
SEED ?= 7

.DEFAULT_GOAL := help
.PHONY: help deps test reproduce determinism demo contamination matrix lint mcp-test clean

help:
	@echo "make test          run the conformance suite"
	@echo "make reproduce     run the suite, write results/<today>/, print the summary"
	@echo "make determinism   run everything twice into temp dirs and compare bytes"
	@echo "make demo          the reference, its matrix, and its one divergence"
	@echo "make contamination the three-role simulation, gated against ungated"
	@echo "make matrix        render results/<today>/raw.json as an SVG table"
	@echo "make lint          ruff or pyflakes if available, otherwise compileall"
	@echo "make mcp-test      the MCP stdio integration test (installs the mcp package)"
	@echo "make clean         remove $(VENV) and caches, and nothing else"
	@echo "interpreter:       $(PY)"

# An editable install is what puts `amr` and the amr.systems entry point in place. The
# fallback is the root conftest.py, which is why `pytest properties/` works in a fresh
# clone with nothing but pytest.
deps:
	@if $(PY) -c 'import pytest' >/dev/null 2>&1; then \
		echo "pytest present in $(PY)"; \
	else \
		echo "creating $(VENV) and installing this package with its test extra"; \
		$(PYTHON) -m venv $(VENV); \
		$(VENV_PY) -m pip install --quiet --upgrade pip; \
		$(VENV_PY) -m pip install --quiet -e ".[test]"; \
	fi

test: deps
	$(PY) -m amr test -v

reproduce: deps
	$(PY) -m amr reproduce

determinism: deps
	$(PY) -m amr determinism

demo: deps
	@$(PY) -m amr demo

contamination: deps
	$(PY) -m amr contamination --seed $(SEED)

matrix: deps
	$(PY) -m amr matrix results/$$(date -u +%Y-%m-%d)/raw.json --svg

lint: deps
	@if $(PY) -c 'import ruff' >/dev/null 2>&1; then \
		$(PY) -m ruff check $(SOURCES); \
	elif $(PY) -c 'import pyflakes' >/dev/null 2>&1; then \
		$(PY) -m pyflakes $(SOURCES); \
	else \
		echo "no ruff, no pyflakes: falling back to compileall"; \
		$(PY) -m compileall -q $(SOURCES); \
	fi

mcp-test: deps
	$(PY) -m pip install --quiet -e ".[mcp]"
	$(PY) -m pytest mcp/ -v

clean:
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
