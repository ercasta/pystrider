# Feedback for `../ugm@restart` — from `pystrider`/`restrider`, 2026-08-13

> **⚠ 2026-08-20 — §5 IS NEW AND IT IS A REGRESSION, not a request.** Measured against
> `a3b5474`. §1's fix is intact; the table loop reintroduced the *other* quadratic on the shape §1
> measured as linear. Everything above §5 is the original 08-13 filing, kept as written.

Measured against `restart` @ `c05d5b3`. Framed as **hypotheses**, per our standing practice with this
project: four of our confident diagnoses were inverted last generation because we reason from the
consumer's side and cannot see the engine's. Every repro below is runnable from this repo.

---

## §1 ⭐⭐⭐ There are TWO quadratics, and `quiet` / `weigh` / `heap` all fix the other one

**This is the whole of the feedback; everything else is small.**

`weigh` concludes *the n²/2 is the option set, not waste* — the agent really does have n applicable
rules on tick 1, n−1 on tick 2, and §18 permits one move at a time. We believe that is exactly right
**for the `edge` fixture**, and we can reproduce it. But it is a claim about a fixture whose cost is
**n ticks × O(state) per tick**, and the shape that blocks *us* has a constant option set and **three
ticks**.

One rule, joined against itself over one relation — an AST relation, which is what recognition is:

    rule <s1> = implies( { +child(?p, ?x), +child(?x, ?y) }, { +grand(?p, ?y) } )

against N inert `child` facts. Counted with `rules.unify` wrapped, both fixtures side by side:

| fixture | n | run | **`unify` calls** | ticks | max proposed |
|---|---|---|---|---|---|
| broad self-join | 250 | 0.13s | **129,281** | **3** | 18 |
| broad self-join | 500 | 0.50s | **508,531** | **3** | 18 |
| broad self-join | 1,000 | 1.94s | **2,017,031** | **3** | 18 |
| `edge` chain | 250 | 0.22s | 757 | 253 | 18 |
| `edge` chain | 500 | 0.55s | 1,507 | 503 | 18 |
| `edge` chain | 1,000 | 1.83s | 3,007 | 1,003 | 18 |

> ⭐⭐⭐ **The two rows are the same wall clock and opposite mechanisms.** The `edge` chain's unifications
> are **linear** (2n + 7) and its ticks grow with n — that is the option set, and `heap` addressed it.
> The self-join's ticks are **constant at 3** and its unifications are **exactly quadratic** (4× per
> doubling, ≈ 2N²). **One tick costs a million unifications.** No option set, no arbitration and no
> candidate walk is involved: `proposed` is 18 and `applied` is 1 at every size.

**Our hypothesis about the cause**, from reading `rules.Situation`:

```python
self._by[(e.sign, g.relation_of(e.proposition))].append(e)   # the only index
```

`candidates()` keys on `(sign, relation)` and nothing else, and `match` is a nested loop over members.
So when member 0 has bound `?x`, member 1 (`child(?x, ?y)`) still draws **every instance of `child`**
and unifies each — N candidates for each of N bindings. The 2,017,031 above is ≈ 2 × 1,000², the factor
2 being the two delta pivots.

**What we think would change it: an argument-position index.** Key entries additionally by
`(sign, relation, position, node)` and let `candidates()` use the narrowest already-bound member. That
turns the inner scan into a lookup and the join into O(N × matches). It is local to `Situation`, and we
think it needs nothing from the chain, the gate or arbitration.

⚠ **We may be wrong about the fix and are fairly confident about the measurement.** In particular we
cannot see whether member order is free to be chosen — if the authored order is load-bearing for §18's
tiebreaks, picking the narrowest member changes which application is found first, and that is your
call, not ours.

**Why we are reporting it rather than working around it.** A broad structural join over one AST
relation is not a corner of what we do — **it is what recognition IS**. Every description in
`restrider/rules/patterns.ugm` has that shape. Keeping intake in Python does not help, because the cost
is in the rules that READ the graph, which is the half we most want to be rules.

