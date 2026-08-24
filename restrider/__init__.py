"""`restrider` — pystrider on `../ugm`. Generation three.

**THE BET, unchanged across three engines:** one authored description, read one way
RECOGNIZES code, read the other way WRITES it. What changed each time is what the
substrate lets a description be.

    engine 1  `ugm` classic      a CNL rule's BODY recognizes, its HEAD writes
    engine 2  `microfunctions`   pattern matching deleted, so `driver.establishes`
                                 reconstructed the duality from a function's body
                                 versus its effects. That is `pystrider/`.
    engine 3  `restart`          pattern-matching rules are back, AND a backward
                                 reader over the same rules ships. This package.

⚠ **`restart` IS `main` NOW.** Upstream merged it on 2026-08-20 and kept going on
`main`; the branch called `restart` has not moved since 2026-08-16 and is 77
commits behind. Engine 3 means *`../ugm` on `main`* — see `mf.py`, which resolves
it and says why the old "are you on `main`?" diagnostic was exactly inverted.

⭐⭐⭐ **On this floor the bet is NATIVE** (`docs/restart_port_survey.md` §7,
`experiments/restart_bet.py`, 11 checks). `driver.establishes` — the module the
entire engine-2 rewrite was founded on — is **not missing, it is unnecessary**:
what it reconstructed by reading a function body is what an antecedent already is.
And recognition now arrives EXPLAINED, because `why()` walks the derivation and
names every part it consumed.

## The bar for retiring `pystrider/`

⚠⚠ **NOT "the tests pass", and this time we know why that bar is worth writing
down.** Engine 2's stated bar was the reach measurement from `experiments/
reach_curve.py` — and on 2026-08-02 the old packages were retired anyway, without
it, because the artifact holding the measurement went out with the same commit.
The handoff records that plainly: *we did not measure it.* So:

> **`pystrider/` stays until this package round-trips a comparable corpus and
> refuses the rest BY NAME, predicted in advance.** A raw pass rate measures only
> which inputs you chose.

Until then `pystrider/` remains the only running account of what this is supposed
to do, and it stays green — `python -m pytest tests/ -q`, 219 passed.

## ⚠⚠ TWO ENGINES CAN BE NAMED `ugm` — READ `mf.py` BEFORE RUNNING ANYTHING

`restrider` and `pystrider` **cannot share a process**: importing `restrider.mf`
re-points `import ugm` for everything after it. `tests/` and `tests_restart/` are
separate pytest invocations, and both `mf.py` files assert which engine they got,
so a cross-wiring fails loudly instead of producing answers from the wrong engine.

## What exists

| module | role |
|---|---|
| `mf.py` | the single import surface, plus the engine assertion |
| `facts.py` | the substrate adapter — kind, attribute and edge are ONE thing here |
| `intake.py` | Python → propositions, with provenance and gaps named |
| `emit.py` | propositions → Python, via `ast.unparse` |
| `rules/patterns.ugm` | the descriptions — and the bridges, which are now the same statement |
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
