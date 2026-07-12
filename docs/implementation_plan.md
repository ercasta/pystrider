# pystrider — implementation plan (continuation)

A cold-start guide for the next session. Read this, then `docs/spike_findings.md` (what's proven)
and `docs/code_reasoning_design.md` (the design + open questions). Everything below the spike is
built and green; this plan is what's next.

---

## Where we are (2026-07-12)

A working dynamic, hypothesis-driven code analyzer on ugm. The full design loop runs on one
straight-line function:

- **intake** (`ast` → AST+CFG facts, scope as structural `in_function` edges) →
- **analyze** under a value hypothesis (`suppose` + CHAIN over `semantics.cnl`) → an outcome
  with a real RECORD trace (`ask_goal "why"`) →
- **repair**: retrieve edit operators by effect (backward-CHAIN over `operators.cnl`),
  materialize each as real Python (AST rewrite), verify by re-intake, and **CHOOSE** the
  graded-best.

**Run:** `pip install -e ../ugm -e .` · `python -m pystrider.demo` · `pytest -q` (19 green).

**Module map**

| File | Role |
|---|---|
| `pystrider/intake.py` | §8 tool: `ast` → facts; structural scope (`in_function`, `is_a variable`) |
| `pystrider/semantics.cnl` / `semantics.py` | operational semantics (6 Horn rules, CNL data) + loader |
| `pystrider/analysis.py` | hypothesis loop on public firmware (`suppose`/`ask_goal`) + `repair` / `choose_repair` |
| `pystrider/operators.cnl` / `operators.py` | effect-keyed operator library + backward-CHAIN retrieval |
| `pystrider/transform.py` | AST-rewrite mechanism (materialize an edit as real source) |
| `experiments/state_threading.py` | **validated probe** — state-succession via pre-materialized cell lattice |
| `tests/` | `test_spike.py` (19), `test_state_threading.py` (4) |

**Conventions / gotchas (don't relearn these the hard way):**
- Reasoning goes through the **public firmware only** (`suppose`/`chain_sip`/`ask_goal`/`choose`).
  The one place we author the graph directly is **intake** (the §8 tool boundary). Never poke
  private helpers (`_pencil`, `_facts_matching`).
- Domain **rules** are `.cnl` files; domain **facts** with open vocabulary are materialized by
  the tool (CNL `load_facts` drops undeclared verbs). Mechanism (ast, orchestration) is Python.
  See the design doc's "Python / CNL boundary" table.
- Every machine-rule clause must be a **3-token triple** (`?g guard_open yes`, not `?g guard_open`).
- CNL queries **case-fold** identifiers → use lowercase node names (`attr5`, not `eA`).
- Abstract domain today: `none` / `object` / UNKNOWN. Value flow is SSA-style (sound only for
  straight-line single-assignment code — see slice B).

---

## ugm dependencies (verify at session start — they were in flux)

- **`focus_scope` on `suppose`/`chain_sip`/`ask_goal` — LANDED.** `suppose(..., focus_scope=frozenset(names))`
  now exists (feedback #7 fixed). Attention-bounding the outcome path is unblocked.
- **Id-addressed firmware goals — being added.** ugm is adding the ability to address a goal by
  node **id** instead of by name. Confirm the exact API (`suppose`/`ask_goal` accepting ids)
  before slice C relies on it. Until confirmed, keep node names unique.
- Other feedback fixed: strict `load_machine_rules` (clause validation), `apply_*` rule-node
  `TypeError`, `load_facts(strict=)`. See `../ugm/docs/feedback_from_pystrider.md`.

---

## Next slices (recommended order)

### Slice A — `ast` state-threading in the main analyzer  *(highest analysis value; no ugm dependency)*

**Goal.** Make reassignment / branches correct in the real analyzer, not just the probe. Today
value flow is SSA-style and wrong on `y = a; y = b`. The **validated** fix is
`experiments/state_threading.py`: intake pre-materializes the state×var **cell lattice** (it
knows the CFG statically) and rules only *bind* pre-existing cells — pure Datalog, frame axiom as
one NAC (`not ?t assigns_var ?v`). Existential state-minting is NOT rule-expressible (feedback
#2), so pre-materialization is the way.

**Steps.**
1. Extend intake to emit a CFG: per-statement **program points** (states) + `transition`
   facts (`from_state`/`to_state`/`assigns_var`/`reads_var`), and one **cell** node per
   `(state, var)` — reusing the probe's schema. Attribute sites get `in_state <point>`.
2. Replace `semantics.cnl` value-flow rules (1–2) with the probe's state-threaded rules
   (assign + frame + outcome, keyed on cells/states). Keep the guard/reachability rules.
3. Update `analysis.analyze` to seed the hypothesis at the **entry state's** cells and read the
   outcome at the deref's state.
4. Choose an **unrolling budget** (design "fuel / world budget") — states pre-materialized per
   statement; a loop = a bounded pre-materialized chain. Straight-line first, then a single `if`.
**Done when:** the reassignment case (`test_state_threading` shape) passes through the *main*
`analyze`, and the existing None-deref demo still holds.

### Slice B — inter-procedural / persistent session graph  *(now unblocked by focus_scope + id-addressing)*

**Goal.** A `Session` holding several functions in one graph, reasoning bounded by focus.
Foundation already laid: intake emits `in_function` scope edges.

**Steps.**
1. `Session` owns a shared graph + a global id counter. Intake mints entities with **opaque
   unique ids as names** and **source names as labels** (extend the `s1/attr5` scheme to
   variables + functions); identity keyed by `(function, source_name)`. Render traces from labels.
2. Seed/query via **id-addressed** firmware goals (once the ugm API is confirmed) so readable
   duplicate names are fine; else keep names unique via the ids above.
3. Scope each analysis with `focus_scope=frozenset(<function's entity names>)` so per-hypothesis
   cost tracks the working set, not the accreted graph.
4. Inter-procedural link: a `call` in `f` to `g` wires `f`'s arg cell → `g`'s param cell (a
   cross-`in_function` edge) — the payoff of structural scope over name-mangling.
**Done when:** two functions coexist in one graph, each analyzes correctly, and a value flows
across a call boundary.

### Slice C — breadth: a second effect kind  *(low-risk validation; small)*

**Goal.** Prove the operator library + retrieval generalize past None-derefs. Add one new
outcome (e.g. **wrong return value** — "returns None when a non-None was intended", or an
**unhandled exception** path) with its own semantics rule(s), and 1–2 operators in
`operators.cnl` keyed to the new effect (e.g. change-default, early-return). No new machinery —
authoring in the `.cnl` + a strategy function in `operators.STRATEGIES`.
**Done when:** `choose_repair` retrieves and selects an edit for the new effect, verified by
re-execution, with the None-deref path unchanged.

---

## Not started (design has them; lower priority)

- Concolic / SMT / type-inference **CALL** tools (design "What survives" §CALL boundary); the
  `converse` ask/suspend channel is the natural plumbing for concolic grounding.
- Monotone **code-versioning** nodes (`<version>` hyperedges, `corresponds_to` for diff/blame).
- Richer abstract domain (intervals / type-sets via CALL).

## Open questions still live

See `docs/code_reasoning_design.md` "Open questions" — the load-bearing ones now are the
**unrolling/fuel budget** (slice A) and **guard cost of two monotone axes** (benchmark once
slices A+B put states × versions in one graph).
