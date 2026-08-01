"""The one place `strider` reaches `../ugm`'s microfunctions engine.

A single import surface, so a change upstream touches one file here rather than every module. That paid
off immediately: this file previously carried a `sys.path` fix, because `microfunctions` was missing from
ugm's `pyproject` `packages` and so — unlike `ugm` — was not importable from an install. We reported it
(`docs/feedback_microfunctions.md` §1), ugm shipped it, and **verified against a real wheel rather than an
editable install**, which would have resolved from source and proved nothing. The workaround is gone and
nothing else in `strider` had to know it ever existed.
"""
from __future__ import annotations

from microfunctions import asm, conflict, dispatch, driver, function, goal, loop, types
from microfunctions.focus import Focus
from microfunctions.graph import Graph, new_graph
from microfunctions.isa import Machine

__all__ = ["asm", "conflict", "dispatch", "driver", "function", "goal", "loop", "types",
           "Focus", "Graph", "Machine", "new_graph"]
