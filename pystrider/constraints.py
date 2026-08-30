"""Architectural constraints — the SAME shape `patterns.py` describes
structure with, pointed at a JUDGMENT instead of a neutral description:

    forwards   description  =>  violation   -- RECOGNIZE a forbidden shape

`patterns.py`'s whole discipline — forward-chained, off structure already in
`w`, deposited as its own component rather than computed inline and thrown
away — carries over unchanged. What's different is only the vocabulary a
rule concludes in: `Iteration`/`Choice`/`Applies`/`LoopCount` describe what
something IS; a constraint describes that something IS NOT ALLOWED, given a
rule someone authored. Nothing about the engine cares about that distinction
— a rule here is not privileged, arbitrated, or run any differently from one
in `patterns.py`. It is a person's own opinion, made a rule the same way any
other description is.

⚠ This is a PROTOTYPE, one constraint deep, on purpose (this project's own
"do one concretely first" rule — see `docs/TODO.md` thread 1's own note on
why). Two things are deliberately simplified rather than designed properly,
and both are named, not hidden:

1. **The threshold is a module CONSTANT, not a policy someone states.**
   `MAX_LOOPS` is one number, hardcoded — a real constraint wants its limit
   to be something a person or a config sets (per-project, maybe per-
   function), which is a genuine design question (where does that live —
   a durable, singular component like `Session`? per-function?) this
   prototype does not answer. Answering it is what a SECOND constraint
   would force into the open — see this module's own docstring precedent
   in `patterns.py`: generalize only once there's a second instance to
   check the generalization against.

2. **Not wired into the live prompt.** No `why`-style verb in `domain.py`
   asks about a `TooManyLoops` fact yet — the fact is real, deposited,
   and inspectable (`w.get(function, TooManyLoops)`, `w.show(function)`,
   `loop.trace` if tracing is on), but nothing in this repo currently
   surfaces it to a person typing at a prompt, the same honestly-named gap
   `repair.py`'s own "Where this goes next" already carries for a
   different feature.
"""
from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient
from pystrider.intake import Function
from pystrider.patterns import LoopCount

#: The one number this prototype hardcodes — see the module note, point 1.
MAX_LOOPS = 2


@transient
@dataclass(frozen=True)
class TooManyLoops:
    """A `Function` violates the max-loops constraint. `count` is what
    `LoopCount` said; `limit` is `MAX_LOOPS` at the moment THIS fact was
    derived — carried on the component itself, not left implicit in the
    module constant, so an already-deposited fact stays honest about what
    it was actually checked against even if `MAX_LOOPS` changes later in
    the same process (the constant is mutable Python state; the component
    is not).

    `@transient`, same as `LoopCount` and everything it is built from — a
    claim about ONE `intake()`'s entities, gone with them."""

    count: int
    limit: int


def max_loops(w) -> None:
    """`LoopCount(n)` where `n > MAX_LOOPS`  ->  `TooManyLoops(n, MAX_LOOPS)`.

    ⚠ Reads `LoopCount`, never counts anything itself — `patterns.
    loop_count` must already have run, the same dependency `iteration()`
    has on `intake.py`'s `ForStmt`/`Target`/`Iterated`/`Body` already
    existing. Nothing here resolves a stable key or triggers a reread the
    way `pystrider.domain._reconcile_watch` does, so the "resolved but not
    derived YET" wait that rule needs does not apply to this one — this
    rule only ever looks at what is already in `w`.
    """
    for entity, _fn, count in w.each(Function, LoopCount, without=TooManyLoops):
        if count.count > MAX_LOOPS:
            w.attach(entity, TooManyLoops(count.count, MAX_LOOPS))


#: ⭐ Same shape as `patterns.DESCRIPTIONS` — one entry today, room for a
#: second without reworking `install()`.
CONSTRAINTS = {"max_loops": max_loops}


def install(loop, only=None) -> None:
    """Register the constraints. `only` names a subset, same as
    `patterns.install`. ⚠ Does NOT install `patterns` itself — a caller
    wanting `max_loops` to derive anything also needs `patterns.install`
    (or at least `patterns.loop_count`) on the SAME loop; see `max_loops`'s
    own docstring on why."""
    for name, make in CONSTRAINTS.items():
        if only is None or name in only:
            loop.rule(make, name=f"constraints.{name}")
