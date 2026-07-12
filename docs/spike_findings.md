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
| **Modification = verify by re-execution** | `guarded_variant()` adds the effect of `if x is not None:` as monotone V2 facts; re-running the same analysis inside that edit yields **no** outcome — the loop closes. |

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

- **State-succession / the frame problem.** The spike models value flow SSA-style
  (each variable assigned once), which is sound for straight-line code but sidesteps the
  design's "mint a successor state" axis. Reassignment, loops, and general branch merging need
  the monotone state-successor structure of §2 — untested here, and the design's own biggest
  open question (guard cost of *two* monotone axes).
- **The transformation-rule library and backward means-ends.** Step 5 applied *one*
  hand-picked operator (insert guard) and verified it forward. Backward-`CHAIN` from a desired
  outcome over an effect-keyed operator library (design §3) is unbuilt.
- **The concrete-execution (concolic) tool** and the SMT/type-inference CALLs — all future.
- **Scale.** One function. The "session-sized working set" claim is untested.

None of these are blocked by what we found; they are the next slices, in the order the design
already lists them.

---

## Reproduce

```bash
pip install -e ../ugm -e .      # ugm sibling + this spike
python -m pystrider.demo        # the five-step walkthrough
pytest -q                       # the behaviour pins
```
