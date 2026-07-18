# pystrider — implementation plan (continuation)

A cold-start guide for the next session.

**Read the "Current state — START HERE (2026-07-18)" section immediately below, then the COURSE
CORRECTION.** Those two are the whole briefing. This file has accreted several superseded lines
(the grammapy convergence, the 2026-07-12 spike, the 2026-07-17 soundness trail); each is marked,
and none of them is the current direction. Older reading — `docs/spike_findings.md`,
`docs/code_reasoning_design.md`, `docs/roadmap.md` — describes the earlier generations and should be
read as history, not as the plan.

---

## Current state — START HERE (2026-07-18)

**Read this section and the COURSE CORRECTION below before anything else in this file.** Everything
under "Historical" and "Where we are (2026-07-12)" is a superseded line, kept as an archive; the
2026-07-17 footprint/soundness material is superseded too (see the correction — that trail was a
rabbit hole the user stopped).

**The active work is the BUILD SPINE:** a succinct spec becomes running Python through steps sequenced
by ugm's real planner, with the navigate loop (do → check → recover) as the organizing principle.

- **`experiments/build_procedure.py`** (+ `tests/test_build_procedure.py`, 51 pins) — the centrepiece.
  `to build : expand then lower then emit then check`, driven by `corpus/procedure.cnl` +
  `planning*.cnl`. Run it: `python -m experiments.build_procedure` (the walkthrough prints the whole
  argument, and is the fastest way back into the state of play — several bugs this session were found by
  READING its output, not by a test).
  Its specs, roughly in order of what each was built to demonstrate: `SPEC` (attribution over multiple
  statements) · `SPEC_UNCOVERED` / `SPEC_UNREPAIRABLE` (the two refusal kinds) · `SPEC_TWO_REPAIRS`
  (repairs compose) · `SPEC_LOOP` / `SPEC_LOOP_FLAT` (nesting; a requirement only reading the code can
  check) · `SPEC_BRANCH` (an expectation under an untaken branch is NOT OWED) · `SPEC_GUARD` (a repair
  that restructures — currently stranded, ugm #22) · `SPEC_CASES` / `SPEC_BRANCH_CASES` (several input
  sets; the second is the one that turns a vacuous pass into a refusal).
- **`experiments/ast_representation.py`** (+7) / **[`docs/ast_representation_findings.md`](ast_representation_findings.md)**
  — how ordered/nested/revisable AST lives in triples. The design rules everything else obeys.
- **`experiments/vocabulary_bridge.py`** (+7) / **[`docs/vocabulary_bridge.md`](vocabulary_bridge.md)**
  — vocabularies reconcile by BRIDGES, never convergence; bridges fix naming, never coverage.
- **`pystrider/patterns.py`** — THE PATTERN LIBRARY. Structural descriptions in a neutral vocabulary,
  read as a rule BODY to recognize and as a rule HEAD to construct. Three entries of DIFFERENT shape
  (`ITERATION`, a container of statements; `APPLICATION`, an expression with an operand; `CONDITIONAL`,
  a container that may not run at all), each driving the spine's construction AND its structural oracle.
  Its module docstring carries the authoring rules.
- **`experiments/reach_curve.py`** (+5) — the coverage claim MEASURED over a 36-spec grid: predicted
  reach vs actual reach, and zero silent-wrong. Run it: `python -m experiments.reach_curve`.
- **`experiments/bidirectional_pattern.py`** (+8) — ONE authored pattern text that both RECOGNIZES an
  iteration in hand-written Python and WRITES one from an intent. The humble goal's load-bearing claim,
  isolated and perturbation-tested. Run it: `python -m experiments.bidirectional_pattern`.

**Suite: 388 green** (`./.venv/Scripts/python.exe -m pytest -q`, ~7.5 min). Playground:
`python demos/playground/playground.py`. Site: `python -m mkdocs build`.

### What the spine currently proves

Every judgement is a rule over the substrate; Python is mechanism only. `check` RUNS the program and
MINTS one observation per output line, forming no opinion — `VERDICT`/`INSPECTION`/`SATISFIED`/`REFUSAL`
rules derive whether it is satisfied, WHICH line is wrong, and what kind of failure it is. Two
independent oracles (watch the output; READ the code via `intake` + a bridge), ANDed by a rule. Three
repair shapes — rewrite a payload, wrap an existing repair, ADD a statement — ATTRIBUTED to the statement
that actually produced a line so fixing line 1 provably does not rewrite line 2, ordered cheapest-first by
staged `cost` knowledge, and composing to reach specs no single rule covers. Programs NEST: a rule mints a
`for`, another nests statements in its body, and the unchanged recovery rules repair inside that body.

**The construction comes from a shared PATTERN LIBRARY** (`pystrider/patterns.py`), not from rules local
to the pipeline: the same description that lowering uses as a rule HEAD to build a construct, the
structural oracle uses as a rule BODY to confirm — by READING the emitted source — that it is really
there. That is the humble goal's central clause, made structural.

**A spec is checked against SEVERAL INPUT SETS.** Expectations are reified (`expectation` nodes carrying
`in_case` + `text`), because `expects hello_bob` only ever meant anything relative to `name=bob`. A second
case catches the literal-printing cheat with the OUTPUT oracle alone — so cases and the structural oracle
are independent defenses: cases catch a program that does not GENERALIZE, the structural oracle catches
one that is right the wrong way on every input you tried.

**Reachability is OBSERVED, because conditionals made it load-bearing.** An expectation is owed only by a
statement the run actually reached — the run traces which lines executed and one rule joins that to the
emission record. The same spec and rules therefore ship on one input and refuse on another, which no
static reading could distinguish. What that guard lets through is REPORTED (`unexercised`), never
silently counted as verified.

