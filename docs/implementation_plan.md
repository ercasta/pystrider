# pystrider — implementation plan (continuation)

A cold-start guide for the next session. Read this, then `docs/spike_findings.md` (what's proven)
and `docs/code_reasoning_design.md` (the design + open questions). Everything below the spike is
built and green; this plan is what's next. The *strategic* layer — which product this becomes and
in what phase order — is `docs/roadmap.md` (2026-07-14); this file stays tactical.

---

## Current work line — the grammapy convergence (2026-07-14)  ← START HERE

The active work is a NEW line. **grammapy was absorbed in-repo** (top-level peer package `grammapy/`,
`import grammapy`, no external install) and pystrider + grammapy are being wired into one loop:
**pystrider REASONS** what deviates from default (deontic obligations, defeasible preferences, bridges);
**grammapy's sound-composition algebra** — four combinators (`Choice`, `Accumulate`, `Scope`, `Fold`)
plus §12 cross-cutting constraint resolution — **RESOLVES and GATES** every decision point; and the
emitted app is **verified by DRIVING it** (Textual Pilot). Full design, status, and the phased plan:
**[`grammapy_convergence.md`](grammapy_convergence.md) — read that first for this line.**

**Status: Phases 1–5 DONE; bridges-vs-channels RESOLVED + collapse ENACTED (suite 254 green).** All four
combinators are built and exercised by one app (`experiments/app_synthesis.py` — synthesize a runnable Textual cash-withdrawal app
across bridged business/framework/UX vocabularies, verified by driving). §12 resolution unifies the four
decision points under one `DeviationSpec` (`assemble`); **emission is AST-built** (`assemble_ast(dev)`
composes `ast` fragments into an `ast.Module`, unparsed; string templates retired); and **footprint
honesty is checked by execution** (`experiments/footprint_honesty.py` — grammapy admits by *declared*
footprints, pystrider's concrete-exec oracle certifies the declarations and rejects a composition grammapy
admitted from a dishonest atom). **Phase 5 steps 5–6 landed** — an external generator front-end
(`experiments/generator_frontend.py`) drafts a design from intent and is gated by four trusted layers it
doesn't control (the derived obligation, grammapy Scope + Accumulate, the Pilot), with a reasoning-repair
back-edge; an unreliable proposer + trusted disposers = trustworthy output. **Phase 5 complete — the
north-star loop is closed.** **Next: the perf mitigation (`chain_sip` / await ugm #13), a real LLM in the
generator seam, or libcst** (round-trip of user-owned atom bodies) — see the convergence doc.

**Run:** `./.venv/Scripts/python.exe -m pytest -q` (254 green) · `python -m experiments.app_synthesis`
· `python -m experiments.footprint_honesty` · `python -m experiments.combinators_as_cnl`
· `python -m experiments.generator_frontend` (the closed loop: generator → gates → drive → repair)
(the walkthrough) · combinator tests: `tests/test_disjointness.py` (Accumulate), `test_choice.py`,
`test_scope.py`, `test_fold.py`, `test_resolution.py` (§12).

**Bridges-vs-channels — RESOLVED + FULLY ENACTED (collapse into CNL).** The two live in different engines
(bridges = CNL facts; channels = Python checks); all four grammapy combinators are Datalog-shaped, so the
unification target is **CNL rules over the one ugm graph** (the "type" question dissolves — types are
facts, compatibility a rule). The real seam is **reason-about-it (CNL) vs run-it (Python)**, not pystrider
vs grammapy. **Enacted for all four:** grammapy imports ugm; `grammapy/_cnl.py` runs rule banks read-only
(`ask_goal(commit=False)`) — Accumulate (`disjoint_writes`/`_DISJOINT_WRITES_RULE`, `?a != ?b`), Scope
(`unhandled_emissions`/`_UNHANDLED_RULES`, closure + `not handled`), Choice (`guard_coverage`/`_GUARD_RULES`,
overlap `?p != ?q` + gap negation + unknown), Fold (`lattice.fold_winner`/`fold_unknowns`, `outranks`
closure + `not beaten` winner). Public return types + messages preserved; all suites green. Unblocked by
ugm feedback #11 (`?a != ?b`) + #12 (read-only `ask_goal`). **Cost (real):** a CNL check is ~1150× slower
than the old Python one-liner — a single check ~3.2ms, entirely `ask_goal` (~2.8ms fixed floor); the suite
went ~55s→~255s. Filed as ugm #13; our-side mitigation = switch `_cnl.derive` to the `chain_sip` tuple path
(~2.7×). Fine off the hot path; revisit before checks land in a per-candidate drive loop.

### Roadmap Phase 0 — harden the trust core (STARTED 2026-07-14; suite 259)

`docs/roadmap.md` promoted **Phase 0 (harden the disposers) to "do first."** First slice DONE — the
three interlocking oracle holes it named:
- **Liveness in the drive oracle.** `VerifyResult` now carries `live` alongside `ok`: `ok` is the
  SAFETY contract (unchanged — no ungated irreversible withdrawal), `live` is the LIVENESS contract
  (driving the affirmative/proceed button, the withdrawal COMPLETES). Safety alone was vacuously
  satisfied by a DEAD app (a confirm screen with no proceed button — `("cancel","back")` — was
  certified `ok=True` while withdrawing nothing). Liveness is measured on its own happy-path drive, so
  it holds even when a caller drives the abort path. (`experiments/app_synthesis.py`.)
- **GATE 4 is now a real rejector.** `generator_frontend.gate` rejects on `¬live` (new
  `pystrider/Pilot-liveness` verdict); a new `sterile_generator` drafts the dead app, slips past the
  obligation + Scope + Accumulate, and is caught ONLY at the Pilot — then repaired by reasoning.
- **Gate the emitted artifact, not the draft.** `gate` now runs Accumulate on `_ordered_buttons(
  emit_spec)` (the preference-resolved set that ships) and drives the emitted `emit_spec`, closing the
  `draft.buttons or None` gap where the gate certified a different button set than emission shipped.

Pins: `test_app_synthesis.py::test_a_dead_confirm_screen_is_safe_but_not_live` (+ live/abort-path
companions); `test_generator_frontend.py::test_sterile_generator_is_caught_by_the_liveness_gate`,
`::test_the_gated_button_set_is_the_one_that_ships`.

Second slice DONE — **oracle contracts written** (`docs/oracle_contracts.md`, critique rec #6): every
verdict surface (forward analyzer, Pilot `ok`/`live`, the four grammapy gates, footprint honesty, the
obligation gate, conformance, verify-by-re-execution, diagnosis) now has a stated contract — *a pass
proves X / does NOT prove Y / bounded by Z* — and the **diagnosis axis is named in `docs/`** for the
first time (it lived only in a probe docstring). The "every verdict surface ships its contract" Held
Line (`roadmap.md` #2), made a maintained document.

Third slice DONE — **`repair_all` verifies under a swept hypothesis space** (critique residual (b)).
New `sweep_hypotheses(intake)` enumerates the parameter × `VALUE_KINDS` product (bounded by `cap=64`;
all-object + one-None-each fallback above it) — the mirror of `conformance_strider.sweep_scenarios`.
`repair_all`'s no-regression gate now re-verifies each surviving candidate over the whole input space
(`regressions_over_sweep` / an inlined precomputed-baseline variant in the hot loop), so an edit that
clears the seeded bug but plants a new one reachable only when a *different* parameter is None is
rejected — where the single-seeded-dict check passed it blind. Guards/coalesce are monotone (they only
remove outcomes), so no current operator regresses under the sweep → existing repairs still reach clean;
the gate's teeth are pinned directly on `regressions_over_sweep` (a hand-crafted regressing edit).
Perf: the sweep's marginal cost is ~`|sweep|×2` extra `analyze_all` calls per step (~25ms on the README
example), riding the existing CNL per-check floor (ugm #13, Phase 1) rather than adding an order of
magnitude. Pins: `tests/test_repair_verification.py` (4 new — enumeration, cap fallback, the swept-catch,
monotone-still-clean). **PHASE 0 COMPLETE.**

**Phase 0 residual still open (NOT part of (b)):** the single-site `repair`/`candidate_edits`/
`choose_repair` path still verifies under the one passed hypothesis — the sweep was wired into
`repair_all` (the productized driver the roadmap names) only. `sweep_hypotheses` /
`regressions_over_sweep` are public, so adopting the sweep single-site later is a small follow-on.

### Roadmap Phase 2 Track A — the KB pipeline: extracted KBs (STARTED 2026-07-14)

**PHASE 0 DONE → moved to Phase 2 (the KB pipeline, the gate before both wedges).** Track A =
extracted KBs: productize `absorb(module)` (`docs/api_absorption_design.md` slices 3–4). **Slice 3
DONE** — `pystrider/absorb.py` (+ `tests/test_absorb.py`, 10 pins):
- `absorb(class|module) -> FactBank` reflects a live-annotated surface into `has_method` +
  `returns_optional yes|no` facts via `typing.get_type_hints` — the §8 boundary at the TYPE level, the
  reverse-intake tool. **Never runs library code**; reads declared hints only.
- CONSERVATIVE by construction: `Any` / missing / unresolvable-forward-ref returns are OMITTED and
  surfaced in `FactBank.omitted` (the caveat discipline, never guessed); a `Union`-vs-generic check
  stops `Generator[None,…]` being mistaken for Optional. `FactBank.version` keys the bank for
  cache-invalidation.
- Proven on a REAL installed library dependency-free (`textual.Widget` — 73 optional-returning public
  methods), and end-to-end: a GENERATED `returns_optional yes` fact drives the UNCHANGED slice-2
  None-deref effect (`experiments/api_absorption.py::analyze_with_absorption` now takes an explicit
  bank; `main()` PART 2 shows it). Suite 263 → 273.
- Honest edge: LIVE introspection needs resolvable annotations — builtins/stdlib carry Optional-ness
  only in typeshed `.pyi` stubs (`dict.get` has no live hint), and a string forward-ref to a
  *locally-scoped* class won't resolve (omitted, correctly). A **stub-parsing source** (`.pyi` via
  `ast`) is the named follow-on for the builtin surface (design §3.1).

**Slice 4 DONE** — the `method_not_found` effect (`experiments/api_absorption.py::find_method_not_found`,
`tests/test_method_not_found.py`, 7 pins). A SECOND library-shaped effect from the absorbed `has_method`
facts, no per-library rule: a `?attr raises method_not_found` rule flags a method CALL whose receiver
type lacks the method. Receiver type via a one-hop fixpoint `infer_types` — given param type, or the
absorbed RETURN type of a call assigned to a var (`r = s.repo()` → `r: _DemoRepo`, the design's headline
"returned type" case, using intake's `assign from_expr call` link + slice-3 `returns` facts). Also fixed
slice-3's `has_method` to be TYPE-keyed (`(Type, has_method, m)`, per design §2.B) and added `returns`
facts to `absorb`. CALLED-node restriction + unknown-type conservatism = no false positives. Detection
only — a method_not_found *repair* has no obvious local synthesis (unlike coalesce); noted, not built.
Suite 273 → 281.

**Track A follow-ons (optional, unbuilt):** slice 1 (value-domain growth: constants + comparisons, for
conformance on real Python text); a `.pyi` stub-parsing source to absorb builtins/stdlib (`dict.get`)
live introspection can't reach; `has_attr` absorption to extend method_not_found to plain field reads.

### Roadmap Phase 2 Track B — rulestrider (the KB-ingestion QA gate) (STARTED 2026-07-14)

The roadmap elevates rulestrider from side-spike to product-critical: the anomaly checks become the
**ingestion gate for LLM-authored CNL knowledge** (a KB that survives them + human review is trustworthy
by the same argument the codegen loop uses). The pystrider spike MIRRORED onto a rule bank — **no
`intake.py`, no `semantics.cnl`** (the artifact is already CNL; ugm reifies it as ground structure, the
homoiconic payoff). **Slice 1 DONE** — `experiments/rulestrider.py` (+ `tests/test_rulestrider.py`, 7):
- The first bug class — **wrong outcome / over-firing** — detected exactly as pystrider detects a deref:
  `check(suite, policy)` SWEEPS an expected-outcome scenario suite, `derive`s each decision READ-ONLY
  (`commit=False` — no materialization, the pystrider discipline), compares to the intended outcome, and
  renders the `why`-trace of each divergence.
- The planted defect is feedback #1's own class — a **dropped body condition** (loyalty rule ships
  `big_spender` only, intended `premium AND big_spender`) → over-fires for a non-premium big spender. The
  sweep isolates exactly that scenario; the `why`-trace shows the rule firing with `premium` ABSENT — the
  provenance IS the diagnosis. The FIXED policy clears the suite; detection also catches under-firing.
- Mechanics learned (ugm): `why` must render on a FRESH graph — a prior `commit=True` query materializes
  the derived fact so a later `why` collapses to `(given)`; and `ask_goal(..., provenance=True)` currently
  raises `KeyError` on a shared object node (a ugm bug to file). Read-only `commit=False` + fresh-graph
  `why` is the working pattern. Suite 281 → 288.

**Track B NEXT:** slice 2 — the ORACLE-FREE anomaly meta-rules (contradiction pairs, dead/shadowed rules,
coverage-gap sweep over `full_sweep`), the homoiconic checks that need NO test cases (what makes this an
*ingestion* gate, not a regression suite); then slice 3 — rule repair operators (strengthen-body,
add-exception via ugm defeasibility), retrieved by effect key, verified against the whole suite, CHOSEN
minimal (reusing the pystrider repair machinery — `choose_repair` already takes a pluggable analyzer).
The homoiconic meta-rules need ugm's rule-reification vocabulary (`rl_lhs`/`k_pred` per the critique) —
probe it first.

### Roadmap Phase 3 — the generation wedge: mode-1 spec→code (the CODE GENERATION track, resumed 2026-07-14)

Resumed the code-generation line (the app_synthesis/generator_frontend loop Phase 0 hardened). Phase 3
is mode-1 pure-derivational spec→code; its headline deliverable is the artifact no LLM regeneration can
produce. **Re-derivation diff DONE** — `experiments/rederivation.py` (+ `tests/test_rederivation.py`, 7):
`rederive(before, after)` runs `synthesize` on both specs and diffs three things in lockstep — the SPEC
delta (which succinct sentence moved), the DECISION delta (which resolved decision points re-resolved:
screen / confirm_buttons / confirm_policy / effect_handling, each still forced/defaulted, never guessed),
and the emitted SOURCE delta (unified diff) — with each changed decision carrying its WHY (the RECORD
derivation: the screen flips to `confirm_screen` *because* `withdrawal is_irreversible` fires the deontic
obligation, reached through the framework bridge). Both before+after apps are Pilot-verified (`verified`
= both ok AND live, using the Phase-0 liveness), so it is a *verified* code change; a no-op spec change
re-derives to an empty delta (determinism). This is the "policy change → verified code change" artifact,
made runnable. Suite 288 → 295.

**Phase 3 NEXT (roadmap work items):** the REFUSAL UX (an uncovered spec region → a named gap "no
fragment provides X; a KB entry of shape Y would fill it" — held line #3, and the on-ramp to Track C /
the hole mode 2 hands an LLM); deepen expansion (more deontic rules / bridges / decision points on the
Phase 2 harness); a SECOND scaffold family generated from a Track-C fragment KB without touching engine
code (proof the fragment KB, not the probe, does the work — depends on Track C).

The pre-convergence pystrider loop (below) is unchanged and green — the substrate this line builds on.

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

- **Distinctness `?a != ?b` + read-only `ask_goal(commit=False)` — LANDED (ugm feedback #11, #12,
  2026-07-14).** `?a != ?b` in a rule body is a distinctness condition honoured by the join (identity
  semantics; loud on unsupported shapes — in a head, under `not`, a literal/unbound side). `ask_goal(...,
  commit=False)` is read-only (ephemeral pencil scope) for yes/no + who questions — but a `why`/n-ary
  render RAISES under `commit=False` (it materializes). These unblocked the composition-checks-as-CNL
  collapse (see `experiments/combinators_as_cnl.py`).
- **`rules` is KEYWORD-ONLY on `suppose`/`chain_sip` (ugm "firmware over ISA", `0709c74`, 2026-07-14).**
  The signature is now `suppose(fact_g, assumptions, predictions, *, rules=None, …)`; `ask_goal` is
  unchanged (positional `rules`). pystrider's `suppose(kb, rg, assumptions=…)` call sites were adapted to
  `suppose(kb, assumptions, predictions, rules=rg, …)` (`analysis.py`, `session.py`,
  `experiments/api_absorption.py`). If a cold suite shows `TypeError: suppose() got multiple values for
  argument 'assumptions'`, ugm changed the firmware signature again — re-check against `import ugm;
  inspect.signature(ugm.suppose)`.
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
