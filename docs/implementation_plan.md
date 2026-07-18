# pystrider — implementation plan (continuation)

A cold-start guide for the next session. Read this, then `docs/spike_findings.md` (what's proven)
and `docs/code_reasoning_design.md` (the design + open questions). Everything below the spike is
built and green; this plan is what's next. The *strategic* layer — which product this becomes and
in what phase order — is `docs/roadmap.md` (2026-07-14); this file stays tactical.

---

## Current state — START HERE (2026-07-17)

The durable record is the **memory files** (`footprint-synthesis`, `pattern-writer`, `docs-site`) and the
current docs: **[`the_case.md`](the_case.md)** (the whole argument), **[`understanding_findings.md`](understanding_findings.md)**
(the findings), **[`deep_dive.md`](deep_dive.md)** (the tour), **[`roadmap.md`](roadmap.md)** (strategy).
Everything below the next heading is the *historical* grammapy-convergence line, superseded.

**The thesis is made, demonstrated, documented, and shipped.** "Trustworthy code from a symbolic core +
execution, with a language model nowhere in the trust path" — for the orchestration-and-decision class of
software. Backed by four adversarial limit-tests (soundness, economic, composability, membrane-vagueness) and
two scale legs (feature-interaction, re-targeted families), each pinned to a runnable probe. The strong claim
is on the README front door and in `the_case.md`.

**Repo is the current generation only.** The previous template/skeleton-selection codegen was deleted
(`emit.py` + the `*_synthesis` probes + `app_synthesis` + the phase-3 UX/frontend). What remains: the
analysis/repair core; the humble writer (`pattern_compose`, `footprint_*`, `compose_recover`); understanding
(`understand_*`, `base_tier`); the playground; the scale demos; the limit-tests; and `grammapy` as the
optional checker.

**Docs site + live playgrounds (MkDocs → GitHub Pages).** `mkdocs.yml` + `.github/workflows/docs.yml` build
the ugm + pystrider wheels and publish; two in-browser Pyodide playgrounds — **Generate** (CNL → emitted
Textual code) and **Understand** (code → recognized aspects). To go live: enable *Settings → Pages → Source:
GitHub Actions*.

**Footprint synthesis — abstention productized + coverage measured & grown + inter-procedural following.**
`pystrider.footprint`: `footprint_of` carries an `unknown` flag from `modelable` (the honest-unknown
membrane); the compose check refuses on unknown. Real-corpus coverage (`experiments/footprint_corpus.py`)
over the stdlib: **31% of container-accumulators modelable, 69% honest-abstain, zero silent-unsound** —
after modeling subscripts + known container methods (`append`/`add`/`update`/`setdefault`/…).

**Inter-procedural following DONE (2026-07-17).** A store passed to a LOCAL helper (a callee whose `def`
is in view — `h(out)` with `def h(o): …` in the same source, or a module sibling via the new `helpers=`
arg) is no longer an escape: it is FOLLOWED into the callee EXACTLY — mapped onto the callee's parameter,
recursively, cycle-guarded, renamed back at each hop (`o.total`→`out.total`) — the write-side analog of
`session.link_calls`. Static following is branch-complete (it sees a helper called on an UNTAKEN branch a
run never would); `dynamic_writes` switched to a single exec namespace (so a callee resolves free vars +
sibling names) and degrades to a partial observation instead of crashing. This turned the `helper_untaken`
/ `helper_mutate` cases from UNSOUND-SILENT / abstained into EXACT / SOUND (scalability + red-team pins
updated). HONEST REACH: on the stdlib it recovers only ~5 accumulators — the passed-slice (49%) is
dominated by calls to METHODS (`self.m(acc)`, needs receiver-type resolution) and IMPORTS (cross-module),
genuinely out of view and honestly abstained. The exact local-sibling slice it *can* prove, it now does.

**Wildcard-conflict DONE (2026-07-18) — plan item #3, the stated soundness follow-on.** Two holes, both
verified real first: (a) `grammapy.disjoint_writes` matched channels by string equality, so `out.<items>`
(from `out.update(d)`) did not match `out.total` and a composition that CLOBBERS at runtime was certified
disjoint — both fragments honest, both `modelable`, nothing abstaining; the unsoundness was purely in the
READING. Fixed by a second CNL clause in `_DISJOINT_WRITES_RULE`: a wildcard channel conflicts with any
same-store write by a distinct item (over-approximating, store-confined). (b) `CodeFootprint.writes`
DROPPED the `<computed>` placeholder once the dynamic run named a key — the one under-approximating step
in the derivation (one input's key licenses nothing about another's). The union is now taken whole, and
precision is recovered by PROOF instead: a subscript key bound to a literal is resolved statically
(`_const_bindings`, every constant a name can hold, poisoned by any non-constant binding), so it never
becomes a placeholder. Pins: `test_disjointness.py::WildcardChannels` (7), `test_footprint.py`
(const-key resolution + the surviving wildcard), `test_footprint_synthesis.py` (the end-to-end clobber).
**CAVEAT — `_const_bindings` is a Python algorithm** (a small constant-propagation pass), which is the
anti-pattern flagged below; it wants re-authoring as CNL rules over intake facts.

**Suite: 310 green** (`python -m pytest -q`). Playground: `python demos/playground/playground.py`. Site:
`python -m mkdocs build`.

---

## COURSE CORRECTION (2026-07-18, user) — READ BEFORE PICKING THE NEXT SLICE

Two standing constraints that override the candidate list below:

1. **This is not a theorem prover.** The "soundness" trail is a rabbit hole. The humble goal is to leverage
   ugm to **read and write code the way humans do** — symbolic execution, actually RUNNING it and looking
   at the output, and a *learned library of patterns and composition rules*, with patterns and rules
   expressed AS RULES so the same library serves both writing and understanding. Rules go down to the
   **AST**; an external tool handles only the last mile AST⇄Python text.
2. **Leverage ugm — no algorithms in Python.** Reasoning belongs in the ugm engine (ISA, firmware, CNL).
   Python is mechanism only (the §8 tool boundary: `ast` intake, orchestration, emission). If a reasoning
   step cannot be expressed today, the move is to **write custom firmware, or ask the ugm team for new CNL
   forms** — not to write the algorithm in Python. Audit existing code against this; `_const_bindings`
   (above) is a fresh violation, and the symbolic-execution work is the main thing to resurrect.

**SLICE 1 DONE (2026-07-18) — the AST-representation probe.** De-risked the representation before
building any pipeline: `experiments/ast_representation.py` + `tests/test_ast_representation.py` (7 pins)
+ **[`docs/ast_representation_findings.md`](ast_representation_findings.md)** (findings + a ugm ask-list).
Headline: rules CAN build ordered, nested, revisable AST — the mint wall that forced the previous
generation into template selection has fallen. Design rules that came out: mint on invariants + attach
with the parent LHS-bound (a mint head anchored on a per-element endpoint splits the parent per element);
address minted nodes by ID, never by name (they are name-degenerate — this silently collapsed three
statements into one during the probe); order/scope are derived relations, emission only walks them;
revision = mint v2 + move a `current` pointer. **ugm ask-list #1 is the significant one:** minted nodes
are unaddressable in prose CNL, so `why`-traces over generated code cannot be rendered. **Biggest open
risk: the shared-vocabulary bet** — intake emits CFG/analysis-shaped facts, not the `ast_call`/`body_has`
vocabulary the lowering rules invent; reconciling them is unstarted.

**SLICE 2 DONE (2026-07-18) — vocabulary reconciliation by BRIDGES, not convergence.**
`experiments/vocabulary_bridge.py` + `tests/test_vocabulary_bridge.py` (7) +
**[`docs/vocabulary_bridge.md`](vocabulary_bridge.md)**. The "shared-vocabulary bet" named in slice 1 was
the WRONG FRAME (user: multiple authors in multiple domains will never converge on one vocabulary — and
bridges are the move we already used for business/UX/Textual in `app_synthesis`). Each author keeps their
own vocabulary and writes ONE bridge to a neutral *question* vocabulary; patterns are authored once
against that. **O(N) bridges, not O(N²) translations.** Proven by round trip: spec →(lowering rules)→
minted structure (`emit_bind`/`callee`) →`ast.unparse`→ real Python →`intake`→ facts
(`call`/`calls_func`), with ONE pattern text answering identically over both ends and the two
vocabularies pinned DISJOINT. **The finding: bridges reconcile NAMING, not COVERAGE** — intake
deliberately does not model a bare expression statement (audited `not_modelled`), and no bridge can
invent a node that was never created; the two gap kinds look identical from outside (a question returns
nothing) and have completely different fixes. Coverage gaps are a separate backlog and `not_modelled` is
its worklist.

**ugm feedback FILED** in `../ugm/docs/feedback_from_pystrider.md` as items **#15** (the question surface
is name-addressed but minted nodes are nameless-by-design — ask for definite-description addressing),
**#16** (independent NACs, a heads-up not a request), **#17** (`run_to_fixpoint` vs `run_bank` naming).
NOTE the correction: an earlier draft of #15 asked for fabricated per-node skolem names (`c_s1`, `c_s2`)
— **wrong**, it contradicts the nameless-substrate law ugm's own `_find_skolem_witness` states ("a minted
node is identified by how it relates to the LHS match, not by a raw id or a fabricated name"). The ask is
now structural/definite-description addressing in the QUERY layer. **The substrate is nameless; names are
a human surface label, never identity — do not design against this.**

