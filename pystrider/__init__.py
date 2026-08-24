"""`pystrider` — reads and writes Python by reasoning, on ugm's rules engine. Generation three.

**THE BET, unchanged across three engines:** one authored description, read one way
RECOGNIZES code, read the other way WRITES it. What changed each time is what the
substrate lets a description be.

    engine 1  `ugm` classic      a CNL rule's BODY recognizes, its HEAD writes
    engine 2  `microfunctions`   pattern matching deleted, so `driver.establishes`
                                 reconstructed the duality from a function's body
                                 versus its effects
    engine 3  `rules-design.md`  pattern-matching rules are back, AND a backward
                                 reader over the same rules ships. This package.

⭐⭐⭐ **On this floor the bet is NATIVE** (`docs/restart_port_survey.md` §7,
`experiments/restart_bet.py`, 11 checks). `driver.establishes` — the module the
entire engine-2 rewrite was founded on — is **not missing, it is unnecessary**:
what it reconstructed by reading a function body is what an antecedent already is.
And recognition now arrives EXPLAINED, because `why()` walks the derivation and
names every part it consumed.

## ⚠⚠ THE RETIREMENT HAPPENED WITHOUT THE MEASUREMENT IT WAS GATED ON. AGAIN.

This package was `restrider/` until 2026-08-18, and the engine-2 `pystrider/` it
replaced had a **written bar** for being retired:

> `pystrider/` stays until this package round-trips a comparable corpus and refuses
> the rest BY NAME, predicted in advance. A raw pass rate measures only which inputs
> you chose.

**That bar was never met, and the retirement happened anyway** — a user decision,
taken once the floor engine 2 binds to was deleted upstream and the package stopped
being able to *import*, let alone stay green. So the honest record is:

| | engine 2, at its last green | this package, measured 2026-08-18 |
|---|---|---|
| reach | **64.1%** (710/1107) | **3.1%** (18/587) |
| bar | — | 21/21 in-closure, 15/15 refused by name: **not run** |

⚠ The comparison is not like-for-like — the corpora differ — and **that is the
point**: nothing now compares this generation's reach against the old one's, and
the artifact that could have (`experiments/reach_curve.py`) ran on the deleted
engine. This is the SECOND retirement here to go through ungated, and the first
one is recorded in `HANDOFF.md` §5 in exactly these words: *we did not measure it.*

**So the 3.1% is debt, not a result.** `experiments/strider_reach.py` re-derives it
on demand; `UNSTABLE 0` is the number that must stay zero. Comprehensions are the
biggest lever and the hardest — they bind variables and open a scope.

## One engine now, and one pytest invocation

`restrider` and `pystrider` could not share a process, because two engines were
installed under the name `ugm`. Upstream deleted engine 2 deliberately, so the
split suites, the `ugm-classic` refusal and the `sys.path` reach-past are all gone
— `python -m pytest tests/ -q` runs everything, **75 passed**. See `mf.py`.

## What exists

| module | role |
|---|---|
| `mf.py` | the single import surface, and the only file that names `ugm` |
| `facts.py` | the substrate adapter — kind, attribute and edge are ONE thing here |
| `intake.py` | Python → propositions, with provenance and gaps named |
| `emit.py` | propositions → Python, via `ast.unparse` |
| `evaluator.py` | the tool a goal drives, with its membrane FIRST and explicit |
| `rules/patterns.ugm` | the descriptions — and the bridges, which are now the same statement |
| `rules/repair.ugm` | repair families, proposable only once backward reading finds a goal `unmet` |
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
