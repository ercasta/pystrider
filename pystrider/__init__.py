"""`pystrider` — reading and writing Python by reasoning, on `../ugm`.

**THE BET, unchanged across four engines:** one authored description, read one way
RECOGNIZES code, read the other way WRITES it. What changed each time is what the
substrate lets a description be.

    engine 1  `ugm` classic      a CNL rule's BODY recognizes, its HEAD writes
    engine 2  `microfunctions`   pattern matching deleted, so `driver.establishes`
                                 reconstructed the duality from a function's body
                                 versus its effects
    engine 3  `restart`          pattern-matching rules are back, AND a backward
                                 reader over the same rules ships. This package was
                                 written here
    engine 4  the scratchpad     one graph that IS the state. The forward half is
                                 untouched; the BACKWARD reader went into the engine's
                                 bin and has to be re-authored in `rules/`

⭐ The forward half is native on this floor and stays native: an antecedent is
literally what `driver.establishes` spent engine 2 reconstructing.

⚠⚠ **The backward half is currently a debt, not a feature.** `Machine.why` and the
whole goal apparatus (`GOAL`, `SUBGOAL`, `backward.py`, `Machine.focus`) were deleted
upstream on the way to the scratchpad, and goal management is now something a corpus
authors for itself (`../ugm/ugm/rules/bundle.ugm` is the worked example). Nine tests
are `xfail(strict=True)` against exactly that, so the day it is authored they XPASS
rather than staying quietly green.

## Where the reach went, and what is owed

This package absorbed `restrider/` on 2026-08-23 and the engine-2 `pystrider/` was
deleted the same day. That was a decision to stop maintaining a private fork of a dead
engine, **not** a claim that this one caught up: measured on one corpus that day,
engine 2 round-tripped **68.3 %** of 587 functions and this package round-trips
**3.1 %**, both with UNSTABLE 0.

⭐ The gap is collectable rather than lost. Engine 2's 923-line `intake.py` + `emit.py`
— the entirety of what produced the 68.3 % — imported `ast` and nothing else, and the
whole engine surface they touched was seven graph methods that `facts.py` already
offers under other names. **`docs/transplant.md` holds the measurement, the runner,
and the git ref to lift them from.** It is written down precisely because this project
has already once deleted the artifact holding the measurement in the same commit that
took the decision it gated.

> The bar: re-run `experiments/pystrider_reach.py`. It must clear 68.3 % with UNSTABLE
> still 0 before this repo reads as much Python as it did on 2026-08-23.

## ⚠ THE TRAP THIS ENGINE CARRIES — read `mf.py` before authoring a rule

There is no inert set. A rule without a `no <its own conclusion>` premise re-fires for
ever, and the symptom is a silent one: the run burns its whole budget on the first
applicable rule while every later rule never fires.

## What exists

| module | role |
|---|---|
| `mf.py` | the single import surface, the engine assertion, and the trap above |
| `facts.py` | the substrate adapter — kind, attribute and edge are ONE thing here |
| `intake.py` | Python → propositions, with provenance and gaps named |
| `emit.py` | propositions → Python, via `ast.unparse` |
| `evaluator.py` | the tool that answers what a function does for a case |
| `rules/patterns.ugm` | the descriptions — and the bridges, which are now the same statement |
| `rules/repair.ugm` | diagnosis and the two repair families |
"""
from __future__ import annotations

import os

RULES = os.path.join(os.path.dirname(__file__), "rules")


def corpus(*names: str) -> str:
    """Read authored rule files, to be loaded in ONE call.

    ⚠ One call, always. Two `load`s build two name tables, so the facts' relations
    are TWINS of the rules' and nothing matches — while the run reports a contented
    quiescence having done nothing. Upstream's most-recorded trap, and it has cost
    this project three separate wrong readings.
    """
    return "\n".join(
        open(os.path.join(RULES, f"{n}.ugm"), encoding="utf-8").read() for n in names
    )
