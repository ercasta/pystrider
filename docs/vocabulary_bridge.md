# Reconciling vocabularies with bridges

**Date:** 2026-07-18 · **Probe:** `experiments/vocabulary_bridge.py` · **Pins:** `tests/test_vocabulary_bridge.py` (7)

## The question, and the frame that was wrong

`ast_representation_findings.md` closed by naming an integration risk: the lowering rules invent a
construction vocabulary (`is_a ast_call`, `body_has`), while `pystrider/intake.py` emits an analysis
vocabulary (`is_a call`, `calls_func`, `passes`, state-threaded cells). It called reconciling them
"the shared-vocabulary bet" — i.e. the two halves must converge on one set of names.

**That framing is wrong.** It is unrealistic to expect multiple authors, working in multiple domains
at different times for different purposes, to converge on one vocabulary. Intake's names were chosen
for dataflow analysis and are right for it. A lowering bank's names are chosen for construction and
are right for that. Neither should have to move for the other.

The project already had the answer and used it a level up: **bridges**. `app_synthesis` fused three
vocabularies — business, UX, and the Textual framework — with a handful of cross-vocabulary facts, and
said so plainly: *"the bridge is the only link between the UX vocabulary and the framework vocabulary."*
The same move applies to code structure itself.

```
author W (lowering)   is_a emit_bind / callee / argument  --.
                                                            >-- BRIDGE --> invokes / hands
author R (intake)     is_a call / calls_func / passes     --'         (the question vocabulary)
```

Each author keeps their vocabulary and writes ONE small bridge into a neutral **question** vocabulary.
Patterns are authored once against that neutral layer. The cost is **O(N) bridges for N vocabularies**,
not O(N²) pairwise translations: a third author — a fragment library, an absorbed framework surface —
costs one more bridge and edits no existing rule or pattern.

## What the probe shows

The round trip, end to end:

1. a spec is **lowered** by rules into minted structure — author W's vocabulary
2. the structure is **emitted** as real Python (`ast.unparse`, the last mile)
3. the emitted source is **read back** by the shipped `intake` — author R's vocabulary
4. **one pattern**, authored once over the neutral vocabulary, answers over both ends

```
the pattern, authored ONCE:   ?c is_a greet_site when ?c invokes greet

emitted:   def report(name, title):
               msg = greet(name)
               sig = greet(title)
               print(msg)

write side (emit_bind/callee):   2 greet_site(s)
read  side (call/calls_func):    2 greet_site(s)
=> one rule text, two vocabularies, same answer.  Each bridge is 2 lines.
```

So an understanding rule written against hand-written code recognizes **generated** code, and the two
halves never share a predicate name. That is the "one library serves writing and understanding" claim
delivered without forcing anyone to rename anything.

A pin holds the two vocabularies **disjoint** (`test_neither_author_shares_a_predicate_with_the_other`),
so if the demo ever quietly becomes convergence, the suite says so instead of flattering us. Another pin
removes the bridge and confirms the same pattern then answers nothing — the bridge is doing the work,
not an accident of naming.

## The finding: bridges reconcile NAMING, not COVERAGE

Part 2 of the probe is the more useful half. The emitted code ends with a bare `print(msg)`. Intake
**deliberately does not model a bare expression statement** — it emits an audited `not_modelled` marker
instead (the honesty discipline from critique #5). There is no call node for it, and **no bridge can
invent one**.

| gap | the two authors disagree about | who can fix it |
|---|---|---|
| **naming** | what to *call* a thing | a bridge — 2 lines, no author moves |
| **coverage** | what *exists* | only the vocabulary's author |

Both look identical from the outside: a question returns nothing. They have completely different
fixes. This is the practical argument for making the join explicit rather than stretching one
vocabulary to cover both jobs — `not_modelled` names the coverage gap out loud, instead of letting it
masquerade as a naming mismatch that someone then tries to bridge away.

## Consequences for the track

- The spec→AST→code pipeline **does not need a unified vocabulary**, and should not attempt one. Author
  the lowering bank in whatever names suit construction.
- Every new knowledge source arrives as *its own vocabulary + one bridge*. This is what makes a "learned
  library of patterns" additive rather than a renaming project.
- The neutral question vocabulary is the thing to design carefully, because patterns are written on it
  and it is what stays stable as authors come and go. It should describe *questions about code*, not
  either side's mechanics.
- Coverage gaps are a real, separate backlog: intake models assignments, returns, ifs and whiles, and
  audits everything else as `not_modelled`. Growing that is the vocabulary author's job, and the
  `not_modelled` list is the worklist.
