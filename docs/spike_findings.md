# Spike findings — is the dynamic UGM-for-code design feasible?

**Verdict: yes, the core bet holds.** A ~250-line spike (the `pystrider` package) intakes a
real Python function, reasons about it under a value hypothesis by running an operational
semantics expressed *as UGM rules*, reaches the correct runtime outcome (`AttributeError`),
renders a human-readable execution trace that is **real UGM provenance** (not hand-built),
does not over-fire on a benign hypothesis, and confirms that a guard-insertion edit clears
the outcome under re-execution. All five steps of the design's vertical spike pass, pinned by
tests (`tests/test_spike.py`, 6 passing) and shown live by `python -m pystrider.demo`.

Crucially, this validates the design's *distinguishing* claim. UGM already ships a **static**
code probe (`ugm/tests/test_code_frames.py`) that matches hand-authored CPG frames with
`run_rules`. This spike instead runs the **dynamic / hypothesis-driven** loop the design
proposes as the supersession: `SUPPOSE` a value → `CHAIN` the semantics → read the outcome.
That loop works on the public firmware.

---

## What was proven, claim by claim

| Design claim | Spike evidence |
|---|---|
| **Intake = §8 tool, AST+CFG only, no DFG** | `intake.py` walks `ast` and materializes 17 facts for `def f(x): y=x; return y.bar()` — no def-use overlay; value flow is left to the rules. |
| **Operational semantics as reified rules** | `semantics.py` is 6 Horn rules in machine-rule CNL (`?e eval_to ?v when …`). Value flow is *computed by executing them*, exactly as the design's §2 predicts ("the DFG dissolves"). |
| **SUPPOSE is the method** | `analyze()` opens the hypothesis world with the public `suppose(...)`; the outcome is its CONFIRMED verdict. No graph poking. |
| **Outcome = a runtime behavior under a hypothesis** | Under `x=None`, `attr5 raises attribute_error` is derived and CONFIRMED. |
| **RECORD → human trace** | `ask_goal(kb, "why attr5 raises attribute_error")` returns the full derivation tree: `x=None → e2 evals None → y binds None → e4 evals None → y.bar on None → AttributeError`. This is the design's "great fit for RECORD-as-explanation" — realized verbatim. |
| **Agent, not theorem prover** | Demand-driven `suppose`/`chain_sip`; only the hypothesized site is explored. A benign hypothesis (`x=object`) derives nothing — no path explosion, no over-firing. |
| **Modification = verify by re-execution** | `repair()` **materializes a real edit** — an AST transformer wraps the deref in `if y is not None:` and unparses V2 Python — then re-intakes that *edited source* and re-analyzes; the outcome is gone. The edit is trusted because it clears on the actual transformed code, not because the operator claims it will. |
| **Effect-keyed operator library + backward-CHAIN retrieval (§3 step 2)** | `operators.py` holds operators as data keyed by `prevents attribute_error` with preconditions; `retrieve()` backward-CHAINs `who applies_to <site>` to pull only applicable operators (precondition-discriminated — a direct param deref retrieves only the local guard). |
| **CHOOSE among candidate edits (§3 step 3)** | `choose_repair()` verifies each retrieved edit and uses the public **CHOOSE** firmware mode to pick the most-local/smallest (`guard_base`, fit 1.0), retaining the beaten alternatives (fit 0.7, 0.5) in an auditable trace. |

The trace, produced by the engine:

```
attr5 raises attribute_error  <- rule.?e.raises.attribute_error
  e4 eval_to none  <- rule.?e.eval_to
    y has_value none  <- rule.?var.has_value
      s1 assigns y  (given)
      e2 eval_to none  <- rule.?e.eval_to
        e2 reads x  (given)
        x has_value none  (given)
  attr5 reached yes  <- rule.?e.reached
  attr5 attr_of e4  (given)
  none is_a none_value  (given)
```

---

## The fact vocabulary (as-built)