**SLICE 3 DONE (2026-07-18) — the BUILD PROCEDURE spine.** `experiments/build_procedure.py` +
`tests/test_build_procedure.py` (8). `to build : expand then lower then emit then check` authored as KB
text and driven by ugm's REAL planner (`procedure.cnl` + `planning*.cnl`), the `procedure_assembly`
harness. Each step is a §8 tool; every decision inside is a rule bank or the observed world. The full
navigate loop runs: naive lowering emits `print(name)` → **check RUNS it** and observes `['bob']` vs the
spec's declared `['hello_bob']` → the effect `output_ok` is never observed → the planner's own
discrepancy/replan rules select `repair` (no Python `if`) → a RECOVERY RULE mints a nested `ast_call`
(`greet(name)`) as a new version → re-emit → re-run → `['hello_bob']`, verified by execution. Also
exercises the case slice 1 left open: **minting anchored on a minted node** (nesting a call inside an
existing statement).

**THE MONOTONE LESSON (cost a real bug, now pinned):** a "current version" pointer **cannot be
materialized** — the graph is monotone, so an earlier `current arg_v1` survives forever and the node ends
up with two currents (the first run emitted the UNREPAIRED code while claiming success). `current` must
be **ASKED, never stored**: a projection rule (`?pr current ?v when ?pr version ?v and not ?pr version ?w
and not ?w supersedes ?v`) derived read-only on a `g.copy()` scratch. Supersession must be scoped
per-node by the conjunctive NAC, or repairing one statement strips every unrepaired sibling of its
current version (pinned). This is `versioned_recovery.py`'s "append-only + `current` projection" idiom,
re-derived the hard way — treat it as standing guidance for all revision work.

