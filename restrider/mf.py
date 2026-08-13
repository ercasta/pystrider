"""The one place `restrider` reaches `../ugm@restart`'s engine.

The single-import-surface bet, taken a third time. It paid off twice on the last
generation — once when ugm shipped a packaging fix and the `sys.path` workaround
vanished from one file, once when `microfunctions` was renamed to `ugm` and the
whole package moved on four lines.

⚠⚠ AND IT CARRIES SOMETHING NEW, WHICH IS THE POINT OF READING THIS FILE: TWO
ENGINES NAMED `ugm` NOW EXIST ON THIS MACHINE, AND `import ugm` RESOLVES TO
WHICHEVER ONE THE PROCESS FOUND FIRST.

    ../ugm            branch `restart`  — engine 3, what THIS package is written for
    ../ugm-classic    branch `main`     — engine 2, what `pystrider/` is written for

The editable install points at `ugm-classic`, so `import ugm` is *pystrider's*
engine by default and this file reaches past it by path. Which means:

> **`restrider` and `pystrider` CANNOT SHARE A PROCESS.** Importing this module
> re-points `ugm` for everything that imports it afterwards.

That is not a limitation to work around; it is a fact to make loud. `tests/` and
`tests_restart/` are therefore separate pytest invocations, and both `mf.py` files
assert which engine they got. A silent cross-wiring would not show up as an import
error — it would show up as an engine answering questions it was never asked,
which is survey §0's trap in its most expensive form.
"""
from __future__ import annotations

import os
import sys

#: Where `restart` lives. A path rather than an install, because the install is
#: the other engine. ⚠ If this moves, it moves here and nowhere else.
UGM_RESTART = os.environ.get("UGM_RESTART", r"C:\Users\ercas\creazioni\ugm")


def _engine():
    """Import `restart` by path, and refuse the wrong engine loudly."""
    if "ugm" in sys.modules:
        # Somebody imported the other one first. Say so now, with both paths, in
        # the one place that can tell — by the time a caller sees a missing
        # attribute the trail is cold.
        already = getattr(sys.modules["ugm"], "__file__", "?")
        if "ugm-classic" in already:
            raise ImportError(
                f"`ugm` is already imported from {already} — that is ENGINE 2, which "
                f"`pystrider/` uses. `restrider` needs `restart` and the two cannot "
                f"share a process. Run `tests_restart/` in its own pytest invocation."
            )
    sys.path.insert(0, UGM_RESTART)
    import ugm

    if "ugm-classic" in (ugm.__file__ or ""):
        raise ImportError(
            f"expected the `restart` engine, resolved {ugm.__file__}. Either "
            f"{UGM_RESTART} is checked out on `main`, or the cwd is inside a "
            f"sibling repo and its local package won (survey §0)."
        )
    return ugm


_ugm = _engine()

from ugm import PLUS, MINUS, Graph, Machine, Rule, RuleSet  # noqa: E402
from ugm.text import load  # noqa: E402
from ugm.text import Loader  # noqa: E402

#: The path this resolved to, so a probe can PRINT which engine it measured
#: rather than assert it and hope.
ENGINE = _ugm.__file__

__all__ = ["ENGINE", "Graph", "Loader", "Machine", "MINUS", "PLUS", "Rule", "RuleSet", "load"]
