# Decision patterns — agency without a backward-chaining engine

*Written 2026-08-27, against the working tree at that date (harneskills 11c459a, `pystrider/effects.py`
just landed). A design note from a live design conversation, not yet built beyond `effects.py` itself —
kept here for the record the way `docs/critique.md` and `docs/roadmap.md` are, and to be attacked or
extended before anything below becomes code.*

## The claim

`facts.py`'s own module note says restoring "the write half of the bet" — code generated from a wanted
outcome, not just recognized from structure — means making descriptions data again, the way `cnl.py`
did, because a Python function has no antecedent to read backwards. **That's the wrong target.**
Backward-reading a recognition rule to get a generation rule isn't a weaker substitute worth
resurrecting — it was never a valid move: `structure ⇒ effect` does not invert into `effect ⇒ structure`
any more than "wet ⇒ rained" licenses "rained ⇒ wet" as the *only* way to get wet. What a generation
capability actually needs is its own, independently authored **forward** rule — antecedent *wanted
effect*, consequent *this structure* — running on the exact same substrate as recognition. Nothing
about "goes in the backward direction" requires an engine that reads backwards.

Everything below is that idea, pushed until it broke or didn't: propose facts, arbitrate over sets of
facts, run to a fixpoint. No goal stack, no unification, no CNL, no new engine.

## Already proven, not just argued

Every piece of this pattern already exists somewhere in this repo, doing real work, before this note
was written:

- **Goal-as-antecedent** — `repair.py`'s `relax`/`lower`: `wants(unmet) ⇒ specific edit`. Not derived by
  inverting a recognizer; hand-authored, the same way `patterns.py`'s recognizers are.
- **Composability by disjointness** — `design.py`'s `check_interference`: "the placed widgets compose
  iff their writes are pairwise disjoint." Two candidates need no shared awareness to combine safely;
  they need disjoint `(entity, component)` footprints, a structural, generic test.
- **Refuse rather than guess** — `design.py`'s `resolve_screen` and `facts.py`'s `one()`: a decision
  point with more than one satisfying candidate is **Ambiguous**, not resolved by taking the first.
- **Subgoaling with no subgoal machinery** — `repair.py`'s `ask`/`answer`/`checked`: `ask` deposits a
  bare request (`evaluate(function, case)`), `answer` watches for it and answers when it can (or
  deposits its refusal, `could_not_evaluate`, rather than staying silent), `checked` reads the answer
  back. None of the three call each other. The loop's "run everyone, every tick, until nothing changes"
  *is* the dispatch.
- **Free transitive propagation** — `effects.py`'s `transitive()`: `outer` calls `inner`, `inner` has an
  effect, so `outer` does too — one more system reading the same fixpoint, not new machinery.

## The vocabulary

For one contested decision point (an *occasion* — an entity, or a `reify()`d proposition):

| relation | shape | written by | meaning |
|---|---|---|---|
| `candidate(occasion, option)` | monotonic | any proposer, unaware of rivals | *this is one way to resolve it* |
| `realizes(option, property)` | monotonic, transitive | any proposer | the justification chain a judge reasons over — `pizza realizes carbs`, `carbs realizes energy` |
| `ruled_out(occasion, option, reason)` | monotonic, never retracted | a hard-constraint judge | a categorical, named veto |
| `ranked(occasion, option, …)` | monotonic | a soft-preference judge | orders survivors; never eliminates one |
| `winner(occasion, option)` | `state()`d | the one generic commit step | eligible-minus-ruled-out, top-ranked |
| `needs(occasion, information)` | monotonic, idempotent | a blocked judge | an explicit, inspectable request — not silence |

A judge writes `ruled_out`/`ranked`/`needs` about a `candidate`; it never has to know which other judges
exist, only the vocabulary (`realizes`, or whatever property it reasons in) the candidates are described
in. A judge that finds no chain from a candidate to its own vocabulary abstains on that candidate — the
same discipline `patterns.py` already uses for `readable`: silence, not a guess.

