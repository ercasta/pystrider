"""The one place `strider` reaches `../ugm`'s microfunctions engine.

`microfunctions` is not in ugm's `pyproject` (`packages = ["ugm", "ugm.cnl", "units"]`), so unlike `ugm`
it is not importable from an install. Rather than let every module re-invent a path fix, it is done once
here and everything else imports from this module — which also means that when ugm ships it properly,
exactly one file changes.

⚠ FEEDBACK FOR ../ugm: if `microfunctions` is to be the substrate, it needs to ship in `packages`.

The path is derived from the *installed* `ugm` package's repo root, not from a relative guess about how
the checkouts sit next to each other, so it survives a different working layout.
"""
from __future__ import annotations

import sys
from pathlib import Path

import ugm as _ugm

UGM_REPO = Path(_ugm.__file__).resolve().parents[1]
if str(UGM_REPO) not in sys.path:
    sys.path.insert(0, str(UGM_REPO))

from microfunctions import asm, conflict, driver, function, goal, types  # noqa: E402
from microfunctions.graph import Graph, new_graph                        # noqa: E402

__all__ = ["UGM_REPO", "asm", "conflict", "driver", "function", "goal", "types", "Graph", "new_graph"]
