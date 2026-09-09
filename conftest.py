"""Put the repository root on ``sys.path`` so ``harness`` and ``systems`` import.

Deliberately the only packaging in the repository. There is nothing to install.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