## Composability is a structural test, not luck

Two candidates compose for free — both stand, no arbitration needed — exactly when their delta
footprints are disjoint `(entity, component)` pairs. That's `check_interference`, generalized past UI
widgets. Overlapping footprints are the only case that ever needs a judge's attention; today's
`repair.py` treats *every* case this way, arbitrating by bare registration order, and its own docs
record the cost: `gated=False` makes `relax` and `lower` both fire on one bug, "correct by luck and
wrong as a repair." That's what happens when agency lives in the base rule instead of in one generic
reader of the candidate set.

## Elimination and ranking are different things, kept apart on purpose

A hard veto (`ruled_out`) and a soft preference (`ranked`) could collapse into one numeric score (a
veto is just rank = −∞), but that throws away exactly what this project's decisions already insist on —
a *named* reason (`interferes_with`, `uncovered`, `detail`), not an opaque number. Keeping them separate
also buys safety for free: elimination only ever shrinks the candidate set (`fact()`, never `deny()`),
so a chain of judges — *pizza beats ice cream on preference, then diet rules pizza out* — can't cycle
back to a prior answer, because nothing is ever un-ruled-out. That's `nothing`'s whole win in the pizza
example: not chosen by override, just never eliminated once everything ahead of it was.

**Four verdicts at commit time**, not three — `resolve_screen`'s Forced/Ambiguous/Unresolved plus one:

- **Forced** — exactly one candidate survives elimination and leads the ranking.
- **Ambiguous** — more than one ties; refuse, the way `one()` already refuses.
- **Unresolved** — every candidate was ruled out, and the occasion declared no fallback (`is_default`,
  or an always-eligible `nothing`) of its own. Distinct from a *declared* fallback winning — that's an
  ordinary Forced.
- **Pending** — a `needs` request is still open when the world settles. Not a hang (`Loop.run` reports a
  clean settle either way) and not the same as Unresolved: *someone might still answer this.*

## Observability comes from the substrate, not the language

There is no CNL in this plan. CNL's actual value was letting a non-programmer swap `business.cnl`
without touching Python — a property about *who can author a rule*, not about whether its conclusion is
visible. Every relation above is deposited with the same `fact`/`state` this codebase already uses in
plain Python (`patterns.py`, `repair.py`, `design.py`), and nothing in `Facts` lets a system hide a
conclusion in a local variable — `fact`/`state` write onto an entity, not into a return value. So the
trace of a decision — which candidates existed, what ruled each one out, who won — is just
`f.of("candidate", occasion)` / `f.of("ruled_out", occasion)` / `f.of("winner", occasion)`, inspectable
by the same generic reads `why` already uses, regardless of which system or which language wrote them.
That's a *better* fit for a contested, multi-candidate decision than `cnl.explain()` ever was — its own
docstring admits it re-derives symbolically and can't say which of several concluding rules actually
fired. `winner(occasion, option)` says exactly that, for this run.

## Non-goals

- No SLD-resolution-style backward search, no unification, no choice-point/backtracking stack. A
  "goal" here is not a first-class thing the engine manages — it's an ordinary fact a judge's ordinary
  guard is checking for, the same as every other fact.
- No CNL authoring surface for any of this. It's Python, on purpose, per the section above.
- No score that swallows a categorical veto and a soft preference into one number.

## Open questions for the next pass

- What is an *occasion*, generically, across domains that aren't code — an entity minted per decision
  point, or always a `reify()`d proposition? `design.py`'s `decision:<point>` interning is one answer;
  it may not generalize past a fixed, known set of points.
- Does a `ranked` judge ever legitimately need to see *why* something was `ruled_out` (not just that it
  was), or is the boundary between the two total?
- Should "no fallback declared" be something every occasion author states explicitly, or should the
  generic commit step supply a bare "Unresolved, no default" verdict when none was declared?