**ugm #15 LANDED and is load-bearing here** (they fixed it same-day, plus #17; #16 in progress). `ByDesc`
definite-description addressing + `who` enumerating per WITNESS node + **provenance backfill onto
forward-built structure** (the `(given)` symptom turned out to be a third, separate bug: a firing's
support was never recorded, so anything built by `run_bank` was permanently unexplainable). Result:
*"why is this line here?"* now answers over GENERATED code — and the trace cites `report unmet yes`, i.e.
**the failed execution is recorded as the cause of the code change.**

**SLICE 4 DONE (2026-07-18) — the HONEST BOUNDARY: refusal as a first-class build outcome.** Extends
`build_procedure` (12 pins). Navigating a large space with few rules is only honest if the loop SAYS SO
when it cannot get there. Two distinct failures, deliberately kept apart because they have different
fixes: **`uncovered`** (MISSING knowledge — no expansion rule reaches the intent; names the intent and
tells you what to author) and **`unverified`** (INSUFFICIENT knowledge — rules built a program, execution
disagreed, the available recovery rule did not close the gap). `Build.shipped` returns the source **only
when verified**; a refused build ships `None`. The `unverified` case is the interesting one: it genuinely
tries — repair fires, improves `print(name)` → `print(greet(name))`, gets from `['bob']` to
`['hello_bob']` — and still refuses because the spec wanted `['HELLO_BOB']`. Getting closer is not
getting there, and the verdict is execution's, not the generator's.

