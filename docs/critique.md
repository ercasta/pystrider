# A critique of pystrider (and the ugm engine under it)

*Written 2026-07-12; revised 2026-07-13 against the working tree at that date (102 tests
collected and green, including the uncommitted path-sensitive-cross-call and minting-comparison
slices; README says 101). Empirical checks re-run for this revision: a single `analyze` of the
4-line README example takes ~1.4s over 74 facts (unchanged per-fact cost since yesterday); the
full suite now runs in ~295s (vs. ~75s for 49 tests yesterday — 2.1× the tests, 3.9× the time).*

*Revised again 2026-07-14 against the working tree at that date: 246 tests collected and green
(2.4× yesterday's count), suite ~140s — the rule-bank memoization (weakness #4, now addressed)
cut a ~376s peak to ~24s at the then-110 tests; the growth back to ~140s is new work (Pilot-driven
app tests, CNL-collapse checks), not the old constant returning.*

---

## What changed since the first version (one day, a lot)

The 2026-07-12 critique was written against a three-slice analyzer + single-site repair. Since
then:

- **A third axis — spec → code synthesis — appeared and was probed end-to-end four times**
  (`spec_synthesis`, `codegen_understand`, `controlflow_synthesis`, `multifunction_synthesis`):
  whole-function templates, then compositional recipe expansion from a business rule with
  round-trip recognition, then synthesized control flow with demand-driven pool minting, then a
  synthesized helper verified *across a call boundary* through the productized Session.
- **Whole-function repair (`repair_all`) landed productized**, driving repair to a fixpoint with
  cross-effect regression checking — the first version's recommendation #2, done within a day.
- **The cross-call link became path-sensitive** (`refine_nonnull` on guarded calls, semantics
  rule 2e) — and notably it was the *synthesis* probe that surfaced the false positive the
  refinement fixes.
- **ugm resolved feedback #2 upstream**: rules can now genuinely Skolem-mint (`n?`). The
  `minting_comparison` probe immediately re-examined the axis-shaping constraint that fix
  removed, and concluded tool-minting remains right for synthesis — by reason now, not by force.

The revision below keeps the original's structure; each section says what still stands, what
moved, and what is new.

---

## What changed since the 2026-07-13 revision (another day, another two axes)

- **A fourth axis — diagnosis (abduction) — appeared** (`experiments/diagnosis.py` +
  `tests/test_diagnosis.py`): observe a symptom ("an `AttributeError` happened at line 5", no input
  given), abduce the value hypothesis that entails it, CHOOSE the most specific explanation (Occam),
  and verify the cause by re-running the *forward* analyzer. The loop now runs backwards over the
  **hypothesis** space as well as the code space — same firmware, exact mirror. Notably, it exists
  only as a probe docstring: nothing in `docs/` names it.
- **The conformance spike was built the same day it was designed** (see the BUILT note at the
  bottom), and its deliberately-left edge shrank within hours: `intake_growth` intakes real Python
  text with **constants and comparisons as data** and ground-evaluates by reasoning, pinned against
  Python execution itself as a differential oracle; `api_absorption` shows library knowledge
  (`dict.get returns_optional yes`) absorbing as **facts** that fire the unchanged deref rule with
  no seeded hypothesis at all.
- **The synthesis target graduated from functions to an app** (`app_synthesis`): a runnable Textual
  cash-withdrawal app synthesized across three bridged vocabularies (business, framework, UX), with
  deontic obligations firm and preferences defeasible — and, the verification crux, verified by
  **driving it** (Textual's Pilot) and reading the event trace. The winner-flip under one business
  fact (`irreversible` forces the confirm screen) is enforced by execution: the compact app really
  withdraws with no gate, and is really rejected for it.
- **A composition half was absorbed: grammapy**, now an in-repo peer package. Deviations-from-default
  compose through four combinators (Choice / Accumulate / Scope / Fold) with design-time soundness
  checks (guard coverage, footprint disjointness, effect reachability, declared lattice joins), a §12
  resolution discipline ("forced where unique, declared where preferred, surfaced where ambiguous,
  never inferred"), and AST-built emission (the string templates are gone). Step 7 closed the loop the
  right way around: **footprint honesty is checked by execution** — pystrider runs the atoms in an
  instrumented store and rejects a composition grammapy had admitted from dishonest declarations.
- **The two engines began collapsing into one.** All four combinators are Datalog-shaped; Scope and
  Accumulate now compute their verdicts as CNL rules over ugm (`grammapy/_cnl.py`), verdict-identical
  to the Python checks they replaced — unblocked by two same-day upstream fixes (distinctness
  `?a != ?b`, read-only `ask_goal(commit=False)`). Choice and Fold still await the same two
  primitives' application.
- **The performance wall was measured and turned out mostly self-inflicted** — recommendation #3
  done; details under weakness #4.

---

## Verdict up front

The engineering discipline is still unusually good and now demonstrably *repeatable*: the
probe → findings → productize → pin pipeline has run five more times since yesterday without
loosening. The headline claim has also honestly grown: this is no longer only a
**demand-driven, flow-sensitive may-dataflow analysis in Datalog with first-class provenance
and a generate-and-validate repair loop** — it is that, *plus* a template-selection synthesis
loop (CEGIS-shaped: a generator proposes, the productized analyzer disposes) running backwards
over the same firmware. The characterization from the first version stands for the analysis
half: the semantics is classic bounded abstract interpretation, not a new kind of "dynamic"
analysis. What is genuinely novel is unchanged in kind but stronger in degree: the *entire*
loop — hypothesize, derive, explain, repair, verify, choose, and now *generate* — runs on one
auditable substrate where every conclusion is a proof object, and the analyzer and the
synthesizer are literally the same rules. No system I know of closes that particular loop in
both directions on one engine. Whether it is useful still depends on building toward the place
where that property is the product.

> **Update (2026-07-14).** The verdict's shape holds and the direction count grew: the same
> substrate now also runs *diagnosis* (abduce the hypothesis from an observed symptom) and
> *conformance* (derive spec↔code divergence), and acquired a composition half (grammapy) whose
> design-time admissions are certified by execution. Two tempering notes. First, the docs are
> falling behind the artifact — the diagnosis axis exists only in a probe docstring, and the
> README's "five directions" claim has no `docs/` page behind two of them. Second, the strongest
> new verification oracle (drive the app, read the event trace) is also the least characterized:
> nothing states *which* trace properties a passing drive proves and which it silently doesn't
> check. Both are documentation debts, but they are debts against the project's own moral claim,
> which is auditability.

---

## Strengths

**1. The provenance is real, and that is still the crown jewel.** Unchanged, and now it spans
both directions: an analysis outcome carries its derivation tree, and a synthesized function
carries a spec→code rationale trace from the same RECORD journal.

**2. The probe methodology is exemplary — and it survived a 2× growth spurt.** Five new probes
in two days, each with the same shape: a sharp question, a minimal artifact, findings mapped to
evidence, an honest "still open" list, and pins. Two deserve singling out. The
`multifunction_synthesis` probe *found a precision bug in the analyzer* (the path-insensitive
cross-call link rejected a runtime-safe composition) and the fix was productized with a pin in
`tests/test_session.py` — synthesis acting as a fuzzer for analysis is the two-axes-one-firmware
bet paying off concretely. And `minting_comparison` re-opened a settled design choice the moment
its forcing constraint disappeared upstream, and re-closed it with a head-to-head experiment.
Most projects never re-examine a workaround that turned out convenient; this one did it within
hours of the upstream fix.

**3. The repair loop is architecturally right, and now stronger.** `repair_all` iterates to a
fixpoint, judging every candidate by re-running `analyze_all` (every known effect) on the edited
source: an edit must make progress *and* introduce no new outcome, or it is refused, and an
unfixable outcome yields an honest `stuck` rather than a lie. This is exactly the cross-effect
verification the first version asked for (weakness #6 there); the residual gaps are noted below.

**4. The synthesis-verification closure is the strongest architecture validation yet.** In
`controlflow_synthesis`, CHOOSE prefers the compact unguarded form and the *productized
analyzer* rejects it, forcing the guarded form; in `multifunction_synthesis` the oracle is the
productized inter-procedural `Session.analyze_across_call`. The generator proposes, the analyzer
disposes — the same trust model as repair ("clears on the actual code, not because the operator
claims it will"), now serving codegen. Both flips in the earlier probes (strictness:
`v or {}` vs. the explicit ifexp; readability: inline vs. named steps) are validated by
execution, not annotation — `coalesce_or` passing the symbolic check but failing the concrete
one is a textbook example of why.

**5. Layer discipline held under pressure.** pystrider still owns no engine code; the emit tools
are the §8 boundary run in reverse, which is the *designed* extension point, not a hack. The
"rules never mint; tools mint, demand-driven" invariant was maintained across all four synthesis
probes, and when the constraint behind it dissolved, the invariant was re-justified rather than
ritually preserved.

**6. The pre-materialized-pool insight generalized.** "The state pool is the fuel budget" now
has three instances: unroll depth (analysis), skeleton/recipe pool (synthesis), and
`max_rounds` for rule-grown chains. `minting_comparison` finding 3 — Skolem convergence bounds
re-asks, not generative depth, so fuel discipline always lives outside the rules — is a real,
articulable result about where "agent, not theorem prover" must be enforced.

---

## Weaknesses

**1. The "dynamic vs. static" framing still overreaches, and the README now leads with it
harder.** Unchanged in substance from the first version: intake pre-materializes the
`(program-point × variable)` cell lattice and the rules are pure Datalog over pre-existing
structure — flow-sensitive dataflow with magic-sets demand and bounded unrolling, not a new
species. The README's first line now says "dynamic, hypothesis-driven code analyzer, bug-fixer,
and code generator"; the middle term is UX-true, the first is semantics-false. Likewise
"symbolically *run* the code" invites a symbolic-execution comparison (path conditions,
constraint solving) the system rightly does not attempt. The distinctive, defensible pitch is
provenance + closed loop in both directions + honest boundedness.

> **ADDRESSED (2026-07-14) — the word is gone.** The README now leads with "**hypothesis-driven**
> code analyzer, bug-fixer, code generator, and policy-conformance checker" — the semantics-false
> "dynamic" was dropped, and the UX-true term promoted, which is exactly what this weakness asked
> for. "Symbolically *run* the code" survives, but it is *closer to true* than when the complaint
> was written: `intake_growth` now ground-evaluates real constants and comparisons (concrete
> interpretation of a fully ground scenario, one path taken, arithmetic in the §8 calculator),
> which is a defensible sense of "run". Residual: the README's five-direction breadth claim now
> runs ahead of the docs rather than of the semantics — a lesser sin, noted in the verdict update.

**2. The hypothesis must still be supplied — and now the spec must be too.** Analysis needs the
caller to enumerate `{"raw": "none"}`; synthesis needs a hand-built `Spec` dataclass whose
intents (`lookup_with_default`, `accrual`, …) name hand-authored recipe pools. Both halves are
checkers/selectors, not discoverers. This is survivable at the current two-value domain and
three-candidate pools, but it is the axis on which the whole system is a *verifier of proposals*
rather than a *generator of them* — which is also why the LLM-in-the-loop direction (Risks,
below) keeps getting more attractive rather than less.

> **ERODED FROM THREE SIDES (2026-07-14), not yet dissolved.** (i) The diagnosis probe *inverts*
> the axis: the hypothesis is the output — an observed symptom in, an abduced input out, verified
> by the forward analyzer. (ii) The conformance sweep enumerates hypotheses from the spec's
> declared vocabulary and boundary constants, exactly as the unification design predicted.
> (iii) `api_absorption` derives a deref bug with *no seeded hypothesis at all* — the None source
> is an absorbed library fact, not a supplied dict. Each is a probe, not the productized `analyze`
> surface, and the general answer is still the LLM generator — but "the hypothesis must be
> supplied" is no longer structurally true of the architecture, only of the current entry point.

**3. The flagship effects are the ones existing tools already solve — and "verified" means only
them.** Still two effects, both None-shaped (`attribute_error`, `returns_none`), both caught by
`pyright --strict` on annotated code. This now has a sharper second edge: the synthesis probes
report `verified True`, but the oracle is `analyze`/`analyze_all`, so *"verified" means "no
None-bug under the seeded hypothesis"* — not "correct". The probes that need more (the accrual
formula, `preserves_input`) honestly bolt on concrete execution, which is the right instinct,
but the README's "verified by re-execution" reads stronger than the effect vocabulary backing
it. Growing the effect table is now load-bearing for *both* axes.

> **PARTLY ADDRESSED (2026-07-14) — the "verified" half moved; the effect table did not.** The
> oracle family grew well past `analyze_all`: `app_synthesis` verifies by *driving* the emitted app
> (Pilot) and asserting the observed event trace (`gate_shown` before `withdrawn`);
> `footprint_honesty` certifies declared write-footprints by instrumented execution — and rejects a
> composition the design-time check had admitted; `intake_growth` pins reasoning against Python
> execution itself as a differential oracle. "Verified" increasingly means "observed under
> execution", which is what the README claimed all along. The effect table itself is still two
> None-shaped effects; `api_absorption` slice 4 (`method_not_found` from absorbed `has_method`
> facts) is the named next entry, still unbuilt — and absorption is now the cheapest way to grow
> the table, since a new effect can ride on absorbed facts rather than new semantics rules.

**4. Performance is still a wall being walked toward, and the wall got closer.** The README
example still costs ~1.4s over 74 facts (per-fact cost unchanged). The suite went from 49 tests
in ~75s to 102 tests in ~295s — 2.1× the tests at 3.9× the cost, i.e. the *average test nearly
doubled in price*, because each synthesis verification is a full re-intake + re-analysis —
`repair_all` multiplies that by candidates × fixpoint steps, and `multifunction_synthesis` by
compositions × Session builds. The first version's recommendation #3 (benchmark the Session
path before widening it) was *not* done, while the Session path acquired a new consumer
(synthesis verification). The collision course with the inter-procedural ambition is unchanged;
the traffic on it doubled and the toll went up.

> **ADDRESSED (2026-07-14) — and the wall was mostly self-inflicted.** Recommendation #3 was done
> (`experiments/session_benchmark.py`): `seed_from_focus` keeps analyze ~flat (×1.67 over a ×7.95
> graph growth) while global focus goes super-linear (×13.22) — the Session scoping is load-bearing,
> not decorative. The benchmark also exposed the real hot-path cost, which was not ugm's per-triple
> constant but `load_machine_rules` *re-validating the static bank on every detect* (~65% of every
> analyze) — now memoized: `repair_all` 8.2s → 0.21s, the suite 376s → ~24s at the then-110 tests.
> Today's 246 tests run in ~140s; the regrowth is new work (Pilot app-driving; the CNL-collapse
> checks, each heavier than the Python one-liner it replaced — fine off the hot path, watched if
> checks move onto a per-candidate drive loop), not the old constant returning. The remaining lever
> — ugm's per-triple pure-Python fold — is upstream, and has been fed back there.

**5. UNKNOWN is still not surfaced — recommendation #1, not done, and now it leaks into
"clean".** `stmt()` still returns the state unchanged for unsupported statements
(`intake.py:267`), so a skipped `x.attr = …`, tuple unpack, or augmented assign frames the
*stale* value forward — confidently wrong, not honestly absent. `unknown_expr` nodes exist
("honest UNKNOWN" in name) but no verdict ever says UNKNOWN; absence still conflates "proved
safe", "not modelled", and "fuel exhausted". This now matters more than yesterday:
`repair_all` returns `clean=True` and `controlflow_synthesis` returns `verified=True` on
exactly that silence. The system's moral claim is auditability; its most-load-bearing verdicts
("clean", "verified") are the ones inheriting the un-audited gap. Still the single most
important semantic fix.

> **ADDRESSED (2026-07-13).** Intake now emits a visible `not_modelled` marker for every statement
> kind it cannot thread (`intake.py` — the else branch that used to `return state` silently), so the
> gap is auditable instead of framed-stale-forward. `analysis.caveats(intake)` surfaces them; a new
> `Caveat` type and `RepairPlan.caveats` / `.fully_modelled` qualify the verdict — `repair_all`'s
> summary now reads *"repaired to clean (modulo N unmodelled statement(s))"* and lists each, so
> "clean" means "checked and clear" only when `fully_modelled` is True. The productized synthesis
> surface's `emit.verify_clean` returns `(outcomes, caveats)` for the same reason. Pinned in
> `tests/test_caveats.py` (8) + `tests/test_emit.py`. **Not** fixed: the framing is still *stale*
> under the marker (we surface the gap, we do not model the statement), and `unknown_expr` values are
> still only conservatively sound, not reported as UNKNOWN — but the load-bearing "clean = silence"
> conflation the weakness named is closed.

**6. Repair verification: largely fixed, with named residuals.** `repair_all` now
regression-checks across all known effects — the Slice-A-guard-introduces-Slice-C-effect hole
from the first version is closed. Residuals: (a) the single-site `choose_repair` path still
verifies one effect only; (b) verification is still under the *one* seeded hypothesis dict, not
a sweep; (c) the regression check compares outcome *labels*, so an edit that replaces one
outcome with a different-labeled outcome of the same kind at the same site passes as
"progress"; (d) the operator library still cannot express "delete the clobbering assignment" —
in the README example the winning repair still guards the deref and preserves the actual bug.
(a)–(c) are afternoons; (d) is the library-breadth problem, which is structural.

> **ADDRESSED (2026-07-14) — (a) + (c) done; (b) + (d) stand.** (a) The single-site path
> (`choose_repair`/`candidate_edits`) now verifies via `analyze_all` — EVERY effect, not just the
> target's — so a candidate `cleared`s iff its target is gone AND it introduces no new outcome of any
> effect, and each `Candidate` carries the full cross-effect `residual` (a return-None fix no longer
> hides a still-broken deref). Affordable now only because the rule-bank cache (weakness #4) removed
> the per-analyze constant. (c) Both the single-site check and `repair_all`'s regression check now
> compare a stable outcome KEY `(kind, base_var, label)` instead of the bare label — precise enough to
> separate a different-kind/different-variable problem, and stable across the re-intake that renumbers
> structural `site` ids (which is why raw site-id comparison was never an option). Pinned in
> `tests/test_repair_verification.py` (3). **Not** fixed: (b) verification is still under the one
> seeded hypothesis, not a sweep; (d) the library still cannot delete a clobbering assignment
> (structural). Residual on (c): two textually identical derefs still share a key — perfect site
> identity would need intake to emit ids stable across edits.

**7. `link_calls` is still context-insensitive, now with one earned refinement.** Two callers
of one function still merge into the callee's single entry cell — the classic imprecision, still
unregistered in the docs as such. What *did* land is path-sensitivity at the call site
(`refine_nonnull`): a call inside `if arg is not None:` no longer leaks None into the callee.
Credit where due — and note the refinement credits only a guard that directly tests the passed
argument, the narrowest possible pattern. The IFDS-style summary-edge answer to
context-sensitivity remains future work and should be named in the docs.

**8. (New) The synthesis axis is selection, not generation — and the README's "code generator"
title is ahead of the artifact.** Every probe's candidate pool is 2–4 hand-authored skeletons or
recipes; the "spec" is a dataclass with boolean flags; the refinement rules choose among
alternatives a human already wrote. That is honest and correctly scoped *in the probes' own
docs* — the findings are about the loop's shape, not its breadth — but the README's framing
("a succinct spec expanded by CNL rules into real Python") will read to an outsider as program
synthesis in the SyGuS/SKETCH sense, which this is not yet: there is no search over a grammar,
no hole-filling beyond tool-side string templates, no spec language. Related: five probes and
zero productized synthesis surface is the start of a probe pile — each experiment re-implements
its own emit/verify scaffolding, and the divergence tax will grow.

> **PARTLY ADDRESSED (2026-07-13) — the probe-pile half.** The shared selection loop is now
> productized in `pystrider/emit.py` (+ `emit.cnl`, the realization rule bank as data, the mirror of
> `operators.cnl`): `emit.select(spec, required_features, candidates)` does realize-iff-provides-all
> + CHOOSE + provenance, and `emit.verify_clean` re-intakes + analyzes emitted source (returning
> caveats too). It is authored the ugm-vision-aligned way (`load_fact_triples` interns by name, no
> hand-rolled `ids` cache). `callgraph_synthesis` was refactored onto it — its re-implemented
> `_graph`/`retrieve`/`choose`/realization-rules are gone. Pinned in `tests/test_emit.py` (8), with
> the six probes still green. The *deeper* half of the weakness stands: this is still selection over a
> hand-authored pool, not grammar search — the "code generator" framing remains ahead of the
> artifact, and `spec_synthesis`/`codegen_understand` have not yet been migrated onto `emit` (they
> can be; the surface fits their shape). Productizing an end-to-end synthesis *entry point* (spec →
> source), not just the selection core, is the remaining step.

> **FURTHER ADDRESSED (2026-07-14) — composition arrived; grammar search still absent.** The
> selection-not-generation gap was attacked from a direction this weakness did not anticipate: not a
> grammar over expressions but a **composition algebra over deviations-from-default** (grammapy,
> absorbed as an in-repo peer package). The app probe assembles a *runnable Textual app* from
> separable fragments across three bridged vocabularies; four checked combinators replace the flat
> candidate pool for the compositional part; emission is AST-built (string templates retired); and
> `assemble(spec) → DeviationSpec → synthesize` is, in probe form, the end-to-end spec→source entry
> point recommendation #4 asked for. What still stands: the atoms and fragments are hand-authored —
> the generator front-end that would draft them (grammapy Phase 5 steps 5–6, the natural LLM slot)
> is the named next build — and `spec_synthesis`/`codegen_understand` were never migrated onto
> `emit` (now partly moot: the app path retired `emit.select` in favor of the sounder Choice/§12
> resolution machinery, which suggests `emit.select` was the interim surface, not the destination).

---

## Risks

- **The heap.** Unchanged: no aliasing, no attribute store, no container model. The decision
  (model it deliberately, or permanently scope to value-flow bugs and decision-kernel functions)
  is still pending and still the framework-killer if drifted into.
- **Semantics authoring at scale.** Unchanged, slightly better: the rule bank grew (2e) without
  incident, and ugm's strict-mode fixes reduce the silent-authoring-failure class. Still no
  rule-testing harness; still the steep curve.
- **Niche squeeze — now on both axes.** Above the analysis axis sit LLMs and below it sit
  pyright/CodeQL/Infer, as before. The synthesis axis walks into an even harder squeeze: LLMs
  write real code from real specs today, with vast breadth and zero proofs. A three-template
  selector cannot compete on generation — but it does not have to. The defensible composite is
  the same on both axes: **the verifier with provenance**. The LLM proposes (hypotheses,
  operators, skeletons, recipe pools — dissolving weakness #2 and #8's breadth problem at a
  stroke); pystrider checks, grades, and returns proof objects. The synthesis probes have
  *already built the checking half of that loop* — `controlflow_synthesis`'s
  generator-proposes/analyzer-disposes is exactly the shape, with the LLM as a richer generator.
  That experiment is more reachable today than it was yesterday, and it remains the demo that
  makes the stack legible.

---

## How this compares to existing systems (updated)

### The analysis axis

- **Datalog-based program analysis** (Doop, Soufflé, CodeQL, bddbddb): still the closest kin.
  Distinguishing: demand-driven with honest fuel semantics, first-class derivation provenance,
  repair *and now synthesis* in the same substrate. Deficits: performance and language coverage
  by orders of magnitude. (Soufflé has a provenance/proof-tree mode; ugm's is more central but
  not unprecedented.)
- **Demand-driven dataflow** (Reps–Horwitz–Sagiv IFDS; Duesterwald): `suppose` + `chain_sip` is
  demand dataflow with a seeded query; IFDS summary edges remain the standard answer to
  weakness #7.
- **Bounded model checking** (CBMC): unrolling-as-fuel is BMC's move; same "honest bound, not
  fixpoint" stance.
- **Symbolic execution** (KLEE, angr): shared vocabulary only — no path conditions, no solver.
  The `refine_nonnull` / `assume_*` edge tags are a first, tiny step toward path predicates.

### The repair loop

- **Automated program repair**: `choose_repair` is template-based generate-and-validate (PAR,
  TBar lineage). `repair_all` moves it closer to the standard APR loop: iterate, validate each
  patch against the full oracle, refuse regressions — the analogue of anti-patch-overfitting
  discipline, with `analyze_all` playing the test suite. The oracle is still one hypothesis and
  two effects where APR systems have whole test suites; the *auditability* of the CHOOSE (losers
  retained, graded, explained) exceeds anything in that literature.
- **Means-ends analysis** (Newell & Simon's GPS, STRIPS): the effect-keyed operator library with
  preconditions, unchanged. `repair_all`'s fixpoint-toward-a-clean-state is means-ends toward a
  goal state in the classic sense.

### The synthesis axis (new)

- **CEGIS / SKETCH (Solar-Lezama)**: the closest shape. "CHOOSE proposes the compact candidate,
  the analyzer rejects it, fall back" is counterexample-guided inductive synthesis with the
  Datalog analyzer standing in for the SMT verifier and a hand-enumerated pool standing in for
  the sketch's hole space. The differences are honest: no constraint-driven search, no
  counterexample *generalization* (a rejection eliminates one candidate, not a family).
- **Syntax-guided synthesis (SyGuS) / FlashFill-PROSE**: the pre-minted skeleton pool is a
  degenerate grammar (depth 1, hand-written); PROSE's ranking functions are the industrial
  analogue of CHOOSE's compactness grading. The gap to a real grammar-driven search is the
  content of weakness #8.
- **Derivational synthesis (Smith's KIDS / Specware)**: the deepest ancestor in *spirit* —
  specs refined into code by rules, with the derivation retained as the artifact's
  justification. KIDS needed a human to pick each refinement; here CHOOSE picks and the analyzer
  vetoes. Nobody has run that lineage on a shared analysis/synthesis rulebase; that part is new.
- **HTN planning**: `codegen_understand`'s recipe/plan decomposition (a need is covered iff a
  recipe in the plan produces it, recursively, leaves at parameters) is hierarchical task-network
  decomposition expressed as stratified Datalog — a tidy reduction.
- **LLM codegen with verification** (test-filtered generation à la AlphaCode; self-repair
  agents): they own breadth; none returns a machine-checkable derivation of *why* the emitted
  code realizes the spec. The recognition result (`compute_accrual computes accrual`, derived,
  with an escape hatch for foreign code) is a primitive form of something none of them have:
  bidirectional spec↔code traceability on one substrate.

### The substrate

- **Truth maintenance (de Kleer's ATMS)**: unchanged — SUPPOSE scopes are assumption contexts,
  RECORD is a justification network; ugm remains an ATMS with better ergonomics.
- **OpenCog AtomSpace / SOAR / ACT-R**: unchanged — the nine-mode inventory is the tasteful
  distillation of that tradition into a small logic fragment.

The one-sentence comparison, updated: *systems exist that analyze better, repair better, and
generate far better — no system exists in which analysis, repair, and generation are the same
small rule engine running in different directions, with every step of all three carrying a
replayable proof.* That composite is still the only defensible pitch, and it got materially
stronger this week. *(2026-07-14: "different directions" now counts five — analysis, repair,
synthesis, diagnosis, conformance — and the synthesis direction gained a composition algebra
whose design-time admissions are certified by execution. The sentence's shape survives; its
scope keeps growing without yet breaking.)*

---

## On ugm itself

The first version's assessment stands with two updates, one in each direction.

**The good news is structural.** Feedback #2 (existential minting) was resolved upstream with a
principled mechanism — a Skolem *function* keyed on the firing's bindings, convergent on the
demand chain — not a hack. That retires the first version's third worry ("missing existential
heads are not a small gap; the next consumer may not be lucky"): value invention now exists,
Datalog± territory is reachable, and the state-threading workaround is a choice rather than a
scar. The two-repo feedback loop continues to work at unusual speed (issue filed with repro →
fixed upstream → downstream probe re-examining the consequences, within a day).

**The tempering news is that the fix exposed the next coupling.** `minting_comparison` shows
that rule-minted nodes are name-collided (identity is structural; every minted node is named
`n`), and the goal API is name-addressed — so minting (#2) is only as useful as addressing (#8)
is answered. This is the correct kind of finding to send upstream, and it sharpens rather than
contradicts the original worry about silent failure modes: `nodes_named("n")` being k-way
ambiguous is another quiet trap for the next consumer. The "loudly refuse, don't quietly do
less" culture shift remains the most important ugm-side ask, together with the unchanged
performance question: every triple is still 3 nodes / 2 edges folded in pure Python, and the
synthesis loops just multiplied the number of KB rebuilds per user-visible operation.

> **Update (2026-07-14).** The two-repo loop ran three more times in a single day, in both
> directions. Downstream→upstream: an init-order crash (`'State' object is not iterable` on cold
> import, never minimizable to a standalone repro) was filed and fixed same-day (#10). Upstream→
> downstream, the good case: the combinators-as-CNL collapse was *unblocked by* two requested
> primitives shipping the same day they were asked for — distinctness `?a != ?b` (#11) and
> read-only `ask_goal(commit=False)` (#12) — and grammapy now imports ugm, so the substrate gained
> its second in-repo consumer. Upstream→downstream, the tempering case: a firmware signature change
> (`rules` became keyword-only on `suppose`/`chain_sip`) broke 74 downstream tests unannounced —
> co-development speed cuts both ways, and pystrider is now effectively ugm's integration suite.
> The performance ask is sharpened, not resolved: with the rule-bank revalidation memoized
> downstream, the per-triple pure-Python fold is the only hot-path lever pystrider cannot reach.

---

## What to do next, in order (revised)

1. ~~**Surface UNKNOWN.**~~ **Done (2026-07-13).** Unmodelled statements now emit a visible
   `not_modelled` fact (intake), `caveats()` reports them, and `RepairPlan.caveats` /
   `.fully_modelled` + `emit.verify_clean` qualify the "clean"/"verified" verdicts. See the ADDRESSED
   note under weakness #5. Residual: the stale-framing under the marker and explicit UNKNOWN *values*
   (not just unmodelled *statements*) remain.
2. ~~Cross-effect repair verification~~ — **done** (`repair_all`), and the residuals **mopped up
   (2026-07-14)**: `choose_repair`/`candidate_edits` now verify via `analyze_all`, and both the
   single-site and `repair_all` regression checks compare a stable outcome key `(kind, base_var,
   label)` rather than the bare label. See the ADDRESSED note under weakness #6. Still open: (b) a
   hypothesis *sweep* (verification is under one seeded dict), and (d) an operator that deletes a
   clobbering assignment.
3. ~~**Benchmark the Session path.**~~ **Done (2026-07-14).** `experiments/session_benchmark.py`
   measured scoped vs. global focus as a Session accretes: `seed_from_focus` keeps analyze ~flat
   (×1.67 over an ×7.95 graph) while global goes super-linear (×13.22) — it is load-bearing. The
   benchmark also surfaced the real hot-path cost: `load_machine_rules` re-validating the static bank
   on every detect (~65% of each analyze), now memoized (`semantics.py`) — `repair_all` 8.2s → 0.21s,
   suite 376s → ~24s. The remaining lever is ugm's per-triple constant (§7 Rust), fed back as ugm #9.
4. **Productize one synthesis slice** instead of a sixth probe. The probes have answered the
   feasibility questions they were built for; the marginal information from another is low, and
   the shared emit/verify scaffolding they each re-implement should live in the package (an
   `emit.py` beside `intake.py` — the §8 boundary, both directions, as the design already
   frames it). — **Partly done (2026-07-13):** `pystrider/emit.py` now holds the selection loop
   (`select`/`realizing`/`choose_best`/`verify_clean`) + `emit.cnl`, and `callgraph_synthesis` uses
   it; see the PARTLY-ADDRESSED note under weakness #8. Remaining: an end-to-end spec→source *entry
   point*, and migrating the other probes onto the surface. (The sixth probe, `callgraph_synthesis`,
   was built before this note landed — and has now been refactored onto the productized surface,
   which is the mitigation the critique asks for.) — **Reshaped (2026-07-14):** the app probe +
   grammapy's `assemble(spec) → DeviationSpec → synthesize` *is* a spec→source entry point in probe
   form, and it superseded rather than extended `emit.select`. The productization question is no
   longer "add an entry point to `emit.py`" but "productize the two-half loop: reason (CNL) →
   resolve (§12) → compose (combinators) → emit (AST) → verify by driving."
5. **Prototype LLM-in-the-loop.** Carried over, upgraded from "promising" to "obvious": the
   checking half already exists (generator proposes → analyzer disposes, with proofs). Let an
   LLM be the generator — of hypotheses on the analysis side and of skeleton pools on the
   synthesis side — and the two hardest scaling problems (weaknesses #2 and #8) become the
   LLM's job, while the part LLMs cannot do (checkable justification) stays here. — **Now
   concretely named (2026-07-14):** grammapy Phase 5 steps 5–6, the external generator that drafts
   the deviation spec and fills atom-body AST holes, gated by the combinators and the execution
   oracle ("compose by pattern, skip the math" as the front-end, with the math still run behind
   it). Every prerequisite it was waiting on — AST emission, footprint honesty by execution, §12
   resolution — landed this week. Still unbuilt; still first in line.
6. **(New) Pay the documentation debt on the two newest oracles.** The diagnosis axis exists only
   as a probe docstring — nothing in `docs/` names it — and the Pilot-drive oracle has no stated
   contract (which event-trace properties a passing drive proves, and which it silently does not
   check). Both are cheap to write and both are debts against the project's own auditability claim;
   a critique that praises the probe→findings→pin pipeline has to flag the first two artifacts that
   skipped the findings step.

**Is it useful?** As a bug-finder against typed tooling: still no. As a code generator against
LLMs: no, and it should not try. As a research vehicle: earning its keep faster than before —
the state-minting finding, the minting to addressing coupling, and synthesis-as-analyzer-fuzzer
are three real results in a week. As a substrate for *auditable machine reasoning about code* —
where every conclusion, every fix, and now every generated function carries a checkable proof —
it remains the most promising small system of its kind, and the synthesis axis widened that
claim from "reads code" to "reads and writes code" without breaking it.

*Second-revision addendum (2026-07-14): the week's second half added execution-grade verification
(drive the app, instrument the writes, differential-test against Python itself), a composition
algebra with honesty checks, knowledge-as-data absorption, and a measured-then-fixed performance
story. The "research vehicle" verdict is compounding. The open question has sharpened accordingly:
not "which axis is the product" but "which composed loop is" — and the generator front-end
(item 5) is now the only missing piece of the most plausible answer.*

---

## A second domain: detecting and fixing bugs in CNL business rules

*(Written 2026-07-12 in response to: "what about using the tools to detect and fix semantics
bugs, where semantics is business rules expressed in CNL?" — retained as written; a status note
follows at the end.)*

This may be a **better-fitting domain than Python analysis** — arguably the domain the stack
was accidentally built for. The reasons are structural, not cosmetic.

### Why the fit is better

1. **The intake wall vanishes.** pystrider's hardest problems — the §8 intake tool, authoring
   an operational semantics of Python, the heap, unmodelled statements — all exist because the
   object language (Python) is foreign to the engine. A CNL rulebase is *already* ugm's native
   language: `load_rules` reifies each rule as graph structure (`<rule>` → `rl_lhs` →
   `<cond>` with `k_subj/k_pred/k_obj`), and executing the rules IS the semantics. The
   homoiconicity that pystrider never exercised becomes load-bearing: the artifact under
   analysis, the analyzer, and the repair edits are all the same material.
2. **Finite, enumerable hypothesis spaces.** Business vocabularies are typically closed
   (customer tiers, product categories, declared thresholds). The scenario space can be *swept*
   rather than guessed — coverage and gap analysis become complete rather than fuel-bounded,
   fixing pystrider's weakness #2 (hypothesis-must-be-supplied) for free.
   `vocabulary_declaration_design.md` already gives declared domains to enumerate from.
3. **Provenance is the product, not a bonus.** Regulated decisions (credit, claims,
   eligibility, pricing) legally require explanations. A `why`-trace over the rulebase is
   exactly the audit artifact compliance teams need — here the derivation tree is not a nice
   demo, it is the deliverable.
4. **No incumbent squeeze.** The classic KB-verification literature (Preece & Shinghal's
   anomaly taxonomy: redundancy, ambivalence/contradiction, circularity, deficiency) is
   1990s-era and its tooling is dead. Modern DMN validators (Camunda, Signavio) only check
   decision *tables*, not general Horn rulebases with defeasibility and priorities. SBVR is a
   standard with weak tooling. General rulebase debugging **with repair** is genuinely
   underserved — unlike Python bug-finding, where pyright and LLMs own the field.
5. **The performance ceiling stops mattering.** Rulebases are hundreds of rules, not millions
   of lines. Session scale IS the domain's scale.

### The bug classes (the analogue of pystrider's "effects")

| Effect | Detection | Oracle needed? |
|---|---|---|
| **Wrong outcome** — a scenario derives the wrong decision | SUPPOSE the scenario, compare derived vs. expected | yes (expected-outcome test cases, themselves CNL facts) |
| **Contradiction** — two rules derive incompatible conclusions on one scenario | sweep scenarios; `consistency_design.md` machinery | no |
| **Over-firing** — too-weak body (e.g. a dropped condition — literally feedback #1's bug class) | a scenario outside the intended set fires the rule | yes (or anomaly heuristics) |
| **Gap / deficiency** — no rule covers a scenario; CWA silently answers "no" where policy demands an explicit decision | sweep the declared domain, flag scenarios where nothing fires; OWA-per-predicate makes the silence visible | no |
| **Dead / shadowed rule** — body unsatisfiable, or always beaten by a higher-priority default | meta-rules over reified structure + behavioral sweep | no |
| **Redundancy / subsumption** — rule A makes rule B pointless | see the unification note below | no |

Most of pystrider's machinery transfers directly: `_detect` is already effect-generic,
`choose_repair` already takes a pluggable analyzer, and the nested-SUPPOSE shape (edit-world
containing scenario-worlds) is unchanged. What disappears is `intake.py` and `semantics.cnl` —
the two hardest files.

### Where unification actually stands (an honest note)

ugm's matching today is **one-way** unification: a rule head is unified with a bound demand
(`chain.py:_unify_head_with_demand`), and body atoms match against *ground* facts —
Datalog-style, not Prolog's full two-way unification. Two consequences:

- **Syntactic meta-reasoning works today, with no new machinery.** Because rules are reified as
  ground structure (a rule's `?c` variable is just a token node at the meta level), ordinary
  Horn meta-rules can match rule structure: "which rules conclude `?x gets_discount` whose body
  never tests `?x is_member`" is a plain query over `rl_lhs` / `k_pred` facts. Dead-rule,
  missing-condition, and contradiction-by-conclusion-pair checks are all in this class. This is
  the homoiconic payoff, and it is available now.
- **True θ-subsumption ("does body A subsume body B under a variable renaming?") is not.** That
  needs pattern-against-pattern matching with variable renaming — genuine two-way unification,
  which the firmware does not do. Two honest options: (a) a **§8 CALL tool** that computes
  subsumption over the reified bodies (it is NP-hard in general but trivial for 3–5-clause
  business rules — and "subsumption as a calculator" fits the §8 boundary exactly); or (b)
  approximate overlap **behaviorally**: sweep the finite scenario space and compare firing
  sets — two rules that fire on nested scenario sets are behaviorally subsumed, no unification
  needed. Option (b) works today and is arguably more useful (it catches *semantic* overlap
  that syntactic subsumption misses).

Anti-unification (least general generalization) is the other place the unification family
matters: synthesizing a **missing rule's body** from the set of uncovered failing scenarios is
exactly an LGG computation — a natural CALL tool for the repair side.

### Repair operators for rules

The operator library transfers in shape, with rule-edits instead of AST-rewrites:

- **strengthen** — add a body condition (fixes over-firing; the repair for the
  dropped-condition bug class);
- **weaken** — remove or relax a condition (fixes under-firing);
- **add exception** — a defeasible override with priority, which ugm supports *natively* —
  arguably the most idiomatic business-rule repair there is;
- **add missing rule** — for an uncovered scenario region (body via anti-unification / LGG);
- **reorder priorities** — resolve a shadowing or contradiction.

Mechanism note: because rules are graph structure, speculative rule edits do not even need a
text transformer. **INTERPOSE/RESTORE** — ugm's reversible edge-hiding primitive — can hide a
condition edge (weaken) or a whole `rl_lhs` link inside a SUPPOSE scope, giving trial rule
edits that are natively droppable. `transform.py`'s equivalent becomes engine-native.

Verification is *stronger* here than in pystrider by construction: the oracle is the whole
scenario suite, so every candidate edit is automatically checked against all effects and all
passing cases. CHOOSE then picks the minimal edit that clears the failures without breaking any
passing scenario — with the losers retained and the whole selection auditable, which in a
compliance setting is itself a feature.

### The product story

With an LLM translating policy prose into CNL (the Attempto stance ugm already takes: "CNL as
surface, not engine input"), the pipeline is: *policy document → CNL rulebase → swept,
anomaly-checked, contradiction-free, gap-free, with a proof-carrying explanation for every
decision and a verified minimal repair for every defect*. That is a coherent product with a
real buyer (anyone running regulated decision logic), no dominant incumbent, finite domains
that flatter the engine's strengths, and none of the walls (heap, semantics authoring,
performance at repo scale) that bound the Python domain.

### Suggested spike ("rulestrider")

Mirror the pystrider spike, smaller: (1) a ~15-rule CNL discount/eligibility policy with a
planted dropped-condition bug; (2) a scenario suite with expected outcomes, in CNL; (3) detect:
the failing scenario + its `why`-trace; (4) two oracle-free anomaly meta-rules (contradiction
pair, dead rule) over the reified structure; (5) two repair operators (strengthen-body,
add-exception) retrieved by effect key, verified against the full suite, CHOSEN minimal. No
intake tool, no semantics bank — the estimate is *smaller* than the pystrider spike, and it
exercises the two ugm features pystrider never touched: homoiconicity and defeasibility.

> **Status note (2026-07-13).** Untouched as a spike, but the week's work moved its
> prerequisites: `repair_all` is the fixpoint-repair shape the rule-repair loop needs, and
> `codegen_understand` demonstrated business-term ↔ code bridging (a spec named `accrual`
> expanded to code and recognized back). The estimate stands.

---

## The unification play: spec and implementation on one substrate

*(The intended question, clarified: not "analyze rulebases instead of Python" but "put the CNL
business rules AND the Python code's semantics in the same graph and reason across them." The
rulebase-debugging section above is a component of this; what follows is the composed system.
Retained as written 2026-07-12; a status note follows at the end.)*

This is, in my assessment, **the strongest version of the whole project** — the first workload
where ugm's one-substrate identity pays for itself instead of merely costing performance.

### The shape

One graph holds three co-resident rule systems plus a thin binding layer:

1. **The spec** — business rules as native CNL (`a customer gets_discount when tier is gold and
   total is over 50`). Executable directly; ugm's valued attributes with comparators
   (`age ≤ 40`) already carry the numeric side.
2. **The implementation** — a Python function intaken by pystrider, its behavior derived by the
   operational-semantics bank, exactly as today.
3. **The binding** — a small set of declarative mapping facts, themselves CNL-authorable:
   `discount implements discount_policy`, `param tier means customer_tier`,
   `return_value means gets_discount`. The bridge between the two vocabularies is *data in the
   same graph*, not glue code.
4. **The judge** — divergence is itself one Horn rule, e.g.
   `?s diverges when ?s spec_outcome ?x and ?s code_outcome ?y and not ?x same_as ?y`.

Then the loop is pystrider's loop, run against a spec instead of a hand-picked hypothesis:
**sweep** scenarios enumerated from the spec's declared vocabulary and boundary constants →
for each, derive the *intended* outcome (business rules fire) and the *actual* outcome
(operational semantics fire) → any `diverges` fact is a **semantics bug**: the code does not
implement the policy.

### Why the shared substrate is load-bearing (not a packaging choice)

- **The comparison is a join, not glue.** In any two-tool architecture (rules engine + pytest,
  DMN validator + code) the spec-vs-code comparison lives in brittle imperative glue with no
  provenance. Here `diverges` is a derived fact like any other — queryable, focus-boundable,
  and explainable.
- **One trace spans both worlds.** The `why`-trace of a divergence interleaves business-rule
  firings and operational-semantics firings: *"the policy grants the discount because tier is
  gold and total is over 50; the code denies it because line 7 tests `total > 100`."* No
  existing tool produces that artifact, and it is precisely what a developer, an auditor, and
  an LLM agent each need.
- **Repair becomes spec-directed instead of template-guessed.** Because the violated business
  rule is reified structure, a repair operator can *bind its conditions as data* and
  materialize the corresponding code edit — e.g. read the spec's comparison constant (50) and
  align the code's threshold (100) to it. This answers weakness #6 at the root: the repair
  target is no longer "make this one outcome disappear" but "make the code's derived outcomes
  equal the spec's on every swept scenario" — semantics preservation is the verification
  condition by construction.
- **Scenario generation comes from the spec.** The declared finite vocabulary plus the spec's
  own constants (boundary values: 49/50/51) enumerate the sweep. This dissolves weakness #2:
  the spec is the hypothesis generator.
- **Impact analysis falls out.** Edit a policy rule, re-sweep: every code site that now
  diverges is flagged with a trace. "Which code must change when this policy changes" — the
  question every enterprise rules team asks — becomes a derivation.

### Bug classes unlocked

- **Divergence, both directions**: code denies what the spec grants; code grants what the spec
  denies.
- **Boundary errors** specifically (spec `> 50`, code `>= 50` or `> 100`) — the sweep over
  spec-derived boundary values finds exactly these, the most common real-world policy-code bug.
- **Coverage asymmetries**: code handles a case no rule covers (missing spec rule — surface it,
  don't guess), or a rule no code path implements (dead policy).
- **Drift**: the divergence set over time is a conformance regression suite that maintains
  itself from the spec.

### What it costs (the honest part)

- **The code-side value domain must grow** — constants, `==`/`>`/`<` comparisons, booleans,
  strings — beyond today's `{none, object}`. Crucially, though, the conformance use case only
  needs **concrete** evaluation: each swept scenario is fully ground, so the "symbolic run" is
  a deterministic interpretation — branch conditions evaluate to true/false and one path is
  taken. That is far easier than general symbolic execution: no path explosion, no constraint
  solving, arithmetic delegated to the §8 CALL tool exactly as the design already plans. The
  existing abstract/None machinery stays for the open-input analyses; the conformance sweep
  runs the same rules over ground cells.
- **The checkable code subset must be scoped deliberately**: decision-kernel functions over
  scalars/enums — which is what well-factored business logic looks like anyway. Like
  design-by-contract before it, the tool can *define* the discipline ("strider-checkable
  functions") rather than chase arbitrary Python. The heap wall is thereby avoided on purpose,
  not hit.
- **Two rule banks in one graph** need predicate namespacing / focus scoping so the
  operational-semantics rules never fire on business facts and vice versa — the Session
  machinery already does the per-function version of this.
- **Completeness caveat**: sweeping is exhaustive over finite declared domains and
  boundary-selected over continuous ones — exhaustive testing of the abstraction, not
  verification. Honest, and honestly stated by the fuel/UNKNOWN stance the system already has.

### Literature positioning

Closest kin: **contract-based repair** (AutoFix over Eiffel contracts) and **model-based
testing** (spec-derived test generation, Spec Explorer lineage); more distantly, business-
process conformance checking (van der Aalst — but that checks event logs against process
models, not code against decision rules). The specific combination — declarative spec and
operational code semantics as *co-resident rule systems joined by a derivable divergence
relation, with one provenance journal spanning both and spec-directed repair* — does not, to my
knowledge, exist. Unlike the standalone Python-analysis positioning (squeezed by pyright and
LLMs) or the standalone rulebase positioning (a revival of 90s KB verification), this composed
system has no incumbent shape at all, because every competitor has a wall (parse → IR → engine
→ report) exactly where ugm has none.

### Suggested spike ("conformance strider")

One function, one policy, one planted boundary bug:

- Spec (CNL): `a customer gets_discount when tier is gold and total is over 50`.
- Code: `def discount(tier, total): if tier == "gold" and total > 100: return True; return
  False` — threshold bug.
- Binding facts: `discount implements discount_policy`, param/outcome mappings.
- Intake additions: constants, one comparison form, ground evaluation via the arithmetic CALL.
- Sweep: tiers × boundary totals {49, 50, 51, 100, 101} → `diverges` derived for
  (gold, 51–100), with the two-world trace.
- Repair: one spec-directed operator (`align_threshold` — bind the spec constant, rewrite the
  code constant), verified by re-sweep, CHOSEN.

That spike would demonstrate the one thing neither pyright, nor CodeQL, nor a DMN validator,
nor an LLM can produce: *a machine-checkable proof that a piece of code implements a piece of
policy — and a verified minimal edit when it doesn't.*

> **Status note (2026-07-13).** The synthesis axis quietly built most of one half of this
> bridge: `codegen_understand` goes business-term → code (generation) and code → business-term
> (recognition), and `spec_synthesis` already verifies emitted code against spec features with
> the productized analyzer. What conformance-strider adds over what now exists is the *other
> direction on foreign code*: checking code the system did **not** generate against a spec,
> which needs the ground-evaluation intake growth (constants, comparisons) listed above. The
> synthesis probes make the composed system more credible, not less necessary — and the
> recognition escape hatch ("supply the fact in CNL when there is no fingerprint") is exactly
> the binding layer this design describes.

> **BUILT (2026-07-14).** The spike above is built: `experiments/conformance_strider.py`
> (`tests/test_conformance_strider.py`, 6). A CNL policy + reified decision code co-resident in one
> graph; `diverges` derived as a fact spanning both worlds; the planted `total > 100` vs. `over 50`
> bug found on exactly the gold (50, 100] band (differential-tested against a plain-Python oracle);
> a two-world `why`-trace; `align_threshold` repair (spec constant → code constant) verified by
> RE-SWEEP to zero divergence and CHOSEN over a decoy that fails verification. Faithful to the
> design's "what it costs": arithmetic stays in a Python calculator (ugm's §8 comparison boundary;
> each swept scenario is fully ground), logic stays in rules, and the sweep is the hypothesis
> generator. **Deliberate edge, as predicted:** the code is REIFIED directly, not intaken from
> Python text — the threshold is DATA (so repair genuinely edits + re-derives), but growing
> `intake.py` with constants/comparisons to check *arbitrary foreign Python* remains the separate,
> named cost. See `docs/spike_findings.md` ("conformance strider").

> **Edge shrunk (2026-07-14, later the same day).** `experiments/intake_growth.py` built exactly
> the named cost: a real Python decision function intaken *from source text* with constants and
> comparisons as data, ground-evaluated by reasoning, and differential-tested against Python
> execution over the whole boundary sweep. Beside it, `experiments/api_absorption.py`
> (+ `docs/api_absorption_design.md`) showed the same mechanism one level up: library knowledge
> (`dict.get returns_optional yes`) absorbed as facts that make the *unchanged* deref rule fire on
> `x = d.get(k); x.attr` — conservatively (unknown receiver ⇒ no false positive) and with no
> seeded hypothesis. The remaining wiring is slice 1b — pointing the `diverges` judge at code
> intaken from text rather than hand-reified — documented, not built.