Intake materializes a small, stable predicate set. Structure only — no values.

| Predicate | Meaning |
|---|---|
| `X is_a {function,assign,return,name,attribute,call,none_value,object_value,guard}` | node kind |
| `F has_param V` | function parameter |
| `S assigns V` / `S from_expr E` | assignment target / RHS expression |
| `S returns E` | return expression |
| `E reads V` | a Name expression's variable |
| `E attr_of E'` / `E attr_name A` | attribute access base / name |
| `E calls E'` | call target |
| `E within_guard G` / `G tests V` | guard structure (added by the modification operator) |

Reasoning-time predicates the *rules* derive (never materialized by intake): `has_value`,
`eval_to`, `guard_open yes`, `reached yes`, `raises`.

---

## Gotchas discovered (feed these back into the design)

1. **Facts with arbitrary predicates must be *materialized*, not loaded as CNL.** `load_facts`
   only recognizes a `S P O` line when the verb is in the lexicon or declared (`V is a
   relation`, regenerating surface forms in a second pass). For a code vocabulary
   (`assigns`, `reads`, `attr_of`, …) that is heavy plumbing, and the design already reserves
   intake as a **"§8 tool, not CNL"** — so materializing structure is the faithful choice and
   the one place we author the graph directly. `is a` → `is_a` *does* parse, so the lattice
   type facts could be CNL, but uniform materialization is simpler.

2. **Every machine-rule clause must be a 3-token triple `S P O`.** A boolean-shaped predicate
   needs an explicit object: write `?g guard_open yes`, not `?g guard_open`. A 2-token clause
   is silently mis-parsed — the following keyword (`when`/`and`) is eaten as the object, so the
   clause either vanishes or corrupts the rule. This cost real debugging time; document it in
   the semantics-authoring guide.

3. **NACs fire under the demand-driven path.** `not ?e within_guard ?g` (unbound object)
   correctly blocks under `suppose`/`chain_sip`, and the bank stratifies without hand-holding.
   The reachability model (guard opens ⇒ reached; unguarded attr ⇒ reached) rests on this.

4. **`suppose()` commits the assumption to ink on CONFIRM.** Convenient (ordinary `ask_goal`
   then re-derives the trace), but it mutates the KB — so the analyzer rebuilds a fresh KB per
   site. For a real session-scale tool, a non-committing "just tell me the in-scope verdict"
   entry point would be cleaner than round-tripping through ink.

---

## What the spike deliberately did NOT prove (the honest edges)

- **State-succession / the frame problem.** The main spike models value flow SSA-style
  (each variable assigned once). A **follow-up probe** (below) went further and settled the
  design's biggest open question — with a twist: "mint a successor state" is *not* expressible
  as a rule, but a clean workaround preserves feasibility.
- **The transformation-rule library and backward means-ends.** All three §3 steps now run:
  (2) operators are a **data library keyed by effect** (`prevents attribute_error`) with
  preconditions, **retrieved by backward-`CHAIN`** from the desired outcome (`operators.py`,
  `retrieve` via `ask_goal "who applies_to …"`) — an operator whose precondition the site can't
  provide is never retrieved (a direct param deref pulls only the local guard); (3) the retrieved
  edits are **CHOSEN** graded-best via the public CHOOSE mode; (4) each is **materialized as real
  source and verified by re-execution**. What is left is not a missing *step* but *breadth*:
  one effect kind (`attribute_error`) and three guard operators. Adding effects (e.g. wrong
  return value) and operators (change-default, early-return) is now authoring in the library +
  a strategy function — no new machinery.

  > **Update (slice C, 2026-07-12).** Confirmed: a **second effect kind** (`returns_none` — a
  > function returns None when a non-None was intended) landed as exactly one more semantics rule +
  > two coalesce operators, reusing the whole retrieve/verify/CHOOSE loop. `analyze_return_none`
  > shares a factored `_detect` core with the None-deref `analyze`; `candidate_edits`/`choose_repair`
  > took a `provides_fn`+`analyzer` parameter. No new machinery, as predicted. Pinned in
  > `tests/test_effects.py`.
