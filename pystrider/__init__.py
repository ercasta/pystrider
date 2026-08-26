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
    engine 5  `harneskills`      no engine at all — an entity-component world and a
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
  refusal of a sibling checkout — went away with the thing it guarded.

## What exists

| module | role |
|---|---|
| `facts.py` | the substrate adapter — a relation is a component, its objects are rows |
| `cnl.py` | authored `head when body` blocks, each rule compiled to ONE system |
| `intake.py` | Python → propositions, with provenance and gaps named |
| `transliterate.py` | Python → propositions, TOTALLY — no membrane, nothing refused |
| `emit.py` | propositions → Python, via `ast.unparse` |
| `patterns.py` | the neutral descriptions (the forward half of the bet) |
| `repair.py` | diagnosis, the evaluator-as-system, and the two repair families |
| `evaluator.py` | what a function returns for a case, derived from structure |

⚠ `demos/playground` is the headline: business, UX and toolkit rules in separate
authored files, joined only by `bridge.cnl`, composed and driven green through
Textual's Pilot. It is the one place the CNL surface is load-bearing, and
`cnl.py`'s note says why the answer differs there.
"""
from __future__ import annotations

__all__ = ["cnl", "emit", "evaluator", "facts", "intake", "patterns", "repair",
           "transliterate"]
