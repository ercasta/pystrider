# Feedback for `../ugm@restart` — from `pystrider`/`restrider`, 2026-08-13

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