- **The concrete-execution (concolic) tool** and the SMT/type-inference CALLs — all future.
- **Scale.** One function. The "session-sized working set" claim is untested.

None of these are blocked by what we found; they are the next slices, in the order the design
already lists them.

---

## Follow-up: state-succession (the frame problem) — a wall *and* a way through

Probe: `experiments/state_threading.py`, pinned by `tests/test_state_threading.py` (4 tests).
Test case is the reassignment the SSA model gets wrong:

```python
def f(x, z):
    y = x       # y = None
    y = z       # y reassigned to a non-None object
    return y.bar()   # must NOT raise
```

**Finding 1 — the wall.** The design's §2 move "**mint a successor state**" cannot be written
as an ordinary Horn rule. An existential head variable (`?s next_state ?s2`, `?s2` RHS-only) is
**not Skolem-minted** by ugm's public rule drivers: `chain_sip` collapses `?s2` onto the
demand goal's object (SIP), and `run_rules`/`run_bank` derive nothing. Two different firings
share one node — no fresh state per statement. (Logged as issue #2 in
[`../../ugm/docs/feedback_from_pystrider.md`](../../ugm/docs/feedback_from_pystrider.md).)

**Finding 2 — the way through.** Move the minting to the **intake tool**, which already knows
the CFG statically. Intake **pre-materializes the state×var "cell" lattice** (one node per
`(program-point, variable)`); the semantics rules then only *bind* pre-existing cells — pure
Datalog, no existential heads. The frame axiom is a single NAC: carry a variable's value across
a transition that does **not** assign it —

```
?c2 has_value ?val  when  <transition s1->s2>  and  ?c1 in_state ?s1 and ?c1 for_var ?v
                          and ?c1 has_value ?val  and  ?c2 in_state ?s2 and ?c2 for_var ?v
                          and not ?t assigns_var ?v
```

This threads correctly: `y = None` at p1, `y = obj` (and **not** None) at p2 after the
reassignment, `x` framed forward unchanged, no false AttributeError at the p2 deref — but a
real one if the deref is moved to p1. All four pins pass.

**What it means for the design.** The "two monotone axes, both mint-successor" framing of §2 is
half-wrong: **execution states cannot be minted by rules; intake pre-mints them.** This is
actually a *good* constraint — the size of the pre-materialized state pool **is** the
fuel/unrolling budget (a loop becomes a bounded pre-materialized state chain), which unifies the
"state-succession" and "fuel/world budget" open questions into one knob set at intake time. It
does *not* touch the "owns no engine code" line (the minting stays in the intake tool, the
sanctioned §8 boundary) — but it does retire the idea that states thread themselves via rules.

Still unproven past this probe: deriving the cell lattice + transitions from real `ast`
(the probe hand-builds the CFG), branch-merge (two predecessors → a join rule over cells), and
loop unrolling to a chosen depth.

> **Update (slice A, 2026-07-12).** The first of these is now **productized**: `intake.py` derives
> the states / transitions / cell lattice from real `ast`, and the *main* `analyze` threads value
> through them (`semantics.cnl` rules 1–3 rewritten to bind cells, frame axiom as one NAC). The
> reassignment case that motivated the probe now passes through the production analyzer, pinned in
> `tests/test_spike.py`. `experiments/state_threading.py` remains as the original feasibility probe.
> Branch-merge (join over predecessor states) and loop unrolling are still open.

---

## Follow-up: spec → code synthesis (a third axis) — feasible, and the mirror of analysis

Probe: `experiments/spec_synthesis.py`, pinned by `tests/test_spec_synthesis.py` (10 tests).
Question: is a succinct **technical specification**, *expanded by CNL rules* into real code, a
worthwhile third axis? **Verdict: yes — and it reuses the entire firmware.** Synthesis is analysis
run backwards:

