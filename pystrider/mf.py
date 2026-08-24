"""The one place `pystrider` reaches `../ugm`'s engine.

A single import surface, so a change upstream touches one file here rather than every module. It has
paid off four times now: when ugm shipped a packaging fix and a `sys.path` workaround vanished from one
file; when `microfunctions` was renamed to `ugm` and the whole package moved on four lines; when the port
to `restart` needed a second engine reachable by path; and — below — when that second engine stopped
existing and the whole apparatus collapsed back to six ordinary imports.

## ⚠ THE TWO-ENGINE DANCE IS OVER, AND THAT IS WHY THIS FILE SHRANK

This module used to reach *past* an editable install by path, because two engines were installed under
the name `ugm` and `import ugm` resolved to whichever the process found first. It carried a refusal for
`ugm-classic`, and `tests/` and `tests_restart/` had to be separate pytest invocations.

**None of that is true any more.** Upstream deleted the engine-2 floor deliberately — ugm's `CLAUDE.md`
says so: *"The previous implementation (`ugm/`, ~30k lines, 46 modules) and all other docs were deleted
deliberately, not lost. They implemented a different floor — an ISA with opcodes and registers — which
the design in `rules-design.md` rejects."* There is one engine, it is this one, and `pystrider/` is
written for it. The refusal, the path insertion and the split suites all went with the retirement.

⚠ What did NOT go is the reason the chokepoint exists. A direct `from ugm import …` anywhere else is the
chokepoint quietly ceasing to be one, and it will not announce itself until the next upstream rename.

## `UGM_PATH` — for measuring against a branch, not for finding the engine

By default this imports the installed `ugm` like any other dependency. Set `UGM_PATH` to a checkout to
measure `pystrider` against a ugm *worktree* — an unmerged branch, or a bisect — without reinstalling:

    UGM_PATH=../Universal-Graph-Machine/.claude/worktrees/some-branch python -m pytest tests/ -q

⚠ It prepends to `sys.path`, so it re-points `import ugm` for the whole process. That is the point, and
it is also why `ENGINE` is exported: a probe should PRINT which engine it measured rather than assume.
"""
from __future__ import annotations

import os
import sys

#: An optional checkout to measure against, INSTEAD of the installed package. Empty means "the install",
#: which is the ordinary case. ⚠ If this moves, it moves here and nowhere else.
UGM_PATH = os.environ.get("UGM_PATH") or os.environ.get("UGM_RESTART") or ""

if UGM_PATH:
    if "ugm" in sys.modules:
        # Somebody imported it before we could re-point it. Say so now, with both paths, in the one
        # place that can tell — by the time a caller sees a surprising answer the trail is cold.
        raise ImportError(
            f"UGM_PATH={UGM_PATH} was set, but `ugm` is already imported from "
            f"{getattr(sys.modules['ugm'], '__file__', '?')}. Import `pystrider.mf` first, or unset it."
        )
    sys.path.insert(0, os.path.abspath(os.path.expanduser(UGM_PATH)))

import ugm  # noqa: E402

try:
    from ugm import PLUS, MINUS, Graph, Machine, Rule, RuleSet  # noqa: E402
    from ugm.text import load  # noqa: E402
    from ugm.text import Loader  # noqa: E402
except ImportError as exc:  # pragma: no cover — the one failure worth a sentence of its own
    # The engine-2 floor exported none of these. If someone resolves an old checkout, the bare
    # `cannot import name 'Rule'` sends them looking in the wrong repository.
    raise ImportError(
        f"`ugm` at {ugm.__file__} does not export the rules floor `pystrider` is written for "
        f"({exc}). Engine 2 — the ISA with opcodes and registers — was deleted upstream on purpose; "
        f"this package needs the `rules-design.md` floor. Check out a ugm that has `ugm/rules.py`."
    ) from exc

#: The path this resolved to, so a probe can PRINT which engine it measured rather than assert it
#: and hope. ⚠ Upstream moves fast — several branches are usually live at once.
ENGINE = ugm.__file__

__all__ = ["ENGINE", "Graph", "Loader", "Machine", "MINUS", "PLUS", "Rule", "RuleSet", "load"]