⭐ **And an anchor already helps a lot, which is the good news and is also ours to do.** A description
that names a rare kind first (`for_stmt(?n)`, then `body(?n, ?b)`) has the same exponent with roughly a
20× smaller constant, and per-file it is affordable. So this is not blocking us today; it is what
decides whether a corpus-sized graph is ever reachable.

**Repro:** `python experiments/restart_scale.py` in this repo (four probes, `law` is the one).

### ⭐⭐⭐ UPDATE after `kept` — this stopped being an inference and became a CONTROLLED EXPERIMENT

`kept` made the `edge` chain **linear** (*doubling now doubles*), and we can confirm it independently:
that fixture went **6.4× faster** here and its curve flattened. The self-join, measured in the same run,
**did not move by a single unification**:

| fixture | n | before `kept` | after `kept` | `unify` before | `unify` after |
|---|---|---|---|---|---|
| `edge` chain | 250 | 0.19s | **0.07s** | 757 | 757 |
| `edge` chain | 500 | 0.64s | **0.16s** | 1,507 | 1,507 |
| `edge` chain | 1,000 | 1.97s | **0.31s** | 3,007 | 3,007 |
| broad self-join | 250 | 0.11s | 0.13s | 129,281 | **129,281** |
| broad self-join | 500 | 0.49s | 0.49s | 508,531 | **508,531** |
| broad self-join | 1,000 | 1.93s | 1.98s | 2,017,031 | **2,017,031** |

> **An intervention that made one of them linear left the other byte-identical.** `unify` counts equal to
> the digit on both sides is not a slowdown that failed to appear — it is the join path being untouched,
> which is what makes the two quadratics independent rather than two readings of one.

`law` is likewise flat across the change: 24.8s → 24.1s at 4,000, still 4× per doubling, still 3 ticks and
1 application. And `Situation._keys` still answers `(sign, relation)` and `(sign, ANY)`, so we believe §1's
diagnosis and proposed fix are unchanged by `kept` — if anything `kept` makes the index the natural place
to put it, since it is now maintained incrementally rather than rebuilt, and an argument-position bucket
would be maintained by the same `add`/`drop`.

---

## §2 ⭐ Two independent derivations of the same correction, which we think strengthens it

`weigh`'s ⚠⚠⚠ — *the benchmark that defined the wall is the unrepresentative case* — is a conclusion we
reached the same day from the other side, and neither of us had seen the other's version.

Ours (`docs/restart_port_survey.md` §6): our own §4 had measured a join with **two broad members**, and
re-reading our pattern corpus with the numbers in hand showed **not one description is written that
way**. Yours: one rule with n independent instantiations is the *maximum* of independent applicability,
and over 56 real fixtures the no-op rate inverts (89.4% vs 0.4%).

Recorded because a correction two people derive independently from different evidence is worth more
than either derivation, and because it means **neither benchmark should now be read as typical** — §1
above is offered as a third shape, not as the true one.

---

## §3 `artefact.py` answers a question we were about to ask, and one line of it is load-bearing for us

*Composing the text is a function, and §17 says a request answered by a function is exactly what a tool
is* — so the rendering is a TOOL and not a parser.

We have the same seam and had not argued for it: `restrider/emit.py` is Python, and our standing note
says the `ast` border *should* stay Python without saying why that is principled rather than expedient.
Your line is the argument. We are adopting it as the reason, and recording that the reason changed —
a rule kept for a reason that has evaporated is a rule the next person deletes.

⚠ One difference worth naming, in case it matters to your design: our tool must render an artefact
**it did not compose**, because the structure comes from backward reading and the text comes from
`ast.unparse`. So our tool is closer to `_verdict` than to a corpus function — it answers about a
subgraph rather than composing from bindings.

---

## §4 A small one: `Loader.answerer`'s callback arity differs from `Machine.answerer`'s