**ugm #16 FIXED — and our premise was INVERTED, which mattered.** We filed "only one conjunctive NAC is
expressible" as a limitation. In fact independent NACs always worked on the FORWARD engine
(`lowering._nac_groups` partitions by shared NAC-local free vars), the `cnl_reference.md` line was wrong,
and the *conjunctive* form — the one we said worked and built on — was **silently broken on the DEMAND
engine**, which decided each NAC atom separately. So our `body_first` rule derived correctly under
`run_bank` and returned nothing when ASKED; the same hazard applied to the `CURRENT` projection. They
fixed the demand chain (`chain._nac_atom_groups`, joined witnesses) and gated it differentially: 1792
(rule, world) pairs, 0 divergences (560 against the pre-fix decision). **Pinned on our side**
(`test_the_current_projection_agrees_across_the_forward_and_demand_engines`) — a forward pass and a
question must not disagree. LESSON: exercising a rule only forward can hide a demand-path bug; check
both when a rule carries negation.

**SLICE 5 DONE (2026-07-18) — REPAIRS COMPOSE (a second recovery rule).** `build_procedure`, 15 pins.
Two recovery rules (`greet`, `shout`), neither aware of the other, staged as two alternative producers of
`output_ok`. A spec expecting `HELLO_BOB` is unreachable by either alone — the LOOP composes them:
`print(name)`→`['bob']` MISMATCH → greet →`print(greet(name))`→`['hello_bob']` STILL WRONG → shout wraps
that repair →`print(shout(greet(name)))`→`['HELLO_BOB']` OK. Each hop checked by execution; three
versions held (`arg_v1/v2/v3`), current = v3. **This is the exact spec slice 4 REFUSED as `unverified`** —
the refusal named what was missing, and one small rule closed it. That is the argument for the whole
framing: a small rule set reaches a large space by navigating, not by any rule being complete.

Two mechanisms this forced, both worth keeping:
- **Progress is a declared effect.** `_perform` returns a SET of effects that hold, not a bool, so a
  repair can establish `payload_greeted` (the program changed) while `output_ok` stays unobserved.
  `repair_shout` then declares `payload_greeted` as a PRECONDITION — it wraps the greeted payload, so it
  cannot run first. The ordering between repairs is authored knowledge, not staging luck.
- **An actuator guard: an op does not act when everything it would establish already holds.**
  Content-blind (it never inspects WHICH op), same category as the existing "an op acts once". Without
  it, `repair_shout` fired after `repair_greet` had already satisfied the spec and turned a PASSING build
  into a failing one (`hello_bob`→`HELLO_BOB`) — caught by running the happy path, not by a test.

