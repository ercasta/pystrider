# The transplant — what engine 2 is owed, recorded BEFORE it was deleted

**2026-08-23.** `pystrider/` (engine 2, on the `ugm-classic` worktree) was deleted and `restrider/`
(engine 4, on live `ugm`) was moved into its place. This file exists because of a lesson this repo
already paid for once:

> engine 2's stated bar for retiring the generation before it was a reach measurement — and the
> artifact holding that measurement, `experiments/reach_curve.py`, was deleted in the same commit
> that took the decision it gated. The handoff records the result plainly: *we did not measure it.*
> — `experiments/restrider_reach.py`

So the measurement is written down here, and it was taken **on the day of the decision**, not
remembered.

## The numbers that were true at deletion

⚠ **The corpus is PINNED TO A GIT REF, and that is not fussiness.** The first version of this
bar said *"this repo, `**/*.py`"* — and deleting engine 2 removed 355 of its functions the same
hour, so the corpus the bar was written against stopped existing before the bar was ever read. A
percentage over a moving corpus is not a measurement. Reproduce it with:

```bash
git worktree add --detach /tmp/engine2 4a26c0e
python experiments/pystrider_reach.py "/tmp/engine2/**/*.py"
```

One corpus (this repo **at `4a26c0e`**, 589 `FunctionDef`s), one oracle (`ast.unparse` of the
function), one counting rule (FUNCTIONS blocked, never occurrences).

The live runner is `experiments/pystrider_reach.py`. The engine-2 column was produced by the
*identical* sweep at `4a26c0e`, differing only in the three lines that name the other API — kept
here rather than as a dead module, so it is reproducible without being maintained:

```python
lib = library.load()                       # was: f = Facts(rules, scope=...)
taken = intake(lib, source, origin=path)   # was: taken = intake(source, f, path)
rendered = emit(lib, taken.module)         # raises CannotEmit, not Unrenderable
```


|                                       | engine 2 | engine 4 (this package) |
|---------------------------------------|---------:|------------------------:|
| this repo @ `4a26c0e` (589 functions)  | **401 (68.3 %)** |       **18 (3.1 %)** |
| `../ugm/ugm/**/*.py` (268 functions)   | **137 (51.1 %)** |        **0 (0.0 %)** |
| UNSTABLE, both corpora                 |    **0** |                   **0** |

The second row is a control on a corpus neither engine was developed against, and it says the
first row is not an artefact of measuring ourselves: the gap is real and slightly *wider* on
foreign code. It also names engine 4's true first obstacle — on annotated modern Python the
top of its backlog is `FunctionDef.returns` (248) and `arg.annotation` (162), i.e. **it cannot
yet read a typed signature**, which is most of what it is looking at.

`UNSTABLE 0` on both sides is the property; the percentage is only the coverage. Engine 2's top
backlog was comprehensions and `With` (`ListComp` 21, `GeneratorExp` ~40 across arities, `With` 6,
`SetComp` 5). Engine 4's is the whole middle of the language: `Assert` 234, `Tuple` 221,
`FunctionDef.returns` 206, `Call.keywords` 197, `arg.annotation` 186, `Subscript` 111.

**The 3.1 % is what was moved onto. The 68.3 % is the debt this file records.**

## Why the debt is collectable — and it is not a rewrite

The 68.3 % is **not engine-bound**, which is the finding that decided the whole move:

```
620 lines   0 engine refs   pystrider/intake.py
303 lines   0 engine refs   pystrider/emit.py
```

923 lines — the entirety of what produced the reach — import `ast` and `.library`, nothing else.
The complete engine surface they touch is **seven graph methods**: `target`, `targets`, `attr`,
`put`, `mint`, `link`, `kind`. Today's `pystrider/facts.py` (was `restrider/facts.py`) already
offers that shape under other names — `one`≈`target`, `of`≈`targets`, `text`≈`attr`, `fact`≈`put`/
`link`, `node`≈`mint`, `has`≈`kind`.

The two intake vocabularies are one design a generation apart: engine 4's ~50 relations are close
to a subset of engine 2's ~200, differing by a handful of renames (`function`/`function_def`,
`iterated`/`iter`, `comparison`/`compare`, `returned`/`value`, `unknown_part`/`unknown_parts`).

## Where to get it

    git show 4a26c0e:pystrider/intake.py     # 620 lines, engine-free
    git show 4a26c0e:pystrider/emit.py       # 303 lines, engine-free

`4a26c0e` is the commit recorded below — the last one in which engine 2 existed.

Deleted with it, and deliberately: `pystrider/library.py`, `lift.py`, `patterns.py`, `mf.py` (438
lines, engine-bound — engine 4 does this natively in 62 lines of `rules/patterns.ugm`), the eight
engine-2 test modules, and five engine-2 probes. The engine-independent line — `understand_*`,
`pattern_compose`, `base_tier` — was not touched.

## 2026-08-24 — the other axis: TRANSLITERATION

The table above measures **the membrane** — what `intake.py`/`emit.py`, and therefore this project's
curated vocabulary, can read and write. `pystrider/transliterate.py` measures the other half of the
same question and deliberately has no membrane at all: every AST node, every field, no judgement.
Same corpus, same oracle (`ast.unparse` of the function), same runner discipline —
`experiments/transliterate_reach.py`.

| corpus                                     | functions | carried | CHANGED | REFUSED |
|--------------------------------------------|----------:|--------:|--------:|--------:|
| this repo @ `4a26c0e` (the pinned corpus)  |       587 | **100.0 %** | 0 | 0 |
| `../ugm/ugm/**/*.py` (foreign control)     |       321 | **100.0 %** | 0 | 0 |
| this repo @ HEAD                           |       250 | **100.0 %** | 0 | 0 |
| `/usr/lib/python3.11/**/*.py` (stdlib)     |    13 518 | **100.0 %** | 0 | 0 |

⚠ **`carried` is not a percentage to improve and it is not comparable to `round-trip` above.** This
reader is supposed to be total, so the number that carries information is that `CHANGED` and
`REFUSED` are both zero — a reader that refuses nothing and silently alters something is strictly
worse than one that refuses loudly.

**⭐ THIS DOES NOT COLLECT THE DEBT.** 68.3 % is what the project could DESCRIBE and REPAIR, and
transliteration understands nothing: `syntax($n, ListComp)` plus its fields is a comprehension
present, not a comprehension read. What it changes is where the gap now sits. Before, a construct
`intake.py` had no handler for cost its container, so the backlog was *the whole middle of the
language*. Now the tree is complete and each corpus decides for itself which nodes it matches, so
coverage is per-question and incremental rather than one cliff in front of everything.

⚠ Both defects the sweep found were found on FOREIGN code after the module already looked finished,
and both were silent-wrong rather than refusals — an interned `item($s, $c)` losing the second of two
identical list elements (`{**a, **b}` → `{**a}`; `def f(*, a, b)` losing a parameter), and a string
constant that reads as a literal (`'[]'` → `[]`, and every f-string format spec). Fourteen functions
across the stdlib and `../ugm`, none of them visible on this repo. **The control corpus is not a
formality**, and neither is comparing against the source.

## The bar, restated

`pystrider/` was retired **before** it was matched, which is a deliberate choice to stop
maintaining a private fork of a dead engine rather than a claim that engine 4 caught up. The
replacement bar is therefore this file:

> Re-run `experiments/pystrider_reach.py` after the transplant. It must clear **68.3 %** with
> **UNSTABLE still 0** on this same corpus. Until it does, this repo reads less Python than it
> did on 2026-08-23, and that is a fact to keep in view rather than a number to forget.
