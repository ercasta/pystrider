# Slice 5 predictions — recorded 2026-07-31, BEFORE any code was written

The method matters more than the number. A raw pass rate afterwards would measure only which constructs
we happened to choose; predicting the closure in advance is what makes it a **reach measurement**. This
file is written first so it cannot be retrofitted, and the post-slice report cites it whether it was right
or wrong.

## Baseline (measured)

Corpus: 106 files across `strider/`, `tests/`, `experiments/`.

```
functions round-tripping stably : 24
functions unstable              : 0
functions refused               : 847
```

**2.8%**, and the 0 matters as much as the 24: everything either round-trips byte-exactly or refuses.
Nothing is silently approximated.

Top refusal causes: `Assert` 1052, `Tuple` 530, `keyword` 458, `JoinedStr` 386, `Subscript` 306,
`ImportFrom` 295, `List` 130, `Dict` 125, `Import` 112, `AnnAssign` 101, `ListComp` 95, `BoolOp` 87,
`IfExp` 79, `ClassDef` 77.

## What slice 5 will add

`Assert`, `Tuple`, `List`, `Dict`, `Set`, `keyword` (call kwargs), `Subscript`/`Slice`, `Import`,
`ImportFrom`/`alias`, `AnnAssign`, `BoolOp`, `IfExp`, `ClassDef`, `AugAssign`, `UnaryOp`, `Starred`,
plus the signature extras currently refused as fields (`defaults`, `vararg`, `kwarg`, `kwonlyargs`) and
`decorator_list`.

Deliberately **not** in scope: comprehensions, f-strings, `Try`/`With`/`Raise`, `Lambda`, `while`, async.

## The predictions

**P1 — reach.** `569/1005 ≈ 56.6%` of functions round-trip stably. Stated band: **53–58%**. The estimate
is a closure computation over the corpus, so a result far below it means an implementation bug rather than
a bad forecast, and that is the point of stating it.

**P2 — the membrane still holds: unstable stays 0.** Every function either round-trips byte-exactly or
refuses by name. This is the prediction I would be most troubled to lose, because a non-zero here means we
started silently approximating code.

**P3 — the denominator grows, from 871 to ~1005.** `ClassDef` is currently unmodelled, so methods are
never *reached* at all. Modelling it makes ~134 more functions visible — which means the percentage and
the population both move, and a naive before/after on the fraction alone would flatter us.

**P4 — the remaining blockers, in order:** comprehensions (`comprehension` 305 functions, `GeneratorExp`
144, `ListComp` 138, `SetComp` 70, `DictComp` 30), f-strings (`JoinedStr`/`FormattedValue` 105), then
`Try`/`With` (24 each). Comprehensions alone are the next ~30 points and are a genuinely different
problem: a comprehension binds variables and has its own scope, so it is not a container we can walk.

**P5 — decorators are worth little for reach and are in scope anyway.** +3.2pp only, because
comprehensions dominate. They are included because `@on(Button.Pressed)` is unavoidable for the Textual
app-generation ending, not because they move this number.

**P6 — where I expect to be wrong.** Something will round-trip structurally but not textually, the way
the empty `else` did. Most likely candidates: `Tuple` parenthesisation (`return 1, 2` vs `return (1, 2)`),
`Subscript` in a `Store` context, and `AnnAssign` with no value (`x: int`). If P2 holds, these surface as
refusals or as caught instabilities rather than as wrong code.

## The honest caveat about this corpus

Our own repository is not representative Python: it is unusually comment-heavy, assertion-heavy (it is
mostly tests), and light on classes. A 56% here is not a claim about Python at large. It is a claim about
whether the *membrane* moves where we predicted, which is what the number is for.

---

# Result — measured after the slice