**SLICE 6 DONE (2026-07-18) — MULTI-STATEMENT + the judgement moved INTO THE SUBSTRATE.** Prompted by the
user re-stating the constraint ("leverage the substrate, not logic in Python — the substrate is what makes
everything composable"). Audit found the judgements were the Python holdouts: `check` compared
`stdout == expected()` and `Build.refusal` picked its kind with an `if`. Both are now rules.
`check` MINTS one `observation` per output line and forms NO opinion; `VERDICT` derives `unmet_at` and
`satisfied`; `REFUSAL` derives `uncovered_intent` / `refused_uncovered` / `refused_unverified`; Python
only reads which flag holds. **ATTRIBUTION** is the multi-statement payload: the default spec now has TWO
lines, the second ALREADY CORRECT, and a recovery rule fires only on the statement whose own INDEX is
unmet — so repairing line 1 provably does not rewrite line 2 (pinned structurally: only the unmet
statement gains `arg_v2`). The UNMET condition is authored ONCE and reused by text composition in both
recovery rules and the verdict, so there is one definition of "unmet" in the system.

**TWO REAL BUGS FOUND, both now pinned:**
- **`run_bank` does not stratify** (ugm feedback **#18**). A rule whose `not` ranges over a predicate the
  SAME bank derives can be decided before that rule fires — and on a monotone graph the wrong answer is
  PERMANENT. `satisfied` (negation over derived `unmet_at`) fired in the same pass and reported a
  demonstrably wrong program as **OK**. Cure is `h.stratify` (exists, documented, just not automatic);
  all our banks now run through `run_stratified`. **Standing rule: any bank with negation over a derived
  fact must be stratified.** `experiments/ast_representation.py` had the same latent exposure
  (`body_first` negates over derived `stmt_before`) and was fixed too.
- **Provenance must be captured FORWARD for self-extinguishing rules** (ugm **#19**, a note not a bug). A
  repair rule fires *because* a line is unmet and its own effect makes it met, so the demand chain can
  never re-derive it and `why` collapses to `(given)`. `run_bank(..., provenance=True)` at firing time
  gives a complete trace back to the original spec fact — with the conjunctive NAC rendered jointly
  (`assumed not: … (together)`, the #16 explanation fix). **Any rule whose effect can falsify its own
  body needs forward provenance.**

Also corrected a stale comment in `ast_representation.py` that repeated the wrong "single-NAC limit"
claim (#16 established NAC atoms partition into independent groups by shared NAC-local free vars).

**SLICE 7 DONE (2026-07-18) — TWO ORACLES: the read half wired into the write half.** `build_procedure`
18 pins, suite 342. The loop now also READS the code it wrote. `INSPECTION` = the BRIDGE
(`?c invokes ?f when ?c is_a call and ?c calls_func ?f`) + a requirement rule
(`?p structural_unmet ?f when ?p requires_call ?f and not ?c invokes ?f`); `SATISFIED` ANDs the two
oracles **as a rule**, not a Python `and`. **The demonstration:** a program that prints the literal
`'hello_bob'` satisfies the black-box output oracle (`prints_ok: True`) and is caught by the structural
one (`structure_ok: False`) — right output, wrong reason. `pystrider.intake` parses the GENERATED source
in its own vocabulary and the bridge lifts it into the neutral one the requirement is written against, so
the two halves meet on one graph with **no shared predicate name** (pinned).

**INTAKE COVERAGE GROWN — `expr_stmt`.** Wiring this exposed the concrete form of the integration risk:
our generated programs are built out of BARE CALLS (`print(greet(name))`), which intake did not model —
2 `not_modelled`, **0 call nodes**, so the structural oracle was blind. Per `vocabulary_bridge.md`'s own
conclusion (a COVERAGE gap is the vocabulary author's job; no bridge can close it), `intake.stmt` now
models `ast.Expr`: the expression is visited (its calls/attributes/reads become ordinary nodes) and the
program point does not advance, since it binds nothing. This is the bridge doc's prediction being paid
off in the direction it predicted. Pins re-pointed at gaps that are still real (aug-assign, for-loop);
`test_a_bridge_cannot_close_a_COVERAGE_gap` now uses an aug-assign and additionally asserts the bare
call IS visible.

**ugm #18 FIXED — and it uncovered the opposite bug in `stratify` itself.** `run_bank` now stratifies by
default (our ask). Getting there broke CNL recognition first, because `stratify` ranked rules by NEGATED
dependencies ONLY — a positive PRODUCER could be scheduled after its positive CONSUMER. So the two
forward entry points were unsound in opposite directions. `stratify` now builds the full dependency graph
(+0 positive edges, +1 negated), with a deliberate fallback to the historical NAC-only ordering for banks
containing a cycle through a negated edge (real ugm banks have them; newly rejecting them would be a
regression dressed as rigour). Our `run_stratified` is now a thin wrapper; the hazard pin was re-pointed
at `run_bank(..., stratified=False)`, which still shows the old behaviour and so proves the scheduling
is what buys correctness.

**Framing (user, 2026-07-18):** humans make mistakes and apply recovery rules. Aiming for PERFECT rules
that generate any program is infeasible; a limited set of rules that can **navigate** — do something,
check it, recover / course-correct — reaches a far larger share of the solution space. Build for the
loop, not for first-shot correctness. (F8 in the findings shows the representation supports it.)

**Resurrection target:** the prior-generation work deleted in the `cleanup` commit
`2fb01215f04d19a704394fa1c393fa2244f7a5b8` (2026-07-17) is worth PORTING FORWARD to the current
generation rather than rebuilding — the user named the symbolic-execution line specifically. Candidates in
that diff, by likely relevance: `experiments/controlflow_synthesis.py`, `codegen_understand.py`,
`spec_synthesis.py`, `multifunction_synthesis.py`, `callgraph_synthesis.py`, `combinators_as_cnl.py`,
`minting_comparison.py`, `rederivation.py`, `refusal.py`, `app_synthesis.py`, `generator_frontend.py`,
plus `pystrider/emit.py`+`emit.cnl` (all recoverable via `git show 2fb0121^:<path>`). CONFIRM WITH THE
USER which of these is the intended target before porting — the list is inferred, not stated.

**Next steps (candidates from the pre-correction plan — re-read them through the two constraints above):**

1. **Inter-procedural footprint — LOCAL-helper leg DONE (2026-07-17).** Following the store into a
   local/sibling callee is built; the remaining reach of the 49% "passed" slice is METHODS (`self.m(acc)`
   — needs receiver-type resolution, the `absorb`/`method_not_found` territory) and IMPORTS (cross-module
   analysis). Those are the next coverage levers on this axis, each still an exact model.
2. **A bigger scale demo / real app family** — the economic case pays at scale (§8); more interacting
   features, or a re-targeted family beyond the CLI.
3. **The `<items>`/`<computed>` wildcard-conflict** in a consuming disjointness check — the stated soundness
   follow-on for a store mixed between keyed and whole-container writes.
4. **A real LLM at the input surface** (free-NL → CNL), gated — the last optional, non-load-bearing seam to
   show end-to-end.

---

## Historical — the grammapy convergence line (2026-07-14, superseded)

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

**§12 `resolve` COLLAPSED TO CNL (2026-07-14)** — prompted by a "are we using CNL, not hardcoding
Python?" audit. The four grammapy combinators were already CNL (`grammapy/_cnl.py`); §12 constraint
resolution was the one reasoning-shaped Python holdout (`survivors = [p for p in productions if req <=
p.provides]`). Now `grammapy/resolution.py` derives survivorship via `_RESOLVE_RULES` (a production is
`unmet_req` if a required capability is absent from its `provides`, stratified negation over the join;
`survives` iff not unmet), run read-only through `_cnl.derive`; `resolve` only DISPOSES the CNL-derived
survivor set into Forced/Defaulted/Surfaced/Rejected (the same Python reconstruction the other
combinators do). Public API + messages preserved; all resolution/app_synthesis/rederivation tests green.
The "types are facts, compatibility a rule" half of the bridges-vs-channels collapse, finished. Also
fixed **rulestrider's oracle** (`experiments/rulestrider.py::_intended`) — was Python boolean policy
logic, now `derive(attrs, FIXED_POLICY)` (CNL-to-CNL differential, no policy logic in Python).

**REFUSAL UX DONE** — `experiments/refusal.py` (+ `tests/test_refusal.py`, 6). An uncovered spec region
becomes a NAMED `Gap`, not a crash or a guess (held line #3): grammapy's `Rejected`/`Surfaced` (now
CNL-derived) become an `unprovided` gap ("decision point P requires X, no production provides it — to
fill, add `Production(provides={X})`", the authoring on-ramp) or an `ambiguous` gap ("declare a
preference"). `synthesize_or_refuse(spec, requires)` returns a verified `Synthesis` OR a `Refusal` value
— refusal as a first-class OUTCOME of generation, the alternative to emission and exactly where mode-2
hands the named hole to an LLM. Suite 295 → 302.

**Phase 3 NEXT (roadmap work items):** deepen expansion (more deontic rules / bridges / decision points
on the Phase 2 harness); a SECOND scaffold family generated from a Track-C fragment KB without touching
engine code (proof the fragment KB, not the probe, does the work — depends on Track C).

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
