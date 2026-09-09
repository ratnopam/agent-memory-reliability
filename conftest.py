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