Refusal is a first-class outcome with THREE kinds, because each sends you somewhere different:
`uncovered` (missing knowledge — names the intent to author), `unverified` (insufficient knowledge — the
world disagreed), and `unstructured` (the output was RIGHT and the code is wrong). A refused build ships
NOTHING. `why` answers over generated code, citing the failed execution as the cause of the change.

**And the reach is measured, not asserted** (`reach_curve.py`): over a 36-spec grid whose reachability is
predicted IN ADVANCE from the rule set, 21/21 in-closure specs shipped, 15/15 out-of-closure refused by
name, and ZERO shipped silently wrong (each shipped program re-executed by the probe, not trusted).

### STANDING LESSONS — hard-won, do not re-derive

1. **The substrate is NAMELESS.** Minted nodes share their head's literal name; identity is the node id
   (or a structural `ByDesc`). Keying on a name silently collapsed 3 statements into 1. Never design
   against this — never ask for fabricated per-node names.
2. **A rule body DECLARES cardinality: one minted node per distinct match of the WHOLE BODY.** Not per
   head variable — this lesson previously said "a function of its head-anchored endpoints" and that is
   **wrong**, which matters because it endorses a fix that does not work (moving the offending term out
   of the head does nothing; it has to leave the rule). Verified: `n? … when ?x is_a thing and ?x tag ?y`
   mints one node PER TAG even though `?y` appears nowhere in the head. ugm's own
   `_find_skolem_witness` states it correctly — "identified by how it relates to the LHS match"; our
   distillation had drifted. Raised as ugm **#21** (is a mint head's key meant to be discoverable at
   authoring time?). NB the first draft of #21 also claimed a body-only key variable is "almost always
   accidental" — **retracted**: ugm have 24 correct uses of exactly that shape. The shape is normal and
   merely invisible; do not treat it as a smell.
   - Ask **"one per WHAT?"** and make the body match exactly that. Everything else attaches in a second
     rule with the node LHS-bound, where it mints nothing.
   - Fan-out is often RIGHT (`ast_representation` E3 mints one call per step deliberately). The lesson
     is not "avoid fan-out", it is "the body is the arity declaration".
   - **Collapse an existential into a derived fact BEFORE minting on it.** A shared condition that binds
     `?x` multiplies every mint composed with it; projecting `?x` away (`STALE`) gives one fact per
     subject however many witnesses there are.
   - **Attach a collapsed judgement to the thing it is ABOUT, not to its owner.** On a monotone graph a
     statement-level "unmet" flag means "was EVER unmet" and never clears; keyed on the PAYLOAD VERSION
     (its own node) it is permanently true of that payload and never leaks to its repair.
3. **JUDGE and ACT in separate passes.** A bank that forms a judgement and mints against it in one
   fixpoint lets the new thing be judged by evidence that PREDATES it: `stale` fired on the payload the
   same pass had just minted, before it was ever emitted or run, marking a repaired payload "seen unmet"
   having never been seen. The fact is permanent. Run the judgement bank first, over what has actually
   been observed, then the minting bank gated on its result.
4. **A "latest/current" pointer must be ASKED, never stored.** The graph is monotone, so a materialized
   `current` cannot move and the node ends up with two. Derive it read-only (`?pr current ?v when ?pr
   version ?v and not ?pr version ?w and not ?w supersedes ?v`), scoped per-node.
5. **Any bank with negation over a DERIVED fact must be scheduled.** `run_bank` stratifies by default
   since ugm #18 — but this once reported a demonstrably wrong program as OK, permanently, because the
   graph is monotone. Check a negating rule on BOTH engines (forward `run_bank` AND demand `ask_goal`):
   ugm #16 was a real bug where they disagreed.
6. **Self-extinguishing rules need FORWARD provenance.** A repair fires because a line is unmet and its
   effect makes it met, so the demand chain can never re-derive it and `why` gives `(given)`. Use
   `run_bank(..., provenance=True)` when the bank BUILDS the program.
