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

# The same pattern CI greps for. A model client imported anywhere the suite can reach is
# a measurement path with a model in it, whether or not the import is used.
#
# The former-name gate below spells its pattern as two adjacent quoted strings, which the
# shell joins after `eval`. That is not decoration: written whole, this line would be the
# match, and a gate that fails on itself teaches whoever hits it to disable the gate.
LLM_IMPORT := \b(import|from)[[:space:]]+(anthropic|openai|cohere|litellm|langchain|transformers)\b

.DEFAULT_GOAL := help
.PHONY: help deps test reproduce determinism demo contamination matrix drift lint \
	release-check mcp-test clean

help:
	@echo "make test          run the conformance suite"
	@echo "make reproduce     run the suite, write results/<today>/, print the summary"
	@echo "make determinism   run everything twice into temp dirs and compare bytes"
	@echo "make demo          the reference, its matrix, and its one divergence"
	@echo "make contamination the three-role simulation, gated against ungated"
	@echo "make matrix        render results/<today>/raw.json as an SVG table"
	@echo "make drift         does README.md render the committed matrix?"
	@echo "make lint          ruff or pyflakes if available, otherwise compileall"
	@echo "make release-check every gate, in order, one line each: run this before a tag"
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

drift: deps
	@$(PY) -m amr drift

lint: deps
	@if $(PY) -c 'import ruff' >/dev/null 2>&1; then \
		$(PY) -m ruff check $(SOURCES); \
	elif $(PY) -c 'import pyflakes' >/dev/null 2>&1; then \
		$(PY) -m pyflakes $(SOURCES); \
	else \
		echo "no ruff, no pyflakes: falling back to compileall"; \
		$(PY) -m compileall -q $(SOURCES); \
	fi

# Every gate that has to be green before a tag, in one command. The suite runs first
# because a failure there is the cheapest to read, and the greps run last because they are
# the ones nobody remembers. One line per gate; the first red gate stops the run and prints
# the tail of its output. Green here is the precondition for docs/RELEASE.md.
#
# The two gates that produce results write outside the working tree. Running the gates must
# not modify the repository: a checklist step that leaves the tree dirty gets `git checkout`ed
# away by hand, and the next thing to be discarded by hand is something that mattered. The
# committed results are regenerated deliberately, by `make reproduce`, and the drift gate
# below reads what is committed rather than what a gate just produced.
release-check: deps
	@log=$$(mktemp); out=$$(mktemp -d); trap 'rm -rf $$log $$out' EXIT; \
	gate() { \
		printf '%-34s' "$$1"; \
		if eval "$$2" >$$log 2>&1; then \
			echo "ok"; \
		else \
			echo "FAILED"; echo; echo "\$$ $$2"; tail -n 30 $$log; exit 1; \
		fi; \
	}; \
	gate "conformance suite" "$(PY) -m amr test -q"; \
	gate "results regenerated" "$(PY) -m amr reproduce --quiet --out $$out"; \
	gate "determinism" "$(PY) -m amr determinism"; \
	gate "contamination simulation" "$(PY) -m amr contamination --seed $(SEED) --quiet --out $$out"; \
	gate "lint" "$(MAKE) --no-print-directory lint"; \
	gate "reference is stdlib only" "$(PY) .github/check_stdlib_only.py"; \
	gate "no LLM in the measured path" "! grep -rniE '$(LLM_IMPORT)' --include='*.py' $(SOURCES)"; \
	gate "no former name in the tree" "! git grep -i -q -e 'mem''ledger'"; \
	gate "README renders the matrix" "$(PY) -m amr drift"; \
	gate "documentation links resolve" "$(PY) .github/check_links.py"; \
	echo "release-check: ten gates, all green"

mcp-test: deps
	$(PY) -m pip install --quiet -e ".[mcp]"
	$(PY) -m pytest mcp/ -v

clean:
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
