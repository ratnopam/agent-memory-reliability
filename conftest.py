"""Make ``amr``, ``systems``, ``properties``, and ``scenarios`` importable from a checkout.

``pip install -e .` is the supported way in (see pyproject.toml). This file is the
fallback, so ``pytest`` in a fresh clone works with nothing installed but pytest itself:
the repository root carries the root packages, ``src/`` carries ``amr``.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for path in (ROOT, os.path.join(ROOT, "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

#: ``properties/test_external_adapter_example.py`` and ``test_persistent_system.py`` run
#: the whole suite in a subprocess to measure a system. That subprocess sets
#: ``AMR_NESTED_RUN``, and these files are not collected there, because a run that collects
#: them starts another run, forever. Ignored rather than skipped: a skip is counted as a
#: FAIL (src/amr/runner.py), and the inner run's own totals are what the outer test asserts
#: on.
collect_ignore = []
if os.environ.get("AMR_NESTED_RUN"):
    collect_ignore += [
        os.path.join("properties", "test_external_adapter_example.py"),
        os.path.join("properties", "test_persistent_system.py"),
    ]
