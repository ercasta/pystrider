# pystrider — implementation plan (continuation)

A cold-start guide for the next session. Read this, then `docs/spike_findings.md` (what's proven)
and `docs/code_reasoning_design.md` (the design + open questions). Everything below the spike is
built and green; this plan is what's next.

---

## Where we are (2026-07-12)

A working dynamic, hypothesis-driven code analyzer on ugm. The full design loop runs on a
straight-line function **with correct reassignment** (slice A landed — value flow is
state-threaded, no longer SSA-wrong):

- **intake** (`ast` → AST+CFG facts + a **CFG**: per-statement program-point *states*,
  `from_state`/`to_state` on assigns, `in_state` on every expr/guard, and a pre-materialized
  `(state × var)` **cell lattice**; scope as structural `in_function` edges) →
- **analyze** under a value hypothesis (`suppose` seeds the param's **entry-state cell** + CHAIN
  over `semantics.cnl`, whose rules thread value through cells) → an outcome with a real RECORD
  trace (`ask_goal "why"`, now showing `c_p1_y has_value none ← assign ← c_p0_x`) →
- **repair**: retrieve edit operators by effect (backward-CHAIN over `operators.cnl`),
  materialize each as real Python (AST rewrite), verify by re-intake, and **CHOOSE** the
  graded-best.

**Run:** `pip install -e ../ugm -e .` · `python -m pystrider.demo` · `pytest -q` (22 green).

**Module map**

| File | Role |
|---|---|
| `pystrider/intake.py` | §8 tool: `ast` → facts; **CFG** (states, transitions, `(state×var)` cell lattice); structural scope (`in_function`) |
| `pystrider/semantics.cnl` / `semantics.py` | operational semantics (7 Horn rules, **state/cell-threaded**, CNL data) + loader |
| `pystrider/analysis.py` | hypothesis loop on public firmware (`suppose` seeds entry-state cell / `ask_goal`) + `repair` / `choose_repair` |
| `pystrider/operators.cnl` / `operators.py` | effect-keyed operator library + backward-CHAIN retrieval |
| `pystrider/transform.py` | AST-rewrite mechanism (materialize an edit as real source) |
| `experiments/state_threading.py` | the original **probe** that validated the cell-lattice approach (now productized in intake/semantics) |
| `tests/` | `test_spike.py` (18, incl. slice-A reassignment pins), `test_state_threading.py` (4) |

**Conventions / gotchas (don't relearn these the hard way):**
- Reasoning goes through the **public firmware only** (`suppose`/`chain_sip`/`ask_goal`/`choose`).
  The one place we author the graph directly is **intake** (the §8 tool boundary). Never poke
  private helpers (`_pencil`, `_facts_matching`).
- Domain **rules** are `.cnl` files; domain **facts** with open vocabulary are materialized by
  the tool (CNL `load_facts` drops undeclared verbs). Mechanism (ast, orchestration) is Python.
  See the design doc's "Python / CNL boundary" table.
- Every machine-rule clause must be a **3-token triple** (`?g guard_open yes`, not `?g guard_open`).
- CNL queries **case-fold** identifiers → use lowercase node names (`attr5`, not `eA`).
- Abstract domain today: `none` / `object` / UNKNOWN. Value flow is **state-threaded** through
  the `(state×var)` cell lattice — reassignment is correct on straight-line code. Branch-merge
  (join over predecessor states) and loop unrolling are not yet built.

---

## ugm dependencies (verify at session start — they were in flux)

- **`focus_scope` on `suppose`/`chain_sip`/`ask_goal` — LANDED.** `suppose(..., focus_scope=frozenset(names))`
  now exists (feedback #7 fixed). Attention-bounding the outcome path is unblocked.
- **Id-addressed firmware goals — LANDED (unblocks slice B).** ugm shipped `ById(node_id)`: an
  explicit node-ID endpoint for a bound-tuple goal, accepted in `suppose` assumptions/predictions
  and `chain_sip`/`ask_goal`-materialize endpoints. `ById` PINS to exactly that node instead of the
  `nodes_named(...)[0]` silent pick, so a shared multi-function graph can hold legitimately
  distinct same-named nodes. Companions: `validate_ids` (a `ById` on a missing node raises — the
  stale-id silent→loud fix) and `resolve_write_node` (WARNS when a *name* resolves to >1 node before
  the [0]-pick). Exported from `ugm`. NB the CNL *string* `ask_goal("why …")` path is still
  name-based + case-folded — id-addressing is the tuple/firmware path. (ugm working tree, uncommitted.)
- Other feedback fixed: strict `load_machine_rules` (clause validation), `apply_*` rule-node
  `TypeError`, `load_facts(strict=)`. See `../ugm/docs/feedback_from_pystrider.md`.

---

## Next slices (recommended order)

### Slice A — `ast` state-threading in the main analyzer  ✅ **DONE (2026-07-12)**

**Goal (met).** Reassignment is now correct in the real analyzer, not just the probe. Value flow
was SSA-style and wrong on `y = a; y = b`; it is now state-threaded over the pre-materialized
`(state×var)` cell lattice (intake knows the CFG statically; rules only *bind* cells — existential
state-minting is NOT rule-expressible, feedback #2).

**What shipped.**
- `intake.py` emits a CFG: `entry_state` + one **program point** per statement, `from_state`/
  `to_state` on each assign, `in_state` on every expression + guard, and a pre-materialized cell
  per `(state, var)` (`cell_name`, exposed via `Intake.states` / `state_of` / `entry_cell`).
- `semantics.cnl` value-flow rules are state/cell-threaded: name-eval reads the var's cell **in the
  expr's state** (1); ASSIGN writes the target cell in the to-state (2); a **FRAME** NAC carries
  every other var across the transition (2b, `not ?stmt assigns ?var`); the guard reads its tested
  var's cell in the guard's state (3). Reachability/outcome (4–6) unchanged.
- `analysis.analyze` seeds each param hypothesis into its **entry-state cell** (`entry_cell`);
  `guarded_variant` stamps the guard's `in_state`.
- Pins in `test_spike.py`: reassignment-to-object clears, reassignment-to-None still raises,
  deref-before-reassignment still raises. None-deref demo + all prior pins hold (22 green).

**Left for a follow-on (branches/loops):** the `if` body currently reads at the guard's own
program point (correct for the tail-guard shape the repair emits) — no branch **refinement** (a
then-state that assumes the condition) and no **join** over two predecessor states yet; loop
unrolling to a chosen depth (the state-pool size *is* the fuel budget) is unbuilt. These are the
natural "slice A′".

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

See `docs/code_reasoning_design.md` "Open questions" — with slice A landed, the load-bearing ones
now are **branch-merge + loop unrolling / fuel budget** (slice A′: join over predecessor states,
bounded pre-materialized loop chains) and **guard cost of two monotone axes** (benchmark once
slices A′+B put states × versions in one graph).