| analysis (built) | synthesis (this probe) |
|---|---|
| `ast → facts` (intake, a tool) | `spec-facts → ast → source` (an *emit* tool — the boundary in reverse) |
| operational semantics as Horn rules | **refinement** rules *expand* a succinct spec |
| operator lib keyed by *effect prevented* | skeleton lib keyed by *intent realized* |
| SUPPOSE → CHAIN → **CHOOSE** a repair | (spec) → CHAIN refine → **CHOOSE** an expansion |
| RECORD → execution trace | RECORD → **spec→code rationale** trace |
| verify a repair by re-execution | verify a spec by re-execution (the *same* analyzer) |

**Intent:** `lookup_with_default` — return a possibly-None input, or a non-None `{}` default, never
None. The refinement rules (five Horn clauses) *decompose* the intent into concrete required
features, then *realize* it: a skeleton realizes a spec iff it is for that intent and MISSES none of
the required features. `who realizes <spec>` backward-CHAINs this — the exact mirror of
`who applies_to <site>` operator retrieval. CHOOSE grades the realizers by compactness.

**The non-trivial finding — a strictness flip verified two ways.** `return v or {}` and
`return v if v is not None else {}` are **not** equivalent: on a *falsy* non-None input (`0`, `""`,
`[]`), `v or {}` silently returns `{}` — it fails to *preserve* the input. So a spec that also
requires `preserves_input` excludes the compact `coalesce_or` outright and flips CHOOSE's winner to
the explicit ifexp. This forced the refinement rules to handle a **conjunction of requirements** (a
skeleton must provide *every* one), expressed as **stratified negation** (`realizes` iff it `misses`
nothing — `misses` via `lacks` via `not provides`, two levels of NAC) — which ugm's backward-CHAIN
stratifies correctly. And the flip is validated by execution, not annotation:

- **symbolic** — re-intake the emitted source + run the existing `analyze_return_none` (input IS
  None): confirms `nonnull_return`.
- **concrete** — RUN the emitted function on a falsy-non-None sentinel (the design's concrete-exec
  tool in miniature; safe on our own pure, side-effect-free skeletons): confirms `preserves_input`.

`coalesce_or` PASSES the symbolic check yet FAILS the concrete one — exactly why the strict spec
excludes it. The rule-level `provides` annotation is checked by execution, never merely trusted.

**The pre-mint constraint reappears — and that is the reassuring part.** Generating fresh code nodes
(new statements/variables) is the SAME existential-minting wall Finding 1 hit: ugm rules cannot
Skolem-mint. So, exactly as intake pre-mints the state×var lattice, the emit tool pre-mints a bounded
pool of candidate code **skeletons** and the rules only *select* among them; the skeleton-pool size
IS the synthesis fuel budget (mirror of state-pool = unroll budget). The honest scope of a first
slice is therefore **template/skeleton synthesis over a tiny intent vocabulary**, not free-form
codegen. Still a probe (like `state_threading.py`); not yet productized into the package. **Still
open:** deriving the skeleton pool compositionally (slot-filling beyond whole-function templates), a
real spec language beyond one intent + one flag, and the concrete-exec tool's sandboxing for
non-pure fragments.

## ugm issues found

Six bugs / limitations / surprises hit while building this are written up with minimal repros in
[`../../ugm/docs/feedback_from_pystrider.md`](../../ugm/docs/feedback_from_pystrider.md) — most
are **silent-failure** modes (mis-parsed rule clauses, undropped facts, case-folded queries,
un-minted existentials). None blocked the spike, but a strict/verbose mode in ugm would have
saved most of the debugging time.

---

## Reproduce

```bash
pip install -e ../ugm -e .      # ugm sibling + this spike
python -m pystrider.demo        # the five-step walkthrough
pytest -q                       # the behaviour pins
```
