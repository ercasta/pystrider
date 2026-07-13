# pystrider — implementation plan (continuation)

A cold-start guide for the next session. Read this, then `docs/spike_findings.md` (what's proven)
and `docs/code_reasoning_design.md` (the design + open questions). Everything below the spike is
built and green; this plan is what's next.

---

## Where we are (2026-07-12)

A working dynamic, hypothesis-driven code analyzer on ugm. The full design loop runs with correct
reassignment (slice A), branch-merge + loop unrolling (slice A′), **several functions in one shared
graph with value flow across call boundaries** (slice B), and **a second effect kind — returns-None
— proving the operator library + retrieval + CHOOSE generalize** (slice C):

- **intake** (`ast` → AST+CFG facts + a **CFG**: per-statement program-point *states*,
  `from_state`/`to_state` on assigns, `in_state` on every expr/guard, and a pre-materialized
  `(state × var)` **cell lattice**; scope as structural `in_function` edges; call args + callee via
  `calls_func`/`passes`) →
- **analyze** under a value hypothesis — a **pure, read-only query** now (`suppose(commit=False)`
  seeds the param's **entry-state cell**, bounded by `focus_scope`; CHAIN over `semantics.cnl`
  threads value through cells) → an outcome with a real RECORD trace (`ask_goal "why"`) →
- **repair**: retrieve edit operators by effect (backward-CHAIN over `operators.cnl`),
  materialize each as real Python (AST rewrite), verify by re-intake, and **CHOOSE** the
  graded-best — for **either effect** (None-deref *or* returns-None; `candidate_edits`/`choose_repair`
  take a `provides_fn` + `analyzer`, no new machinery).
- **Session**: several functions in **one shared graph** (identity by `(function, source_name)` via
  per-function namespaces), each analyzed under its own `focus_scope`, with a `call` in `f` to `g`
  wiring `f`'s arg cell → `g`'s param cell so a value flows **across the call boundary**.
- **Second effect (slice C)**: `analyze_return_none` finds returns that yield None; authored as one
  more semantics rule (`?s returns_none yes`) + two coalesce operators — the loop is effect-generic.
- **Whole-function auto-fix**: `repair_all` drives repair as a means-ends loop toward a *clean
  function* — while any outcome (of any effect) remains, retrieve + verify edits, keep only those
  that make **progress** and introduce **no regression** (a new outcome), CHOOSE, apply, re-analyze;
  returns the clean source + an audit log (`RepairPlan`), or an honest `stuck`.

Beyond the analysis/repair loop, a **third axis — spec → code synthesis — is now probed** (2026-07-13,
`experiments/spec_synthesis.py`): a succinct spec is *expanded* by CNL refinement rules into real
Python and *verified by re-execution* (symbolic + concrete). It is analysis run backwards over the
same firmware; still a probe (like `state_threading.py`), not productized. See `spike_findings.md`
§"Follow-up: spec → code synthesis".

**Run:** `pip install -e ../ugm -e .` · `python -m pystrider.demo` · `python demos/run.py` ·
`python -m experiments.spec_synthesis` · `pytest -q` (65 green).

**Module map**

| File | Role |
|---|---|
| `pystrider/intake.py` | §8 tool: `ast` → facts; **CFG** (states, assign+branch/merge/loop transitions, `(state×var)` cell lattice, `_if` fork/join + `_while` bounded unroll); structural scope (`in_function`); call args/callee; **per-function `namespace`** so functions coexist in a shared graph |
| `pystrider/semantics.cnl` / `semantics.py` | operational semantics (**10 Horn rules**: value-flow 1–3, frame 2b + **refined frames 2c/2d** (path-sensitive), guard/reachability 3–5, the two OUTCOME rules `raises attribute_error` + `returns_none yes`, **state/cell-threaded**, CNL data) + loader |
| `pystrider/analysis.py` | hypothesis loop on public firmware — a shared `_detect` core (**`suppose(commit=False)` read-only + `focus_scope`, one KB reused across sites**, optional external `kb`); `analyze` (None-deref) / `analyze_return_none` (returns-None) / `analyze_all` (every effect); effect-generic `candidate_edits` / `choose_repair`; **`repair_all` — whole-function auto-fix to a fixpoint** (progress + regression-checked, `RepairPlan` audit log) |
| `pystrider/session.py` | **Session**: several functions in one shared graph; namespaced identity, per-function focus, cross-call value-flow linking (`link_calls` / `analyze_across_call`), label-rendered traces |
| `pystrider/operators.cnl` / `operators.py` | effect-keyed operator library (None-deref guards + returns-None coalesce ops) + backward-CHAIN retrieval (source-name ⇄ namespaced graph-id at the fact boundary) |
| `pystrider/transform.py` | AST-rewrite mechanism (guard insertion; `coalesce_return`) — materialize an edit as real source |
| `demos/` | five focused, runnable walkthroughs (core loop, state-threading, Session/inter-procedural, second effect, whole-function auto-fix) + `run.py` |
| `experiments/state_threading.py` | the original **probe** that validated the cell-lattice approach (now productized in intake/semantics) |
| `experiments/spec_synthesis.py` | **probe** for the third axis — spec → code synthesis (refinement rules + emit tool + verify-by-re-execution); the mirror of analysis, not yet productized |
| `tests/` | 65 green: `test_spike.py` (33, slice-A/A′ + branch-refinement + boundary-guard), `test_state_threading.py` (4), `test_session.py` (7, slice-B), `test_effects.py` (5, slice-C), `test_repair.py` (6, whole-function auto-fix), `test_spec_synthesis.py` (10, spec→code synthesis) |

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
  the `(state×var)` cell lattice — reassignment (A), branch-merge + loop unrolling (A′),
  **inter-procedural flow across a call** (B), and **path-sensitive fork refinement** (a `VAR is
  [not] None` fork assumes its condition per branch; refined-frame rules 2c/2d) are all correct.
- Identity across functions is by **`(function, source_name)`**: intake takes a `namespace` that
  prefixes every *structural* node id (states, exprs, cells, variables, the function node); the
  *type/value* vocabulary the rules match on (`assign`, `none`, `none_value`, `attribute_error`, …)
  stays **shared/unprefixed**. `Outcome.base_var` is a **source name**; graph-var-id translation
  (`intake.var_id`) happens only at the fact boundary (guards, operators).
- Detection is **read-only** (`suppose(commit=False)`): the shared graph is never inked, so
  functions and hypotheses never contaminate one another. Traces (which need the hypothesis present
  to re-derive) render on a private scratch KB / `graph.copy()`, never the shared graph.

---

## ugm dependencies (verify at session start — they were in flux)

- **`suppose(commit=False)` — LANDED + ADOPTED (feedback #6).** Read-only suppose: inks nothing,
  returns in-scope `derived` for inspection. `analyze` now builds one KB and reuses it read-only
  across every site (the old rebuild-per-site dance is gone), and a `Session` analyzes against a
  shared graph without contaminating it. This is what makes slice B's shared graph safe.
- **`focus_scope` on `suppose`/`chain_sip`/`ask_goal` — LANDED + ADOPTED.** `suppose(..., focus_scope=
  frozenset(names))` exists (feedback #7). `analyze` and `Session` bound each hypothesis to the
  function's working set.
- **Id-addressed firmware goals — LANDED (unblocked slice B).** ugm shipped `ById(node_id)`: an
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
  deref-before-reassignment still raises. None-deref demo + all prior pins hold.

### Slice A′ — branch-merge + loop unrolling  ✅ **DONE (2026-07-12)**

**Goal (met).** Value flow is correct across `if`/`if-else` **and** `while` loops. Both reduce to
the same primitive: intake mints fork/merge **state structure**; the value union at any join is
derived by the **frame rule firing once per incoming edge** (Horn disjunction) — *never* a
Python-computed lattice join. Intake mints only structure; ugm derives every value.

**Branch-merge.** A conditional (other than the tail `if VAR is not None:` guard, which stays
reachability-gated for the repair round-trip) forks into then/else entry points via plain
`transition` edges, threads each body, and joins into a fresh merge point (union of the branches).

**Loop unrolling.** A `while` body is **unrolled to `loop_unroll` iterations** (default 2, a param
on `intake_function`). Each unrolled head forks into *exit the loop* (edge straight to the post
merge) and *run the body once more* (thread the body → back-edge to the next head); every exit —
after 0, 1, … k iterations — flows into the same merge, so the post-loop value is the union over
all iteration counts. **The pre-materialized state-pool size IS the fuel budget** (design "fuel /
world budget", now concrete): a bug that first manifests on iteration k+1 is missed — an honest
bound, not a fixpoint. The condition is not evaluated (exit always possible → sound may-analysis).

**What shipped.**
- `intake.py`: `stmt`/`block` thread the program point explicitly (a fork-join tree, not one cursor);
  `_if` (guard vs. general fork), `_while` (unrolled chain), `_edge` (plain branch/merge/loop
  `transition`s). `intake_function(src, *, loop_unroll=2)`.
- `semantics.cnl`: the FRAME rule keys on **any CFG edge** (`?t from_state/to_state`, not
  `?stmt is_a assign`), so every join's incoming edges each frame values forward → union.
- Pins in `test_spike.py`: branch may-None via each branch + safe case; loop may-skip (pre-loop None
  survives), loop-may-null (body introduces None), loop-safe; and **`test_unroll_depth_is_the_fuel_budget`**
  — a depth-2 dependency bug is FOUND at `unroll=2`, MISSED at `unroll=1`.
- **Boundary-guard pin** (`test_intake_emits_only_structure_never_reasoning`, run over branch + loop
  shapes): asserts intake emits none of `{has_value, eval_to, guard_open, reached, raises}` — makes
  "the analysis lives in ugm, not Python" a *checked invariant*. A companion pin proves a join value
  is rule-derived (its trace threads back through a branch/loop assignment), not given. 32 green.

**Branch/path refinement — ✅ LANDED (2026-07-12).** A general fork now *assumes its condition* when
it understands it: intake tags each fork edge of a `VAR is [not] None` test with `assume_nonnull` /
`assume_null` (`_none_compare`), and two REFINED-FRAME rules (semantics 2c/2d) carry only values
consistent with the assumption across that edge — none is filtered on the non-null branch, non-None
on the null branch (the plain frame 2b gets NACs so it defers on a refined edge). So the deref on the
then-path of `if v is not None:` (even **with an else**, the old partiality #2) is precise, not a
spurious may-None, while the else-path still sees None — two-sided, both comparison directions. A
condition intake does *not* understand (`if c:`) gets no tag → the sound may-union, unchanged. Pinned
in `test_spike.py` (5). **Still open:** (3) loop `else`, `break`/`continue` are unmodelled; (4)
fixed-depth unroll is not a fixpoint — widening / UNKNOWN-on-exhaustion is the honest next refinement
of the fuel knob; (5) refinement is limited to direct `VAR is [not] None` tests (no `and`/`or`/`not`
compound conditions, no narrowing through an alias).

### Slice B — inter-procedural / persistent session graph  ✅ **DONE (2026-07-12)**

**Goal (met).** A `Session` (`pystrider/session.py`) holds several functions in one shared graph,
each analyzed under its own focus, with value flow across a call boundary.

**What shipped.**
1. **Namespaced identity.** `intake_function(src, *, namespace=…)` prefixes every structural node id
   (states, exprs, statements, transitions, cells, variables, the function node); the type/value
   vocabulary the rules match on stays shared. Identity is `(function, source_name)` → two `x`s in
   two functions are **distinct nodes in one graph** (`test_session`: `{"f0_a","f1_a"}`). Source
   names are kept as **labels**; `Session.render_trace` / `relabel_trace` render traces from them.
2. **Read-only, focus-bounded analysis over the shared graph.** `analyze(…, kb=shared, focus_scope=
   per-function)` runs `suppose(commit=False)` — nothing is inked, so functions and hypotheses never
   contaminate each other; the same function re-analyzes cleanly under a new hypothesis. (ById tuple-
   path id-addressing is available if readable duplicate names are ever wanted; namespaces made it
   unnecessary here.)
3. **Per-function focus** = the function's own entity names + the hypothesis value/outcome vocab, so
   per-hypothesis cost tracks the function, not the accreted graph. The verdict is identical to
   analyzing the function alone (`test_analysis_matches_the_single_function_result`).
4. **Inter-procedural link.** `Session.link_calls()` wires each free-function call `f: …g(a)…` to a
   known callee `g` as a cross-`in_function` **pseudo-assign** (`g`'s param entry cell := `f`'s arg
   expression); the existing ASSIGN rule then threads the value into `g`'s body — **no new
   semantics**. `analyze_across_call(caller, hyp, callee)` seeds the caller's input and finds the
   outcome INSIDE the callee; the trace threads caller-cell → link → callee-cell → deref. Without
   the link there is no phantom flow (`test_call_link_is_inert_without_wiring`).

**Left for a follow-on:** multiple call sites / recursion / a call whose result flows back into the
caller (return-value threading); today the link is one-directional arg→param. A `converse`
ask/suspend channel for concolic grounding is still future (see "Not started").

### Slice C — breadth: a second effect kind  ✅ **DONE (2026-07-12)**

**Goal (met).** The operator library + retrieval + CHOOSE + verify-by-re-execution generalize past
None-derefs.

**What shipped.**
- **New effect `returns_none`** — semantics rule (7): `?s returns_none yes when ?s is_a return and
  ?s returns ?e and ?e eval_to ?v and ?v is_a none_value`. Over the *same* value-flow rules; no new
  machinery. Intake tracks `returns` / `return_var` (structural only — the boundary-guard pin now
  also forbids `returns_none` from intake).
- **`analyze_return_none`** via a factored `_detect` core shared with `analyze` (the None-deref path
  is byte-identical — the prediction `(pred, obj)` and the `kind`/`base_of` are the only knobs).
- **Two library operators** keyed to `returns_none` (`coalesce_or` → `return v or {}`,
  `coalesce_ifexp` → `return v if v is not None else {}`) + `provides_return` + `coalesce_return`
  transform. `candidate_edits`/`choose_repair` gained a `provides_fn` + `analyzer` parameter (default
  = the None-deref effect), so the *same* retrieve/verify/CHOOSE loop serves both effects.
- **Pins** (`test_effects.py`, 5): the effect fires + is sound, the two effects are independent and
  can coexist on one function, `choose_repair` retrieves + verifies + selects the graded-best
  coalesce edit, and the None-deref selection is unchanged.

---

## Not started (design has them; lower priority)

- Concolic / SMT / type-inference **CALL** tools (design "What survives" §CALL boundary); the
  `converse` ask/suspend channel is the natural plumbing for concolic grounding.
- Monotone **code-versioning** nodes (`<version>` hyperedges, `corresponds_to` for diff/blame).
- Richer abstract domain (intervals / type-sets via CALL).

## Open questions still live

See `docs/code_reasoning_design.md` "Open questions" — with slices A, A′, B, **and C** landed, the
load-bearing ones now are **fuel-knob refinement** (fixed-depth unroll → a fixpoint / widening, or
an explicit UNKNOWN-on-exhaustion, and per-path branch refinement — including the noted partiality
that a tail `if v is not None:` guard threads its body linearly and a general fork does not assume
its condition) and **guard cost of two monotone axes**. Slice B put several functions' *states* in
one shared graph (the first axis at session scale) — the guard-cost benchmark is now runnable there;
the second axis (code *versions* as `<version>` hyperedges) is still unbuilt.

**Recommended next** (branch/path refinement now landed): either (a) **more control flow** (loop
`break`/`continue`/`else`, and compound `and`/`or`/`not` conditions for refinement — the remaining
precision gaps), or (b) **breadth via more effects/operators** (unhandled-exception paths,
early-return/default operators), or (c) the **code-versioning axis** (`<version>` hyperedges,
`corresponds_to`) to exercise the second monotone axis and the guard-cost benchmark, or (d)
**productize the spec → code synthesis axis** now probed in `experiments/spec_synthesis.py` — the
honest next steps there are a compositional skeleton pool (slot-filling beyond whole-function
templates), a real spec language (beyond one intent + one flag), and sandboxing the concrete-exec
check for non-pure fragments.
