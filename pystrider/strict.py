"""Run a loop the way a derivation needs, not the way a shared prompt does.

⚠⚠ 2026-08-29: `loopingrules.Loop.run()` CATCHES a rule that raises, records it
on `loop.errors`, and moves on — right for a shared prompt (a typo in one
domain must not take a person's REPL down with it), wrong for a one-shot
derivation, where a rule that raised did not fire, so the world settles
*looking* quiescent while the conclusion it owed is simply absent. That
silence is exactly the shape of bug this project has repeatedly measured and
paid for. The old `Facts.run()` re-raised for this reason; `Facts` is gone,
so this is what a batch caller reaches for instead — `demos.playground.brew.
reason()`'s own private, one-shot `Loop` (what `pystrider.domain`'s `_brew`/
`_why` both run through) is exactly that caller.

⚠⚠ 2026-08-30: `_read` is NOT this any more. It used to be, but moved onto
the SHARED loop (see `pystrider.domain`'s own docstring, "the SHARED
world") — a persistent domain's rules running every tick for the life of
the session are exactly the "wrong for a REPL" case above, not the
one-shot case this module exists for; a rule of `patterns`'s that raised
once should not crash the whole prompt over it. Cite `_brew`/`_why` here
from now on, not `_read`.
"""
from __future__ import annotations

from typing import Optional


def run(loop, budget: Optional[int] = None):
    """`loop.run()`, except a rule that raised is RE-RAISED here, and a world
    that never settled is too."""
    settled = loop.run(budget=budget)
    if loop.errors:
        name, error = loop.errors[0]
        raise RuntimeError(
            f"the rule {name!r} raised, so whatever it concludes is missing "
            f"from a world that otherwise looks settled: {error!r}"
        ) from error
    if settled.hot:
        raise RuntimeError(
            f"the world did not settle in {settled.ticks} ticks — still firing: "
            f"{', '.join(settled.hot)}. Two rules are feeding each other, or "
            f"one concludes something it cannot recognise as already concluded."
        )
    return settled