7. **`cheaper_than` is the planner's ONLY narrowing criterion**, and the rank tool must impose a TOTAL
   order (ties broken deterministically — the §8 calculator's job). Without it every untried producer
   commits and ALL of them run.
8. **A passing run is not evidence a mechanism is doing the work.** A dead rank tool looked alive
   because its output coincided with existing behaviour; only INVERTING the costs settled it. Perturb
   the input whenever claiming something is load-bearing.
9. **Prefer an OBSERVED fact to a derived one when mechanism already knows the answer.** Attribution was
   inferred from position until loops made position meaningless; emission and the run each already knew
   their half, so the honest fix was to record both and join them with one rule. Ask what the tool
   already knows before authoring a derivation.
10. **When a consumer both WRITES structure and READS it back, mark the origin.** Both kinds of neutral
    fact land on one graph, so a requirement checked without `from_code` is satisfied by the structure
    the writer just minted — it verifies its own intention instead of the artifact, and passes. Standing
    trap for any bidirectional vocabulary.
11. **When a limitation can be hidden by tuning a MEANINGLESS knob, PIN THE LIMITATION.** `repair_guard`
    goes green at cost 3 — but only by winning an alphabetical tiebreak that `_rank_tool`'s own docstring
    calls meaningless. Re-pricing would have authored LESSON 8's trap in on purpose: a passing build whose
    passing proves nothing. Keep the honest number, pin the gap, and pin (by varying that one input) that
    the knob is the only thing in the way, so a future fix fails loudly.
12. **Migrate a representation by LIFTING THE OLD FORM WITH A RULE, never with a Python shim.** Slice 18
    changed the core of the verdict — expectations became case-tagged nodes — and 46 existing pins went
    green unchanged, because `?n expects ?x` is lifted into case `k0` BY A RULE. There is then exactly one
    representation downstream and no special path: a single-case spec is genuinely a multi-case spec with
    one case. This is the cheapest way to make a breaking change to the substrate's shape.
13. **A judgement that COLLAPSES several witnesses must attach to the thing it is ABOUT.** Stated as a
    sub-bullet of lesson 2 and it has now cost three separate bugs, so it is its own lesson. On the owner
    it silently means "SOME witness has this property", and reading it back reports the owner's whole
    fan-out: `unexercised` on the STEP listed every text the step wants, marking an expectation satisfied
    on `k0` untested because its `k1` twin had not run. Ask what ONE of these facts is about — usually a
    (case, text) pair, a payload version, a node of its own — and put it there.
14. **File findings to ugm as HYPOTHESES, not as facts** (their explicit request, 2026-07-18 — see the
    `diagnose-as-hypothesis` memory). Keep the full analysis: four of our confident diagnoses were
    INVERTED and each still found a real bug, so the analysis is load-bearing even when wrong. What
    costs them time is a causal claim stated as settled, because they then start from our model instead
    of testing it. Use the **#20 format** ("we may be holding it wrong… is this intended? are we missing
    an authoring step?"). Root cause of the inversions: we reason from ONE of ugm's two engines
    (`run_bank` forward vs `chain_sip` demand), which have a parity contract we cannot see from here.

### ⚠ UNCOMMITTED WORK IN THE TREE (2026-07-18, end of session)

Slices 17 and 18 are **written, green, and NOT COMMITTED** — `git diff --stat` shows ~317/38 across
`docs/implementation_plan.md`, `experiments/build_procedure.py`, `tests/test_build_procedure.py`. Slice 16
(conditionals) was committed mid-session; slices 17–18 were not. Suite is 388 green as it stands, so the
tree is in a committable state — check `git status` first and commit before starting anything new.

**LINE-ENDING TRAP, and it is not only the ugm feedback file.** Every file in this repo is stored LF, and
editing tools on this machine rewrite them CRLF, which produces a whole-file phantom diff (3,700 lines for
a 435-line change). `git diff --stat` looked catastrophic three times this session. Normalize before
reviewing a diff:

```python
for f in [...]:
    p = pathlib.Path(f); b = p.read_bytes()
    if b != b.replace(b'\r\n', b'\n'): p.write_bytes(b.replace(b'\r\n', b'\n'))
```

`git diff --stat --ignore-cr-at-eol` tells you whether that is what you are looking at.

### NEXT (recommended order)

1. **Derive the CASE, instead of authoring it.** The sharpest thing slice 18 left open. `unexercised`
   NAMES an untested expectation but the author still has to invent the input set that exercises it —
   and for a guarded statement the rules already know the condition (`?cs guards_on ?c`). Deriving "to
   exercise this, run a case where `banned` is true" turns the honest gap into a closed loop, and it is
   the same OBSERVE-don't-derive discipline pointed at the inputs rather than the outputs. Ours entirely,
   not blocked on ugm.
2. **The `else` arm.** `CONDITIONAL` describes the then-side only, so a two-armed `if` is half-invisible.
   A SECOND pattern description, not a bridge — cheap, self-contained, and it makes the library's
   construction story a fourth time rather than a third.
3. **Grow the grid's AXES.** `reach_curve.py` measures predicted-vs-actual reach honestly, but its grid
   varies transforms/shape/length/structure over a rule set with two expansion rules. Now stronger than
   when this was first written: branches, guards and CASES are three new axes, and reachability over a
   multi-case spec is genuinely unobvious in advance (today `_reachable` is easy to state, which is a
   sign the space is still small).
4. **Audit `_const_bindings`** (see Known debt) — the standing constraint the user set, not a new
   capability, and the only item on this list that is debt rather than reach.
5. Cheap follow-ons: retire `run_stratified` (now a thin wrapper; `run_bank` stratifies by default);
   loosen the remaining literal `order`/source assertions in `test_build_procedure.py` to the properties
   they mean (the tiebreak pin was given this treatment); a findings doc for the spine, since the
   slice log below is the only write-up.

### Waiting on ugm (nothing is BLOCKED by it)

**#22** — the only open dependency, and it holds back exactly one thing: `repair_guard`'s reachability
*through the planner*. The rule itself is authored, green, and exercised directly in the pins. **#21**
(report a mint head's skolem key at load time) is a diagnostic nicety, never blocking. If #22 is answered,
the first move is to re-run `test_an_INAPPLICABLE_cheaper_rival_STRANDS_a_costlier_repair` — it is written
to FAIL LOUDLY the moment the stranding is fixed.

### Known debt

- **`pystrider/footprint.py::_const_bindings` is a Python algorithm** (a constant-propagation pass) —
  the anti-pattern the correction names. It wants re-authoring as CNL rules over intake facts, or
  deleting with the soundness trail it serves.
- `intake` still does not model: aug-assign, attribute/subscript store, tuple unpack, `with`, and a
  `for` over a non-Name target. Each is an audited `not_modelled` marker, and that list IS the coverage
  worklist. Two kinds GRADUATED off it, both because a pattern needed to see them and no bridge can
  close a coverage gap: bare calls (`expr_stmt`) and `for` over a plain name (`for_loop`).
- **`repair_guard` is authored and pinned but UNREACHABLE by the planner** (ugm #22 — an inapplicable
  cheaper rival strands it). The rule is exercised directly in the pins; `SPEC_GUARD` refuses. Revisit
  when ugm answers, and delete the stranding pin the moment it starts passing.
- `CONDITIONAL` describes the THEN arm only, so a two-armed `if` is recognized by its then-side and its
  `else` is invisible. Coverage gap in the PATTERN (a second description closes it, not a bridge).
- `intake._branch_structure` does not append the branch node to `self.statements`, so an `if` nested in a
  loop body contributes no `loop_body` link — unlike a nested `for`, which does. An inconsistency between
  the two containers, deliberately left alone in slice 16 to keep the blast radius small; it means
  "what does this loop body contain?" under-reports a conditional child.
- Cases must be authored BY HAND. Nothing derives which input sets would exercise an unexercised
  expectation, so `unexercised` names the gap but the author still has to close it. Deriving a case that
  takes a named branch is the obvious next lever on this axis.
- `judge_source` (judging a FOREIGN program) attributes output by position — the k-th printing statement
  realizes the k-th step. Declared in its docstring and used nowhere in the build loop, but it means
  that helper cannot judge a foreign program containing a loop.
- `APPLICATION` matches an application to a NAMED value, so `f(g(x))` is not recognized. A coverage gap
  in the PATTERN, not a bridge.

The durable record is the **memory files** (`build-procedure-spine`, `bidirectional-pattern`,
`reach-measured`, `vocabulary-bridges`, `ast-minting-unblocked`, `humble-goal-course-correction`,
`diagnose-as-hypothesis`, `pattern-writer`) and, for the superseded line,
**[`the_case.md`](the_case.md)** / **[`deep_dive.md`](deep_dive.md)** / **[`roadmap.md`](roadmap.md)**.
ugm feedback + their answers live in `../ugm/docs/feedback_from_pystrider.md` (we are at item **#22**,
rewritten as a question after their note on how we file — see STANDING LESSON 14). **That file uses LF
line endings; write it with `write_bytes`, not `write_text`, or you produce a 2000-line phantom diff.**

---

### Archive — the 2026-07-17 line (SUPERSEDED, skip on a cold start)

Everything from here to the COURSE CORRECTION describes the soundness/footprint trail the user stopped
on 2026-07-18 ("we are again going down the rabbit hole of the theorem-prover family of tools"). It is
factually accurate about what was built and still green in the suite, but it is NOT the current
direction, and its "Next steps" list is superseded by the NEXT section above. Kept for the repo-state
description (what exists, what was deleted) and because the wildcard/soundness work is still shipping
code.

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

---

## The 2026-07-18 arc — slice log (the record of how the spine was built)

Fifteen slices. **Ordering warning: 1–9 read oldest-first, then 10–15 read NEWEST-FIRST** (slice 15
immediately after 9a, slice 10 last) — an artifact of each session prepending. Slices 10–15 are the
second session: loops end-to-end, the pattern library, and the reach measurement. Read for *why* something is the way it is; the STANDING LESSONS at the top of
this file are the distilled version, and each probe's module docstring carries its own argument. Several
entries record a mistake and its correction — those are the valuable ones.

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

**SLICE 8 DONE (2026-07-18) — a repair DRIVEN BY READING THE CODE.** `build_procedure` 20 pins, suite
344. Until now the structural oracle could only FAIL a build; now it drives a third repair shape.
`RECOVERY_AUDIT` fires on the structural gap itself (`?p requires_call ?f and ?f is_a policy_call and
not ?c is_a call and not ?c calls_func ?f`) and **MINTS A NEW STATEMENT** rather than revising a
payload, placing it by linking before whichever statement has no predecessor (so the emit walk stays a
linked list). `?f is_a policy_call` scopes it — `greet` is also `requires_call` but belongs inside a
payload, so no bare `greet()` is bolted on (pinned).

**The demonstration:** `audit()` prints NOTHING. After `repair_greet` the run already produces the final
output `['hello_bob','boss']` and the build is still `STILL WRONG`; `repair_audit` then changes stdout
not at all and makes it satisfied. **No output-watching loop could ever find that repair.** That is the
argument for the second oracle paying for itself, not just catching cheats.

Mechanically this needed the read-side facts on the WORKING graph, not a scratch copy — a repair driven
by the structure of the code needs that structure in the graph it runs over. `observe_code` now runs
alongside the output observation each time the program runs, and both accumulate monotonically (the right
reading: "has this program ever been seen to call `audit`?", so the repair self-gates once it has).

**SLICE 9b (2026-07-18) — ugm ANSWERED #20 and FIXED it; costs now order the recovery.** Suite 346.
Their answer corrected our diagnosis: replan was **not** picking in staging order, it was picking
**every** untried producer at once — because `cheaper_than` (which our stub never produced) is the banks'
ONLY narrowing criterion, so with no costs nothing was ever `dominated`. `corpus/procedure.cnl` gained
the rank call for untried producers of an unmet effect + an `outranked_by` block per cheaper untried
rival (with the two `drop` rules that make the cascade work — without them a cheaper alternative that
itself fails strands the next-cheapest forever). So **"try the smallest edit first" is now authored
purely by staging `?o cost ?c`**, exactly as we wanted.

Our side: (1) the pin was rewritten — it asserted the opposite and now verifies that INVERTING the costs
INVERTS the choice; (2) the rank tool now imposes a **TOTAL order** (ties broken deterministically on
name), which their answer flags as the §8 calculator's job — a forward round collects all matches before
firing, so two incomparable ops both commit; (3) costs re-derived on a defensible principle, "how much
of the existing program does this edit disturb" — `greet` rewrites one payload (1), `audit` ADDS a
statement and disturbs nothing existing (2), `shout` revises an already-repaired payload (3). Effect: the
default build now runs **two** repairs instead of three.

Known limit, pinned upstream: with no cost staged, every untried producer still commits — the bank has
no basis for a tiebreak and a total-order `rank` is where one belongs.

**SLICE 18 DONE (2026-07-18) — SEVERAL CASES: one spec, more than one input set.** 51 pins (+5),
suite 388. The follow-on slice 16 argued for, and it closes that slice's own honest gap.

**The premise.** `expects hello_bob` was only ever true relative to `name=bob`. A spec checked against ONE
input set cannot distinguish a program that COMPUTES the answer from one that prints the right literal —
which is precisely why the structural oracle had to be invented. Expectations are now REIFIED
(`expectation` nodes carrying `in_case` + `text`) and every judgement reads them through that node.

**The legacy shorthand is lifted BY A RULE, not by a Python shim** (`?n expects ?x` → an expectation in
case `k0`), so there is exactly ONE representation downstream and a single-case spec is genuinely a
multi-case spec with one case. That is what let 46 existing pins go green unchanged through a change to
the core of the verdict. Reachability became per-case too (`reached_in ?c`), with line identity left
per-EMISSION so `ATTRIBUTION` joined unchanged — the case rides on its own predicate.

**THE HEADLINE — a second case catches the literal cheat using the OUTPUT ORACLE ALONE.**
`print('hello_bob')` judged against `SPEC_CASES`: `prints_ok True` on one case, `prints_ok False` on two.
So cases and the structural oracle are two INDEPENDENT defenses against the same class of wrong-for-the-
right-reason program, and neither makes the other redundant: **cases catch a program that does not
GENERALIZE; the structural oracle catches one that reaches the right answer the wrong way even on every
input you thought to try.** One repair satisfies both cases, because `greet` applies to whatever `name`
is rather than patching an observed output.

**...AND IT CLOSES SLICE 16'S GAP.** `SPEC_BRANCH` shipped while reporting `goodbye_bob` untested. Add the
case that TAKES the guard and the same spec, with the same rule set, refuses `unverified` — the
expectation stopped being untested and immediately turned out to be unreachable. **The vacuity was in the
TESTING, not in the rules**, which is why no cleverer rule was the answer.

**A BUG A SINGLE-CASE PIN COULD NOT HAVE CAUGHT — STANDING LESSON 2's corollary, again.** `unexercised`
was first derived onto the STEP. On the step it means "SOME expectation of this step was untested", so
reading it back reported EVERY text the step wants — a statement satisfied on `k0` was listed as
unexercised because its `k1` twin had not been run. Moved onto the EXPECTATION node, which is one
(case, text) pair and exactly the grain the claim is made at. **Attach a collapsed judgement to the thing
it is ABOUT, not to its owner** — third time this has bitten, now pinned directly
(`test_UNEXERCISED_attaches_to_the_EXPECTATION_not_to_the_STEP`).

Also: the check log now names each case (`k0:['bob']  k1:['ann']`), because `['bob']` says nothing
without the inputs it came from.

**SLICE 17 DONE (2026-07-18) — A REPAIR THAT CHANGES REACHABILITY, and the planner limit it exposed.**
46 pins (+5), suite 383. The fourth repair SHAPE: the three before it rewrite a payload, wrap a previous
repair, and ADD a statement — each leaves the set of executed statements alone. `RECOVERY_GUARD`
restructures, minting an `emit_if` and making the existing statements its body.

**RESTRUCTURING BY ADDITION — the monotone move.** Nothing is moved because nothing CAN be: a
`stmt_before` fact cannot be retracted. The new container CLAIMS the statement (`body_has`) and the
already-existing `in_body` derivation takes it off the top-level sequence; the emit walk filters dangling
links to statements outside the scope it is sequencing. This is the versioning idiom one level up, and it
is worth naming as the general answer to "move X" on a monotone graph: **add a claimant and let a derived
projection re-scope it.** Two rules, not one, per STANDING LESSON 2 — minting with `?pr is_a emit_print`
in the body would key the skolem on the STATEMENT and give one guard per statement (pinned at two).

**`SPEC_GUARD` is the cleanest structural-oracle case yet**: its output is EXACTLY right on the first run
(`prints_ok: True` immediately), so the entire drive comes from reading the code. The repair authors no
emit vocabulary of its own — it attaches `then_does` to the STEP and lets the shared `CONDITIONAL_TO_EMIT`
bridge and the existing `lowers_to` do the rest, which is the pattern library paying off a third time.

**⚠ THE REAL FINDING — AN INAPPLICABLE CHEAPER RIVAL STRANDS A COSTLIER REPAIR, PERMANENTLY.** The rule
works (applied directly it produces the intended program and both oracles pass) and **the planner cannot
reach it.** `repair_shout` (cost 3) is cheaper, can never run here (its `payload_greeted` precondition
cannot hold on a spec where `repair_greet` did not apply), and is therefore never `done` — and never
`excluded` either, because `procedure.cnl` derives exclusion from `?o discrepancy ?e`, i.e. only an op
that RAN AND FAILED is ruled out. Both drop rules for `?alt outranked_by ?x` are never satisfied and the
block is permanent. The cascade assumes every cheaper rival will eventually be TRIED, which holds when
alternatives differ only in cost and stops holding the moment one declares a precondition the world
cannot satisfy. Filed as ugm **#22**, a QUESTION in the #20 format (STANDING LESSON 14), with our
diagnosis flagged as hypothesis and the three places we may be holding it wrong listed.

**THE METHOD NOTE — we did NOT re-price to make it green.** Cost 3 "fixes" it only by winning the
alphabetical tiebreak against `repair_shout`, and `_rank_tool`'s own docstring says the tiebreak carries
no meaning; a green build resting on it would be STANDING LESSON 8's trap authored in deliberately. 4 is
the honest number under the stated principle ("how much of the existing program does this edit disturb"
— restructuring disturbs most), so 4 stays and the gap is PINNED instead:
`test_an_INAPPLICABLE_cheaper_rival_STRANDS_a_costlier_repair` asserts the stranding AND, by varying that
one number, that the cost is the only thing in the way. If the planner ever gains a fix, it fails loudly.
**Generalize this: when a limitation can be hidden by tuning a meaningless knob, pin the limitation.**

**SLICE 16 DONE (2026-07-18) — CONDITIONALS, and REACHABILITY became an OBSERVED fact.** 41 pins in
`test_build_procedure.py` (+7). Plan item #2. `if` is a third nesting shape, and the reason it was worth
doing is not the shape — it is that a branch body **may run no times at all**, which falsifies an
assumption every unmet condition in the spine was written under.

**The assumption.** Every unmet condition here is a NEGATION: "no observation shows this statement
printing what it wants". That silently assumes the statement had a CHANCE to produce one. A loop body
always did (possibly zero iterations, but the pipeline never generated an empty sequence); a branch body
may legitimately never run, and then "never observed to print it" says nothing whatever about whether the
code is right. Left unfixed, the repairs chase a line that was never going to print and a correct build
refuses.

**The fix is STANDING LESSON 9 again, and it is the third time this file has reached for it.** Not a
static reachability analysis — that is both the Python algorithm the correction forbids and *usually
wrong*, since whether a branch is taken depends on the inputs. The run ALREADY KNOWS: `_run_and_observe`
traces the generated frame and mints `was_executed` on the lines it saw, and one rule (`REACHED`) joins
that to the emission record `emit` was already keeping. Same move as `check` (output) and `ATTRIBUTION`
(which statement produced a line), one level further down.

**THE PIN THAT SETTLES IT: the same spec and the same rules flip verdict on the INPUT alone.**
`SPEC_BRANCH`'s `ban_line` expects `goodbye_bob` — *exactly* the expectation `SPEC_UNREPAIRABLE` is
refused over, since no recovery rule reaches `goodbye`. Guarded by a branch, with `banned=False` the
build SHIPS (not owed, statement untouched at v1); with `banned=True` the identical spec REFUSES
`unverified`. No static reading of that code distinguishes those two cases. That is the argument that
observation was the honest seam and not a shortcut.

**And the boundary it creates is REPORTED, not hidden.** Reachability-aware `unmet` means an unreached
expectation cannot fail a build — so a build could ship having verified less than it appears to. `?st
unexercised yes` derives exactly those, and `unexercised()` reports them (`['goodbye_bob']` above,
empty once both branches are taken). Not owed, but not verified either; counting them as satisfied would
claim more than was checked. This is the vacuity hazard named rather than papered over — and the natural
next slice is driving one spec over several input sets.

**The library took a third entry without changing its construction.** `CONDITIONAL`
(`?x checks ?cond and ?x then_does ?body`) is a third SHAPE — `ITERATION` is an unconditional container,
`APPLICATION` an expression, this a *guarded* container — and it went in by the same three steps: mint on
invariants, ATTACH with the node LHS-bound, BRIDGE to each consumer. Both directions pinned (it lowers the
branch, and recognizes one in hand-written Python). `checks` rather than `tests` deliberately: intake
already spends `tests` on its null-guard register, and a pattern borrowing a consumer's word would be
reconciling by coincidence instead of by a bridge. Two generalities held without edits, which is the
evidence they were real: `?pr in_body yes when ?lp body_has ?pr` needed no clause for the new container,
and the RECOVERY rules repair inside a branch body unchanged.

**INTAKE COVERAGE GROWN — the structural register for `if`.** `if` was already modelled for control flow
(fork/merge, plus the null-`guard` shape) but had no STRUCTURAL register, so no pattern could read it —
a coverage gap, and no bridge closes those. `_branch_structure` emits `is_a branch` / `condition` /
`then_body`, deliberately mirroring `_for`'s, with the same per-SOURCE guard (`_structured`) for the same
reason: an `if` inside a loop is walked once per unrolling. 74 existing intake-facing pins unaffected.

**A MISTAKE WORTH RECORDING — STANDING LESSON 1, live.** `unexercised()` first read the flag with
`holds(g, g.name(st), ...)`. Steps are MINTED and therefore name-degenerate, so every step resolved to
whichever node `nodes_named` returned first, and the helper reported an EMPTY list while the rule was
firing perfectly. The rules were right and the reader was wrong — which is the failure mode the nameless
substrate produces, and it looks exactly like a rule that did not fire.

**SLICE 15 DONE (2026-07-18) — REACH MEASURED.** `experiments/reach_curve.py` + 5 pins, suite 371.
The coverage claim ("a limited rule set navigates a large space") had never been measured; every slice
had demonstrated it on specs chosen to demonstrate it.

**The method matters more than the number.** A raw pass rate over a grid we designed would only report
how many unreachable specs we chose to include. So each of the 36 cases is labelled reachable-or-not
IN ADVANCE from the rule set alone (`_reachable`), making each run a prediction falsifiable in both
directions. Result over the full grid:

    inside the closure : 21/21 shipped
    outside it         : 15/15 refused by name
    SILENT WRONG       : 0

Successes by repairs that CHANGED the program: 5 needed none, 8 one, 7 two, 1 three — so composition
is doing real work, not decorating a lookup table. Repairs ATTEMPTED peaked at 3; the gap between
attempted and applied IS the navigate cost, and it is paid on successes too (counting attempts as
"composition" would have overstated the claim, which the first draft did).

**Two findings worth keeping.** (1) The SHAPE axis costs no reach — every reachable transform stayed
reachable inside a `for` body, repaired by the same rules, which is the empirical form of "the pattern
did not need loop-aware repairs". (2) `shout_only` is the sharp case: `shout` EXISTS as a repair and
still cannot uppercase a raw value, because it only ever wraps an already-greeted payload. **Reach is
the closure of what the rules COMPOSE to, not the set of functions lying around** — the distinction
that makes this a measurement rather than an inventory.

Every shipped program is re-executed BY THE PROBE and checked against its spec independently of the
loop's own verdict: a probe that measured success using the mechanism under test would measure nothing.

**SLICE 14 DONE (2026-07-18) — A SECOND PATTERN, OF A DIFFERENT SHAPE.** 34 pins, suite 366. The
library had one entry, so "library" was still a promise: `ITERATION` might simply have been fitted to
its two consumers. `APPLICATION` (`?x applies ?fn and ?x to ?arg`) is deliberately a different KIND of
thing — an iteration is a container of statements, an application is an expression with an operand —
and it went in without changing the library's construction: mint on invariants, ATTACH the pattern with
the node LHS-bound, BRIDGE to the consumer's vocabulary. The spine's two payload repairs are now
generated from it by one helper (`_repair_by_application`), where before each hand-minted its own
`ast_call`.

**It also bought a capability, which is the better argument than symmetry.** `requires_call greet` can
only say the function is mentioned somewhere; the application pattern asks WHAT IT IS APPLIED TO. The
same program — `print(greet(title))`, greet called on the wrong variable — passes the first reading and
fails the second (pinned both ways). That is the almost-right program that neither watching stdout for
one input nor counting calls can catch.

Honest limit, recorded in the pattern: it recognizes an application to a NAMED value, so `f(g(x))` is
not matched (the argument expression reads nothing). That is a coverage gap in the PATTERN, not in a
bridge, and no bridge can close it.

**SLICE 13 DONE (2026-07-18) — THE PATTERN LIBRARY WIRED INTO THE SPINE.** 32 pins, suite 364. Slice 11
proved one description can drive both halves; this makes it the architecture rather than a demo.

**`pystrider/patterns.py` is now a real module**, not constants in a probe — promoted the moment a
SECOND consumer appeared, since a "library" with one consumer proves nothing. `build_procedure`'s
LOWERING no longer owns a loop rule: it mints a `loop_node` on invariants, ATTACHES `ITERATION` as a
rule HEAD, and bridges the neutral structure into its own emit vocabulary with `ITERATION_TO_EMIT`.
`at` is attached separately and deliberately — WHERE a loop sits is the pipeline's business, not part
of what makes an iteration an iteration. EXPANSION gained `is_a loop_step` purely to give the mint an
INVARIANT to key on (lesson 2: keying on `?ls loops_over ?v` happens to be single-valued today, which
is the kind of luck that stops being luck).

**THE PAYOFF — a requirement authored in the pattern's vocabulary and verified by READING the code.**
`report requires_iteration_over names` is satisfied by the write half and confirmed by the read half
parsing the EMITTED SOURCE. This needed `ITERATION_FROM_INTAKE` to stamp `from_code`: a consumer that
both writes structure and reads it back holds neutral facts of both origins on one graph, so without
it the check would have been satisfied by the loop the writer had just minted — verifying its own
intention instead of the artifact. Demonstrated by `SPEC_LOOP_FLAT`: a spec that never asks for a loop,
whose output is EXACTLY right (`prints_ok: True`), refused because the required shape is absent.

**A THIRD REFUSAL KIND, forced by the above — `unstructured`.** The flat build first refused with "the
program ran and the world disagreed" and printed IDENTICAL wanted/got lists. The world had agreed; the
code was wrong. A refusal that names the wrong cause is barely better than no refusal — it sends you to
fix the output, which is already correct. `refused_unstructured` is derived from `structural_unmet` and
reports "the output was RIGHT … but reading the code shows X missing". Found by reading the walkthrough
output, not by a test.

**SLICE 12 DONE (2026-07-18) — STANDING LESSON 2 WAS WRONG, and it was costing us bugs.** 29 pins,
suite 361. Prompted by the user asking to discuss the lesson before building on it — the right call.

**The lesson misstated the substrate.** It said a skolem is "a function of ALL its head-anchored
endpoints". Verified false: `n? … when ?x is_a thing and ?x tag ?y` mints one node PER TAG with `?y`
nowhere in the head. The skolem is keyed on the WHOLE MATCH. ugm's own `_find_skolem_witness` says this
correctly ("identified by how it relates to the LHS match") — our distillation had drifted, and the
error endorsed a fix that does not work (moving the term out of the head changes nothing). Rewritten as
lesson 2, corrected in `ast_representation.py` / its findings doc / its test docstring, and filed as
**ugm #21** — a *diagnostic* ask (report a mint head's key at load time), since this never errors and
the symptom surfaces far from the cause.

**It was live in green pinned code.** The loop build minted TWO identical `ast_call` nodes and gave one
statement two `arg_v2` values, because the shared unmet condition binds `?st wants ?x` and a looped
statement wants one text per element. Nothing failed — the head names no `?x`, so the duplicates were
interchangeable and `one()` picked between equals. Cured by projecting `?x` away first (`STALE`: one
fact per (statement, payload) however many expectations witness it).

**Which uncovered a second, worse bug — and a new standing lesson.** `stale` was materialized in the
SAME bank pass that minted the payload, i.e. before that payload had ever been emitted or run: a
repaired payload was permanently marked "seen unmet" having never been seen at all, so `repair_shout`
would rewrite a line `repair_greet` had just fixed. Only the planner's actuator guard was hiding it, and
no test would have caught it. Two things fix it, both now lessons: staleness attaches to the PAYLOAD
VERSION (its own node) rather than to the statement, so a monotone fact cannot leak from a payload to
its repair; and **JUDGE and ACT run in separate passes** (new lesson 3) — `ws.rules(JUDGE)` over what
has actually been observed, then the minting bank gated on its result.

Pinned: `test_a_repair_mints_ONE_node_however_many_EXPECTATIONS_are_unmet`,
`test_staleness_attaches_to_the_PAYLOAD_so_it_cannot_leak_to_the_repair`. METHOD NOTE: the second bug
was found only because the first pin was written to assert a *graph* property rather than an output —
the program was correct throughout.

**SLICE 11 DONE (2026-07-18) — ONE PATTERN, BOTH DIRECTIONS (the humble goal's load-bearing claim).**
`experiments/bidirectional_pattern.py` + 8 pins, suite 359. Prompted by an audit against the COURSE
CORRECTION: of its five clauses, "a library of patterns expressed AS RULES so the same library serves
both writing and understanding" was the one we had asserted in prose and not built — the two halves met
at exactly ONE predicate (the `INSPECTION` bridge) and shared no pattern.

**The construction.** A pattern is a structural description authored once in the neutral vocabulary —
`?x repeats_over ?seq and ?x element ?v and ?x each_does ?body`. That is a conjunction of triples,
which is what ugm accepts on EITHER side of a rule: read as a rule BODY it recognizes, read as a rule
HEAD it constructs. Each half reaches its own world through a bridge (`for_loop`/`iterates`/`loop_body`
from intake; `emit_for`/`iter_over`/`body_has` to the emitter), and neither vocabulary appears in the
pattern (pinned). The mint is split in two — the loop node is minted on invariants, the description
attached with the loop LHS-bound — because the description as a mint head would mint one loop per body
statement (STANDING LESSON 2 again, the second time in one day).

**Pinned:** recognizes an iteration in hand-written Python; writes one from an intent that runs; ROUND
TRIP (the pattern recognizes the code it wrote); and **PERTURBATION** — renaming one word in the shared
description takes BOTH halves dark, which is the only evidence that distinguishes one library from two
that happen to agree. (The first perturbation attempted, adding an unbound `?x tagged_by ?t`, was
REJECTED by ugm as an RHS-only head variable — the substrate refusing an ill-founded head, which is
itself worth knowing.)

**INTAKE COVERAGE GROWN — `for`.** The read half was blind to every iteration (`for` was an audited
`not_modelled`), and no bridge can close a coverage gap. `intake._for` now models it in BOTH registers,
and the distinction they force is worth keeping: **structure is per-SOURCE, state is per-UNROLLING.**
Structural facts (`for_loop`/`iterates`/`binds`/`loop_body`) are emitted once, keyed on source position;
the CFG (states, the element binding from an `unknown_expr`, the body threading) repeats per unrolled
iteration exactly as `_while` does. Without that split a nested loop minted a second `for_loop` node for
the same source statement and "how many loops does this function have?" answered 3 for 2 (caught by a
pin, not by the walkthrough). `loop_body` links DIRECT children only. `for` accordingly graduated off
the `not_modelled` list in `test_caveats.py`; a `for` over a non-Name target is still unmodelled and is
now the case pinned there.

**SLICE 10 DONE (2026-07-18) — LOOPS END-TO-END, and attribution became an OBSERVATION.**
`build_procedure` 27 pins, suite 351. Plan item #1: the pipeline had only ever emitted FLAT statement
lists. `SPEC_LOOP` declares an intent that ITERATES with another intent `inside` it; expansion mints a
looping step, lowering mints an `emit_for` and nests the body statement (`body_has`, `in_body` — the
`ast_representation` E4 idiom, now in the real pipeline), and the emit walk sequences each scope on its
own terms. **The unchanged `RECOVERY` rule repairs the statement inside the body**, and `print(title)`
after the loop keeps its v1: a repair in a nested scope stays in that scope.

**THE REAL FINDING — position stopped being index, so attribution had to be OBSERVED.** One statement in
a loop body produces one output line per iteration, so "the k-th statement prints the k-th line" — the
assumption every repair was attributed with — is simply false, and no index arithmetic recovers the
mapping. The fix was not a cleverer derivation: `emit` records WHERE it put each statement
(`source_line`), the run records which line was executing when each output appeared (`from_line`, via a
`print` that reads its caller's frame), and ONE rule joins them (`ATTRIBUTION`). Attribution is now a fact
the world reported, the same move `check` already made for the output itself. Evidence it was the right
seam: **the recovery rules did not change**, and the flat specs behave identically. Line identities are
scoped per EMISSION (`r2L4`) because `repair_audit` ADDS a statement and shifts every line below it —
without that an old observation attributes to whatever moved onto its line number.

**THE E1 TRAP, MET FOR REAL.** `st? … and st? wants ?x` had `wants` in the MINT HEAD, so an intent with
TWO expectations (exactly what a looped intent has — one per element) minted TWO steps; the emit walk
silently dropped the second and the build reported an unmet spec for a program that was correct. Fixed by
the documented idiom: mint on invariants, attach `wants` in its own rule with the step LHS-bound. STANDING
LESSON 2 is not theoretical — it bites the moment arity stops being one.

Also: `judge_source` (judging a FOREIGN program) has no emission record to attribute with, so it declares
its assumption explicitly — the k-th PRINTING statement realizes the k-th step — kept out of the build
loop entirely.

**SLICE 9a (2026-07-18, superseded by 9b) — `rank` made real; the intended benefit did NOT materialize.** Suite 345, 21 pins. `_rank_noop` (a Python stub that only stamped `ranked`) is gone: costs are
now staged as knowledge (`?o cost ?c`, from `Step.cost`) and a real `rank` tool derives `cheaper_than`,
which is exactly the §8 comparison-as-calculator boundary `planning.cnl` documents.

**But it does not order the repair attempts, which is what it was for.** Caught by INVERTING the declared
costs and observing the order unchanged — necessary, because the costs initially agreed with staging
order, so the first "working" run proved nothing. Tracing shows `rank` is invoked for
`expand`/`lower`/`emit` and the FIRST repair only; the later repairs are alternative producers reached
through discrepancy→replan, never reach `cost_settled`, and are never ranked. Attempt order among them is
still staging order. Filed as ugm **#20** (a QUESTION, not a bug — we may be holding it wrong): is
cost-ranking meant to govern replan's choice of alternative, and if not, how should "try the smallest
edit first" be authored? Pinned so that if the replan path gains cost-ordering the pin fails loudly.

METHOD NOTE worth keeping: a passing run is not evidence that a mechanism is doing the work. The costs
agreeing with staging order made a dead tool look alive; only the inverted-cost experiment settled it.

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

**Next steps (SUPERSEDED — the pre-correction candidate list; the live list is NEXT at the top of this
file. Kept only to show what was on the table before the course correction):**

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
