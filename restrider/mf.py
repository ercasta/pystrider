"""The one place `restrider` reaches the engine.

The single-import-surface bet, taken a third time. It paid off twice on the last
generation — once when ugm shipped a packaging fix and the `sys.path` workaround
vanished from one file, once when `microfunctions` was renamed to `ugm` and the
whole package moved on four lines. It has now paid off a third time: `restart`
was merged and this file is where that was absorbed.

⚠⚠ **`restart` IS `main` NOW — DO NOT CHECK OUT `restart`.** Upstream merged it
on 2026-08-20 and kept developing on `main`; the `restart` branch has not moved
since `4df154f attention` (2026-08-16) and is **77 commits stale**. The previous
version of this file told a reader that resolving an engine on `main` meant they
had the WRONG one, which is now exactly inverted — following that advice lands
you on the stale branch, and a stale engine answers rather than erroring.

    ../ugm            branch `main`  — engine 3, what THIS package is written for
    ../ugm-classic    branch `main`  — engine 2, what `pystrider/` is written for

⚠⚠ AND THE OLDER WARNING STANDS, BECAUSE IT IS ABOUT NAMES, NOT BRANCHES: TWO
ENGINES NAMED `ugm` CAN EXIST ON ONE MACHINE, AND `import ugm` RESOLVES TO
WHICHEVER ONE THE PROCESS FOUND FIRST.

Where `ugm-classic` is installed editable, `import ugm` is *pystrider's* engine
by default and this file reaches past it by path. Which means:

> **`restrider` and `pystrider` CANNOT SHARE A PROCESS.** Importing this module
> re-points `ugm` for everything that imports it afterwards.

That is not a limitation to work around; it is a fact to make loud. `tests/` and
`tests_restart/` are therefore separate pytest invocations, and both `mf.py` files
assert which engine they got. A silent cross-wiring would not show up as an import
error — it would show up as an engine answering questions it was never asked,
which is survey §0's trap in its most expensive form.

⚠ On a machine with no `ugm-classic` at all the guard below is guarding a
collision that cannot happen — which is the right state for it to be in. It costs
one `in` test and it is the only thing standing between a two-engine machine and
a wrong reading, so it stays until `pystrider/` is retired for cause.
"""
from __future__ import annotations

import os
import sys


def _resolve() -> str:
    """Where the engine lives. ⚠ If it moves, it moves HERE and nowhere else.

    `UGM_RESTART` wins outright. Otherwise: walk up from this file and try each
    ancestor's siblings, because the checkout is `Universal-Graph-Machine` on
    some machines and `ugm` on others while the docs call it `../ugm` throughout
    — and because a git worktree puts this file several levels below the sibling
    a plain `../ugm` would name.

    ⚠ A candidate counts only if it actually holds `ugm/__init__.py`. An empty
    directory that merely has the right name would otherwise shadow a real
    checkout further down the list and fail as a missing attribute much later.
    """
    env = os.environ.get("UGM_RESTART")
    if env:
        return env
    here = os.path.abspath(os.path.dirname(__file__))
    seen = []
    while True:
        parent = os.path.dirname(here)
        for name in ("Universal-Graph-Machine", "ugm"):
            cand = os.path.join(parent, name)
            seen.append(cand)
            if os.path.isfile(os.path.join(cand, "ugm", "__init__.py")):
                return cand
        if parent == here:
            break
        here = parent
    raise ImportError(
        "cannot find the ugm engine. Set UGM_RESTART to the checkout — note it "
        "must be on `main`, NOT the stale `restart` branch. Tried:\n  "
        + "\n  ".join(seen)
    )


#: Resolved once, at import, so a probe can print it rather than guess.
UGM_RESTART = _resolve()


def _engine():
    """Import the engine by path, and refuse the wrong one loudly."""
    if "ugm" in sys.modules:
        # Somebody imported the other one first. Say so now, with both paths, in
        # the one place that can tell — by the time a caller sees a missing
        # attribute the trail is cold.
        already = getattr(sys.modules["ugm"], "__file__", "?")
        if "ugm-classic" in already:
            raise ImportError(
                f"`ugm` is already imported from {already} — that is ENGINE 2, which "
                f"`pystrider/` uses. `restrider` needs engine 3 and the two cannot "
                f"share a process. Run `tests_restart/` in its own pytest invocation."
            )
    sys.path.insert(0, UGM_RESTART)
    import ugm

    if "ugm-classic" in (ugm.__file__ or ""):
        raise ImportError(
            f"expected engine 3, resolved {ugm.__file__} — that is `ugm-classic`, "
            f"which is engine 2. Either UGM_RESTART points at the wrong checkout, "
            f"or the cwd is inside a sibling repo and its local package won "
            f"(survey §0). ⚠ Being on `main` is CORRECT and is not the fault here."
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
