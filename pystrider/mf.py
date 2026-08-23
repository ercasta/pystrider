"""The one place `pystrider` reaches `../ugm`'s engine.

The single-import-surface bet, and it has now paid off four times: a packaging fix,
the `microfunctions`→`ugm` rename, the `restart` rewrite, and the scratchpad collapse
below. Each time the whole package moved on the lines at the bottom of this file.

⚠ So imports here rather than in the module that wants them, even for a one-off in a
test: a direct `from ugm import …` anywhere else is the chokepoint quietly ceasing to
be one, and it will not announce itself until the next upstream rename.

## 2026-08-23 — ONE engine again

The two-engine era is over. This package absorbed `restrider/` and the engine-2
`pystrider/` was deleted, so nothing coexists any more; the
`ugm-classic` worktree is no longer anyone's dependency, and the loud machinery that
used to live here — refusing the wrong `ugm` by path, asserting which one a process
got — went with it. `docs/transplant.md` records what that cost and what is owed.

⚠ The install still resolves `ugm` by whatever the process finds first, and a sibling
checkout can still win over an install (survey §0's trap). So this file still ASSERTS
what it got, just against a much simpler expectation: an engine that has the names
below. A wrong engine now fails here, on import, by name.

## ⚠⚠ THE TRAP THIS ENGINE CARRIES, and it is not an import error

**THERE IS NO INERT SET.** An application that changed nothing is offered again, so a
rule that does not stop itself never stops. The symptom is not a crash and not an
empty result — it is a run that burns its whole step budget re-applying the FIRST
applicable rule with `wrote=()` while every later rule never fires, and every reader
downstream then answers honestly about a graph nothing was ever written to.

Measured on the port: `run()` spent all 4000 steps re-applying `<conditional>` while
`<guard-of>` — both premises present, one conclusion missing — never ran once, and the
evaluator truthfully reported *no guard* about a function whose guard was plainly
there. Adding `no <own head>` as a premise to all ten rules took the suite from 21 to
33 passing and the run from 12s to 0.9s.

**So: every rule in `rules/*.ugm` carries a `no <its own conclusion>` premise, and a
new rule without one is a hang, not a bug.** Upstream states this deliberately — see
`../ugm/ugm/rules/bundle.ugm`: *"`no says(...)` is the whole of the stopping, and it is
a premise — readable, overridable, and wrong out loud if it is wrong."*
"""
from __future__ import annotations

import os
import sys

#: Where the engine lives, when it is not installed. A path rather than an assumption,
#: because this project has been wrong about which `ugm` it was talking to before.
#: ⚠ If it moves, it moves here and nowhere else.
UGM = os.environ.get("UGM", r"C:\Users\ercas\creazioni\ugm")

if UGM and os.path.isdir(UGM):
    sys.path.insert(0, UGM)

import ugm  # noqa: E402

#: What this package is written against: the scratchpad engine. Named as a set rather
#: than discovered by an AttributeError three frames into a run.
_EXPECTED = ("ASSERT", "ERASE", "Graph", "Machine", "Rule", "RuleSet", "Scratchpad")
_missing = [n for n in _EXPECTED if not hasattr(ugm, n)]
if _missing:
    raise ImportError(
        f"`ugm` resolved to {ugm.__file__}, which is missing {', '.join(_missing)} — "
        f"that is not the scratchpad engine this package is written for. Either the "
        f"checkout at {UGM} is on an older branch, or the cwd is inside a sibling "
        f"repo whose local package won."
    )

from ugm import ASSERT, ERASE, Graph, Machine, Rule, RuleSet  # noqa: E402
from ugm.core.text import Loader, load  # noqa: E402

#: The path this resolved to, so a probe can PRINT which engine it measured rather
#: than assert it and hope.
ENGINE = ugm.__file__

__all__ = ["ASSERT", "ENGINE", "ERASE", "Graph", "Loader", "Machine", "Rule", "RuleSet",
           "load"]