| | predicted | measured | |
|---|---|---|---|
| **P1** reach | 56.6% (band 53–58) | **59.6%** (625/1049) | ⚠ **outside the band, high** |
| **P2** unstable | 0 | **0** | ✅ held |
| **P3** denominator | ~1005 | **1049** | ✅ direction right, 4% out |
| **P4** blocker order | comprehensions, then f-strings | **f-strings first** (435), then comprehensions (165/158/84/33) | ❌ order wrong |
| **P6** named risks | tuple parens, subscript-store, bare AnnAssign | bare tuple **did** normalise; the other two round-trip clean | ⚠ one of three |

**P1 missed on the high side, and the reason matters more than the miss.** The closure estimate counted a
`comprehension` node as blocking a function, but a function containing a `ListComp` also contains a
`comprehension`, so the same functions were counted through two blockers and the estimate under-counted
what would be freed. Then `BitOr` — found *by the sweep*, not by the estimate — freed another 11
functions on its own. A prediction that lands outside its own band is still worth more than no
prediction: it named exactly which assumption was wrong.

**P2 is the one that mattered and it held.** 1049 functions, and not one is silently approximated: every
function either round-trips or refuses by name. That property survived a 21-construct widening.

**P4 was wrong in a useful way.** F-strings, not comprehensions, are the dominant remaining blocker — 435
functions against comprehensions' 165. That reorders the next slice: `JoinedStr`/`FormattedValue` is one
construct pair worth roughly 40% of what remains, and it is *far* cheaper than comprehensions, which bind
variables and introduce their own scope.

## Two bugs the work surfaced, both found by measuring rather than by reading

**`BitOr` was missing from the operator table**, so `str | None` — every modern union annotation — was
refused. 36 functions in our own repo. Invisible to inspection because nobody thinks of `|` as arithmetic.

**⚠ I declared a consumption I did not perform.** `ClassDef`'s `_CONSUMES` entry listed `keywords` while
`_ClassDef` never visited them, so `class A(metaclass=M)` silently dropped its metaclass — precisely the
failure the `unconsumed` guard exists to prevent, reintroduced by the person who wrote the guard.
**Declaring a field consumed is switching the guard off for that field**, and it should be done only
alongside the code that actually reads it.

## A lesson about membrane pins

Eight pins went red on widening because their EXAMPLES had moved inside the membrane — a pin asserting
"`[x]` is refused" once lists are modelled is asserting something false about a correct system. The
invariants were right; the examples had gone stale. **Widening a membrane invalidates the examples, never
the invariant** — so a membrane pin should draw its example from whatever is currently outside, and
expect to be re-pointed each time the boundary moves.

---

# Slice 6 — f-strings (2026-07-31)

**Predicted 64.8%, measured 64.6%** (685/1061), unstable still **0**. Within 0.2pp — much closer than
slice 5's miss, and for a knowable reason: f-strings do not have the nested-node double-counting that
threw the earlier estimate (a function containing a `ListComp` also contains a `comprehension`, so the
same functions were blocked twice).

**⚠ A CORRECTION TO SLICE 5's P4.** That section said f-strings were "worth roughly 40% of what remains".
Wrong: 435 was a count of refusal *occurrences*, not of *functions blocked*. By functions — which is what
reach measures — comprehensions block 318 and f-strings only 107. F-strings were still worth doing (cheap,
+5pp, and they are everywhere in real code), but the stated rationale was mis-derived and the next slice
should be chosen on the corrected figure.

**Modelled as PARTS, not as a template with opaque holes.** `f"{a + b}"` contains a real `binop`
sub-node, so everything that already reads expressions reads inside an f-string for free, and a pattern
could match in there. A format spec (`:>{width}`) is itself a `JoinedStr`, so it nests with no special
case. The `!r` conversion is kept as the raw int Python uses rather than decoded, because emit needs
exactly that int back and decoding it twice is two places to get it wrong.

**The membrane lesson recurred, exactly as recorded.** Three pins used f-strings as their
"still-outside" example — written that way *in slice 5, when f-strings were outside*. They went red on
schedule. Re-pointed at `Lambda`, which sits well clear of the widening backlog.

