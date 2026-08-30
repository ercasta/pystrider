"""`pystrider` — reading and writing Python by reasoning, on `harneskills`.

**THE BET, across five substrates:** one authored description, read one way
RECOGNIZES code, read the other way WRITES it. What changed each time is what the
substrate lets a description BE.

    engine 1  `ugm` classic      a CNL rule's BODY recognizes, its HEAD writes
    engine 2  `microfunctions`   pattern matching deleted, so `driver.establishes`
                                 reconstructed the duality from a function's body
                                 versus its effects
    engine 3  `restart`          pattern-matching rules are back, AND a backward
                                 reader over the same rules ships
    engine 4  the scratchpad     one graph that IS the state; the backward reader
                                 went into the engine's bin
    engine 5  `ugm` (again)      no engine at all — an entity-component world and a
                                 loop that calls every system until nothing changes

## ⚠⚠ WHAT ENGINE 5 COSTS, STATED FIRST

**A description is a Python function here, and a Python function has no antecedent
to read backwards.** On engine 3 a rule was DATA, so the same authored implication
was both a recognizer and a work order. That is gone — not parked behind a missing
feature this time, but given up by the shape of the substrate. `patterns.py` says
so at the top, and `test_spine.py` keeps the expectation a backward reader would
have to satisfy so that whoever restores it has the target in hand.

⭐ Restoring it does not mean going back to `ugm`: it means making descriptions
data again — a small matcher over `Facts`, with each authored description compiled
to a system exactly as `cnl.py` already compiles a `head when body` rule. **That
path is open and `cnl.py` is the worked example**, which is why the CNL blocks
stayed text while these did not.

## ⭐ WHAT ENGINE 5 PAYS FOR

* **The twin trap is structurally gone.** A relation is a Python class interned by
  name, so a relation built in Python cannot be a twin of one a rule uses. Four
  recorded wrong readings came from that, and there is nothing left to get wrong.
* **The `no <own conclusion>` premise is retired.** There is no inert set on `ugm`,
  so a rule that did not stop itself hung the run — silently, by burning the budget
  on the first applicable rule. `World.attach` compares before it stores, so
  re-deriving what already holds is not a change and the world settles.
* **One store, one settle.** `demos/playground` reasons from a business fact to an
  admitted screen design in a single fixpoint, because the composition checks are
  systems on the same loop as the block rules.
* **No path lookup, no name table, no engine to resolve to the wrong copy.** The
  whole of `mf.py` — the single-import-surface bet, the engine assertion, the
  refusal of a sibling checkout — went away with the thing it guarded. ⚠ Its last
  descendant, `_NEEDS` in `facts.py`, went with the 2026-08-28 move: that guard
  asserted a set of `ugm` names on import because `facts.py` lived in a DIFFERENT
  checkout from the world it adapted. It now lives in the same package as `world.py`
  and `loop.py` and versions with them, so there is nothing left for it to catch.
  What still guards this package is `tests/conftest.py`, and it guards the thing that
  can still go wrong — WHICH `ugm` a run imported.

## What exists

⚠⚠ **`facts.py` AND `arbitration.py` ARE BACK HERE, AND THIS TIME FOR GOOD
(2026-08-29).** They lived in `ugm` for one day (2026-08-28), moved there because
neither knew anything about Python. `ugm` was carved out of `harneskills` into its
own repo the day after, renamed `loopingrules` — and on the way out, deleted
`facts.py`/`arbitration.py` entirely rather than port them: nothing in
`harneskills` itself ever imported them, so a generic relation/arbitration
vocabulary had no domain left asking for it. **They do not come back as files.**
Every relation this package used to declare through them is now a real,
explicitly-named `@dataclasses.dataclass` component, read and written straight
through `loopingrules.world.World` — `patterns.py` is the worked example.
Arbitration is domain-owned code in `repair.py`/`effects_repair.py`/`plan.py`
now, not a shared reader — see `docs/decision_patterns.md` for the argument
`harneskills`'s own `docs/intake processing.md` independently arrived at.
`cnl.py` and `transliterate.py` are the two exceptions, and each says why in its
own module note: their vocabulary is late-bound (a `.cnl` predicate, an AST field
name), not fixed at Python-authoring time, so each keeps a small,
`dataclasses.make_dataclass`-based dynamic factory scoped to itself.

| module | role |
|---|---|
| `cnl.py` | authored `head when body` blocks, each rule compiled to ONE loop rule |
| `intake.py` | Python → components, with provenance and gaps named |
| `transliterate.py` | Python → components, TOTALLY — no membrane, nothing refused |
| `emit.py` | components → Python, via `ast.unparse` |
| `patterns.py` | the neutral descriptions (the forward half of the bet) |
| `repair.py` | diagnosis, the evaluator-as-rule, and the two repair families |
| `evaluator.py` | what a function returns for a case, derived from structure |
| `effects.py` | what a function DOES outside its return value, forward off structure |
| `effects_repair.py` | a wanted effect, achieved through this module's own candidates |
| `plan.py` | a parallel demonstration of the same repair, arbitrated as a scenario bench |
| `rules.py` | `derive`/`assign`/`minting` — the three rule shapes `plan.py` is built from |
| `strict.py` | run a loop the way a one-shot derivation needs, not the way a REPL does |
| `resolve.py` | a stable key (`path`, name) → a live, `@transient` entity — the seam a durable fact reaches through |

⚠ `demos/playground` is the headline: business, UX and toolkit rules in separate
authored files, joined only by `bridge.cnl`, composed and driven green through
Textual's Pilot. It is the one place the CNL surface is load-bearing, and
`cnl.py`'s note says why the answer differs there.
"""
from __future__ import annotations

__all__ = ["cnl", "domain", "effects", "effects_repair", "emit", "evaluator",
           "intake", "patterns", "plan", "repair", "resolve", "rules",
           "strict", "transliterate"]
