# One command from a fresh clone: make reproduce.
#
# Requires Python 3.11+ and pip. Nothing is vendored. The suite itself needs pytest and
# nothing else; the MCP server needs the official mcp package and is not on the path of
# any target except `make mcp-test`.
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
SOURCES := harness properties systems taxonomy mcp conftest.py

.DEFAULT_GOAL := help
.PHONY: help deps test reproduce determinism lint mcp-test clean

help:
	@echo "make test          run the conformance suite"
	@echo "make reproduce     run the harness, write results/<today>/, print the summary"
	@echo "make determinism   run reproduce twice into temp dirs and compare bytes"
	@echo "make lint          ruff or pyflakes if available, otherwise compileall"
	@echo "make mcp-test      the MCP stdio integration test (installs the mcp package)"
	@echo "make clean         remove $(VENV) and caches, and nothing else"
	@echo "interpreter:       $(PY)"

deps:
	@if $(PY) -c 'import pytest' >/dev/null 2>&1; then \
		echo "pytest present in $(PY)"; \
	else \
		echo "creating $(VENV) and installing requirements-dev.txt"; \
		$(PYTHON) -m venv $(VENV); \
		$(VENV_PY) -m pip install --quiet --upgrade pip; \
		$(VENV_PY) -m pip install --quiet -r requirements-dev.txt; \
	fi

test: deps
	$(PY) -m pytest properties/ -v

reproduce: deps
	$(PY) -m harness reproduce

determinism: deps
	$(PY) -m harness determinism

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
	$(PY) -m pip install --quiet -r requirements-mcp.txt
	$(PY) -m pytest mcp/ -v

clean:
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