`Machine.answerer` documents `fn(machine, frame, entry)`; `Loader.answerer` passes `fn` straight
through, so a caller who reads the `Machine` docstring and registers through the scoped door (which
your own note says is the door to use) gets

    TypeError: <lambda>() takes 2 positional arguments but 3 were given

at the first write, from inside `gate.write`, with no indication that the registration was the problem.
It cost us one cycle. A line in `Loader.answerer`'s docstring would close it; making the two agree
would close it better.

---

## What we are NOT reporting, deliberately

`support`, `binding` revision, and loop detection all look right to us and none of them is something we
have a live need for yet. Your own §7 rule — *adopt against a live need, never for coverage* — is one
we have been burned by ignoring, so we are leaving them.


---

## §5 ⚠⚠⚠ 2026-08-20 — the table loop put a quadratic back on the `edge` shape

**Measured against `a3b5474`, bracketed to one commit, and it is not the one §1 fixed.**

`b1f7891 flip` — `Machine.run` becoming the table loop — took the `edge` chain from **5,009 `unify`
calls at n=1,000 to 3,012,011**, and 0.30s to 7.96s. Four snapshots, `rules.unify` wrapped and counted
exactly as §1 counts it, same machine, same fixture file:

| fixture | n | `ee129ba` join | `96595ca` preflip | **`b1f7891` flip → `a3b5474`** |
|---|---|---|---|---|
| broad self-join | 1,000 | 3,014 | 3,015 | **9,029** — 3× constant, still LINEAR |
| `edge` chain | 250 | 1,008 | 1,259 | **190,511** |
| `edge` chain | 500 | 2,008 | 2,509 | **756,011** |
| `edge` chain | 1,000 | 4,008 | 5,009 | **3,012,011** — 4× per doubling |

    rule <s1> = implies( { +edge(?p, ?x) }, { +seen(?x) } )
    fact +edge(base, item)
    ...N inert `edge` facts

⭐ **§1's index is intact and this is the other axis.** The self-join is still linear, which is the shape
that disqualified our port and that `join` rescued — that result survives the loop switch with a 3×
constant. What looks lost is **delta narrowing ACROSS ticks**: the `edge` chain is 1,003 ticks over n
facts, and the counts say each tick now re-derives against the whole state rather than against what
arrived. §1's quadratic was *within* one tick; this one is `ticks × facts`.

**Why we think nobody has seen it, offered as the reason it is worth a look rather than as a criticism:**
`tools_sweep.sh` runs corpora, and a corpus does not run a thousand ticks. It needs a fixture whose tick
count grows with the fact count, which is exactly the one §1 built for the opposite purpose.

⚠ **What it does NOT do, measured before filing:** it does not disqualify anything of ours. Twelve real
modules in one machine went 0.07s → 0.45s for the rules run at 47,376 nodes, because our ticks are
bounded by description sites (128) and not by graph size. The shape that would bite us is
`anchor` at 10% density — 402 ticks over 4,000 facts — which went **0.10s → 1.74s** and is quadratic
again where it was linear. `anchor` at 2% is still cheap.

⚠ **We are confident about the measurement and have NOT diagnosed the cause.** We did not read the
2,383-line `machine.py` diff; the commit was found by running four snapshots. Our standing practice
holds — four of our confident diagnoses were inverted last generation, so the hypothesis above
(*the delta pivot is not reaching the table loop's match*) is offered as a place to look and nothing
more.

⚠ **And your own number for `join` was *+16% on the `edge` chain*, stated not buried.** This is 601× on a
different commit, so we are reporting it in the same spirit: not as a cost you hid, but as one that
looks like it was never measured, because the instrument that would show it is a scale fixture rather
than a corpus.

**Repro:** `experiments/restart_scale.py`'s `pinpoint`, run against snapshots extracted with
`git archive <ref>`. ⚠ The runner hardcodes a Windows path; ours is patched at the top constant.
