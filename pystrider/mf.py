"""The one place `pystrider` reaches `../ugm`'s engine.

A single import surface, so a change upstream touches one file here rather than every module. That paid
off immediately: this file previously carried a `sys.path` fix, because `microfunctions` was missing from
ugm's `pyproject` `packages` and so — unlike the old `ugm` package — was not importable from an install.
We reported it (`docs/feedback_microfunctions.md` §1), ugm shipped it, and **verified against a real wheel
rather than an editable install**, which would have resolved from source and proved nothing. The
workaround is gone and nothing else in `pystrider` had to know it ever existed.

⭐ It paid off a second time on 2026-08-02, when ugm's restructuring **renamed `microfunctions` to `ugm`**,
the old engine of that name having been retired. The whole of `pystrider` moved on the four lines below.

⚠ So imports here rather than in the module that wants them, even for a one-off in a test: a direct
`from ugm import …` anywhere else is the chokepoint quietly ceasing to be one, and it will not announce
itself until the next upstream rename."""
from __future__ import annotations

from ugm import (asm, conflict, dispatch, driver, execution, function, goal, loop, thread, types,
                 workbench)
from ugm.focus import Focus
from ugm.graph import Graph, new_graph
from ugm.isa import Machine

__all__ = ["asm", "conflict", "dispatch", "driver", "execution", "function", "goal", "loop", "thread",
           "types", "workbench", "Focus", "Graph", "Machine", "new_graph"]
