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