**Remaining blockers, by functions:** `ListComp` 183, `GeneratorExp` 163, `SetComp` 86, `DictComp` 34,
`Raise` 28, `With` 25. Comprehensions are now unambiguously the next lever and also the hardest — they
bind variables and introduce a scope, so they are not a container that can simply be walked.

---

# Slice 7 — the app-generation ending (2026-07-31)

**⚠ NO REACH PREDICTION WAS MADE, and that is deliberate rather than an omission.** Slices 5 and 6 chose
their constructs to move reach and predicted the move in advance. This slice chose its construct to unblock
a *capability* — the README's ending, a real Textual app derived by a goal and verified by driving it — so
predicting reach would have been predicting something the slice was not aiming at. What it did predict, and
what is recorded below, is that **the reach gain would be near zero and the slice would still be worth
doing**.

## The construct: `Yield`

A Textual `compose` method is a generator. One unmodelled expression made **every** Textual app partial, so
the entire app-generation ending was blocked by `yield` and nothing else.

| | measured |
|---|---|
| reach WITH `Yield` | **64.1%** (710/1107) |
| reach WITHOUT `Yield`, same corpus, same day | **64.1%** (710/1107) |
| difference | **0.0pp — not one function** |

Our corpus contains no generator functions at all. So `Yield` is worth **literally nothing** for reach and
was worth the whole slice.

**⭐ THE LESSON, and it generalises past this construct: REACH IS THE WRONG METRIC FOR CHOOSING A CONSTRUCT
WHEN THE GOAL IS A CAPABILITY.** Slice 5's P5 gestured at this — decorators were "worth little for reach
and are in scope anyway", +3.2pp, included because `@on(Button.Pressed)` was unavoidable. `Yield` is the
same argument at its limit: +0.0pp, and without it there is no app. A slice plan that ranked candidates by
predicted reach would have put this construct last forever, and the README's ending would never have
shipped. **Reach measures the membrane against a corpus; it does not measure what a construct unlocks.**

## ⚠ A silent-wrong bug that two reach measurements missed

`unstable` came back **6**, not 0 — the invariant slice 5 called "the prediction I would be most troubled
to lose".

`intake.signature` minted keyword-only, positional-only, `*a` and `**k` parameters as name-only nodes: it
never read `annotation`, and never called `unconsumed`. So

    def intake(lib, source, *, origin: str = '<unknown>') -> Intaken:

was intaken with an EMPTY `unmodelled` list, reported **complete**, and emitted as `origin='<unknown>'`.
Six functions in our own repo, silently wrong, with nothing to indicate it. `emit` had the identical gap on
the write side.

**This is the `_CONSUMES["ClassDef"]["keywords"]` failure repeating**, and repeating in the same shape:
the `unconsumed` guard exists to catch exactly this class of omission and was bypassed by *never being
called at that site*. Both sides now go through one helper — `Intake.param` and `Emit.arg` — because a
guard that has to be remembered at each site is a guard that will be forgotten at one of them. Fixed;
`unstable` is back to **0**, and the six functions account for the 63.5% → 64.1% move.

**⭐ WHY TWO PREVIOUS SLICES MEASURED `unstable = 0` AND MEANT IT: STABILITY IS NOT FIDELITY.** A round trip
that compares emit against emit reports a clean fixpoint on code that has *already* lost the annotation —
the second pass has nothing left to drop. Only comparing against the ORIGINAL SOURCE catches a silent
deletion. Pinned in `test_the_annotation_bug_was_INVISIBLE_to_a_stability_check`, which asserts that the
weaker check passes on the very input the stronger one fails. **Any future reach sweep must compare against
the source**, or the headline invariant is measuring the wrong thing.

## Where reach now stands

710/1107 = **64.1%**, unstable **0**. Blockers by refusal events: `ListComp` 188, `GeneratorExp` 177,
`SetComp` 92, `DictComp` 35, `With` 26, `Try` 24, `Raise` 23, `Continue` 21, `Lambda` 10. ⚠ Those are
*events*, not functions blocked — the correction slice 6 had to make. Comprehensions remain the next lever
by functions, and `Continue` is new to the list and cheap.
