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

---

## Follow-up: codegen from a business rule + round-trip understanding — feasible, and still one firmware

Probe: `experiments/codegen_understand.py`, pinned by `tests/test_codegen_understand.py` (14 tests).
Question (from [`codegen_understand.md`](codegen_understand.md)): can we generate code from a
**business rule** by *recursive subgoal expansion* (not whole-function templates), and can we
*understand* code back into business terms? **Verdict: yes on both, and it is the same loop again.**
This closes the first of the three edges `spec_synthesis.py` left open ("deriving the skeleton pool
**compositionally** — slot-filling beyond whole-function templates").

**Intent:** `accrual` — compute `principal * rate * days / 365`. Unlike `spec_synthesis`'s flat
template choice, the emit tool pre-mints a pool of **recipes** (each satisfies one *need* by binding
a variable to a value built from its own sub-needs) grouped into candidate **plans** (decompositions).
The CNL rules do a **recursive subgoal expansion** as stratified Datalog: a need is `covered_in` a
plan if it is a leaf parameter or produced by a recipe in the plan; a plan is `complete` iff it has
no `gap` (every sub-need bottoms out) — the recursion, as one positive rule + two NACs. `who realizes
<spec>` then backward-CHAINs completeness **and** the feature conjunction, exactly as before. The
winning plan is emitted **bottom-to-top** (topological over the subgoal DAG: intermediates bind
before the root that reads them, return last) and **verified by re-execution** (run it on samples,
require the accrual formula) — trust by execution, never by the recipe's claim (a recipe that divides
by 360 fails the check).

**The non-trivial finding — a readability flip, the compositional mirror of the strictness flip.**
Two decompositions realize the spec and compute the *same number*: an **inline** one (one statement,
compact) and a **stepwise** one (named `annual_interest` / `day_fraction`, readable). CHOOSE prefers
the compact inline by default — until one word (`readable`) is added, which requires the feature
`named_steps` that only the stepwise plan provides, so the inline plan stops realizing the spec at
all. Same shape as `return v or {}` vs the explicit ifexp: an added requirement excludes the compact
form because compactness no longer buys what the spec now demands.

**Understanding is synthesis run backwards, over the SAME completeness derivation.** A single extra
rule (`?fn computes ?k when ?plan emitted_as ?fn and ?plan for_intent ?k and ?plan complete yes`)
**recognizes** code the system itself generated — attaching the winning plan's topology to the
emitted function derives `compute_accrual computes accrual`, bridging the business term to the code.
This is the doc's "recognize code generated by the system, to allow round trip". And the escape hatch
the doc calls for: a function we did **not** generate (an arbitrary `sort`) has no plan fingerprint,
so recognition derives nothing — the fact is then **supplied directly in CNL** (`mystery is_a
sort_function`), answered with no derivation ("provide a fact without relying on fact derivation").

**The two invariants hold, which is the reassuring part.** (1) *Rules never mint* — a subgoal tree is
existential-minting territory, so the emit tool pre-mints the recipe/plan pool and the rules only
*select*; the pool size is the synthesis fuel (mirror of state-pool = unroll budget). (2) *Trust by
execution* — both decompositions are RUN and checked. Same duplicate-node gotcha as elsewhere:
`add_node(name)` mints a fresh node per call, so a directly-authored fact must thread every mention
of a name through one cached id or the join silently fails (cost real time on the round-trip link).
Still a probe; not productized. **Still open:** a richer recipe algebra (conditionals, loops, calls
between generated functions — the first is now probed, below), recognition from *topology alone* (not
the retained plan label) so externally-written-but-normalizable code is recognized, and the
normalization rules the doc names as the "normalization tax".

---

## Follow-up: control-flow synthesis by demand-driven pre-minting, verified symbolically — feasible

Probe: `experiments/controlflow_synthesis.py`, pinned by `tests/test_controlflow_synthesis.py`
(8 tests). Question (the frontier `codegen_understand.py` left open): does subgoal expansion break
when the generated code needs **control flow**, and does the pre-minted pool then blow up
combinatorially? **Verdict: no on both — and the analysis half now grades the candidates.**

**Intent:** a *total* `fetch(x)` — never raise, never return None — which genuinely needs a guard.
Three findings:

1. **Control flow is synthesizable under the no-rule-mint constraint.** A `program` goal expands into
   a strategy that emits an `if x is not None: return x.value ; return {}` skeleton with HOLES for its
   sub-goals — a pre-minted control skeleton, exactly as intake pre-mints an unrolled loop's state
   chain. Rules only *select* the strategy; the tool fills the holes. A guard is one more skeleton.

2. **The pool is minted DEMAND-DRIVEN, so control flow does not blow it up.** This tests the answer to
   the "would genuine rule-minting help?" question (no — see `feedback_from_pystrider.md` #2): instead
   of pre-materializing every candidate program up front (the cross-product `spec_synthesis` warned
   about), the emit tool mints one goal's candidate strategies at a time and only descends into a
   strategy's sub-tree when that strategy is actually TRIED. In the probe: **5 strategy-nodes minted
   vs. 8 an eager pre-mint would materialize** — the 3 saved are the entire audit/log/timestamp
   sub-tree of an out-competed strategy, never expanded because a better one verified first. That gap
   is the un-explored cross-product; lazy minting refuses to pay it, and stays inside the §8-tool
   contract (minting in the tool, never in a rule) with **no ugm change**.

3. **Verification GATES selection, using the PRODUCTIZED analyzer as the oracle.** CHOOSE prefers the
   compact `return x.value` (no guard) — but the real `analyze` REJECTS it (`AttributeError` under
   `x=None`), so synthesis falls back to the guarded form, which `analyze`/`analyze_return_none`
   clear. The generator proposes; the analyzer disposes. This is the strongest closure yet: synthesis
   is verified not by a bespoke numeric/concrete oracle (as in the earlier probes) but by re-running
   the **same productized analysis loop** the tool uses to find bugs — one firmware, both directions,
   trust by the checker.

**Still open:** loops in generated code (bounded, mirroring the unroll budget), a sub-goal satisfied
by *emitting and calling a helper* (multi-function synthesis — now probed, below), and a spec
language that carries the checkable properties directly (so the analyzer's whole effect vocabulary,
not just a hardcoded hypothesis, drives verification).

---

## Follow-up: multi-function synthesis (emit + call a helper), verified cross-call — feasible, and the verifier shapes it

Probe: `experiments/multifunction_synthesis.py`, pinned by `tests/test_multifunction_synthesis.py`
(8 tests). Question (the frontier after control-flow): does the synthesis loop still close when a
subgoal is satisfied by *emitting a helper and calling it* — so correctness spans a **call
boundary** — and can the **productized inter-procedural analyzer** be the oracle? **Verdict: yes —
and the verifier's precision boundary visibly shapes what the synthesizer certifies.**

**Intent:** a *total* `process(x)` that delegates to a helper `extract(v)` (which derefs `v.value`) —
never raise across the call, even on `x=None`. Three findings:

1. **A subgoal can be a helper.** The `program` goal expands into a composition that emits *two*
   pre-minted function skeletons — a helper and a caller that calls it — the tool filling holes,
   rules only selecting. Multi-function synthesis is compositional synthesis one level up (function,
   not statement), with no new emit-side machinery.

2. **Verification is cross-call, through the productized `Session`.** Each candidate is emitted as two
   real functions, loaded into a `Session` (each under its own namespace — identity by
   `(function, name)`), the call `link_calls`-wired, and `analyze_across_call` seeds a hypothesis
   about the caller's input and reads outcomes *inside the callee*. The value crosses the boundary
   through the exact inter-procedural machinery the analyzer ships — no bespoke oracle. A composition
   that lets a None flow across the call into an unguarded deref is rejected.

3. **Verification is path-sensitive across the call — synthesis found the boundary and moved it.**
   Three compositions are proposed in CHOOSE order: `naive` (delegate + deref — None genuinely
   crosses → rejected), `guard_caller` (guard *then* delegate), and `total_helper` (helper guards its
   own input). `guard_caller` is *safe at run time* (the guard really prevents the call on None — the
   probe pins this by concrete execution), and the cross-call link now **credits** that guard:
   `Session.link_calls` stamps `refine_nonnull` on a call sitting inside `if arg is not None:`, and
   the refined cross-call assign (semantics rule 2e) carries only the non-None value into the callee.
   So `guard_caller` is **certified**, and CHOOSE's compact caller-side guard *wins* over the
   defensive `total_helper`. This was the axis's most useful move: an *earlier path-insensitive* link
   wired the argument unconditionally and rejected `guard_caller` (a conservative false positive);
   **synthesis surfaced that boundary, and the refinement productized it** — while `naive`, where None
   really crosses, stays rejected (the analyzer distinguishes a real cross-call bug from a
   safely-guarded call). Pinned productized in `tests/test_session.py`
   (`test_guarded_call_is_refined_across_the_boundary`).

**#8 is routed around, not blocked on.** Each function is emitted independently and brought together
only inside the `Session`, which namespaces identity — so no shared *synthesis* graph is built and
the name-split-join footgun (`../../ugm/docs/feedback_from_pystrider.md` #8a) never bites. It is a
*productization* prerequisite for a single shared synthesis graph, exactly as the analysis side
proved for a multi-function analysis graph (banks + namespaces).

> **Update (2026-07-13): the path-sensitive cross-call refinement is now productized.** `intake` tags
> a call created inside an `if VAR is not None:` body with `within_guard`; `Session.link_calls` stamps
> `refine_nonnull yes` on a link whose passed argument is that guarded var; and one new semantics rule
> (2e, the assign-shaped mirror of the refined frame 2c) carries only the non-None value across the
> boundary while a NAC on the plain ASSIGN rule (2) hands refined links to it. The full analysis suite
> stays green (no intra-procedural regression — the tag/rule only bind on a guarded cross-call link).

**Still open:** synthesizing the *call graph* shape itself (how many helpers, which delegates to
which) rather than choosing among fixed compositions — **now probed, below**; a guard that tests
something *other* than the passed argument (the refinement credits only `if arg is not None:`
directly); and loops.

---

## Follow-up: synthesizing the call-graph SHAPE (how a computation is factored) — feasible

Probe: `experiments/callgraph_synthesis.py`, pinned by `tests/test_callgraph_synthesis.py` (10 tests).
Question (the frontier after fixed compositions, and the one `codegen_understand.md` posed at the
outset — *"where and when do we decide whether to put statements in a subfunction vs a sequence?"*):
can the program's **shape** — how many functions and the call edges among them — be the synthesis
decision? **Verdict: yes, driven by checkable requirements and verified by re-execution + structural
inspection of the emitted graph.**

**Task:** `report(x)` needs two figures that both consume a shared sub-computation `normalize(x)`.
Three pre-minted SHAPES realize the *same behaviour* but differ in call-graph structure: `inline_dup`
(one function, `normalize` inlined twice), `helper_twice` (a `normalize` helper called at two sites),
`helper_once` (extract AND bind the result, one call site). Because all three compute the same figure
(pinned by execution), the choice is purely about **structure** — the point of the probe. Two spec
requirements progressively FORCE more structure, the mirror of the earlier strict/readable flips but
now over the call graph:

- lenient → `inline_dup` (most compact — fewest functions, 0 call edges);
- `dry_source` (no duplicated logic) → excludes the monolith; `helper_twice` wins (`normalize` node,
  in-degree 2);
- `dry_runtime` (compute `normalize` once) → only `helper_once` realizes — the winner flips again to
  the shape that reuses the shared *result* (in-degree 1 + a binding).

**The epistemic move is intact and is the honest part.** A shape only *claims* `provides factored /
single_eval`; verification **re-parses the emitted program** and DERIVES those properties from the
actual AST (is `normalize` a function? how many call sites?), then checks the winner's real structure
meets the spec's required features — trust by inspection of the artifact, never by the claim (pinned:
each shape's declared `provides` equals the AST-derived features). And every candidate is **run** and
must return the same figure, so the shape choice never changes meaning. Invariants hold: the emit tool
pre-mints the shape templates and the refinement rules only *select* (realizes iff misses nothing, as
`codegen_understand`). **Still open:** the shapes are pre-minted for one fixed computation —
synthesizing the shape over an *arbitrary dependency DAG* is the real generalization; and letting
guard placement (the cross-call refinement) interact with the chosen shape for None-totality.

---

## Productized (2026-07-13): a synthesis selection surface, and honest "clean" — answering the critique

Two of `docs/critique.md`'s load-bearing asks were productized (not probed):

- **Surface UNKNOWN (weakness #5 — "don't build on silence").** Intake now emits a visible
  `not_modelled` marker for every statement kind it cannot thread; `analysis.caveats(intake)` surfaces
  them; `RepairPlan.caveats` / `.fully_modelled` and `emit.verify_clean` qualify the verdict, so
  `repair_all` reports *"repaired to clean (modulo N unmodelled statement(s))"* and "clean" no longer
  means "nothing derived". Pinned in `tests/test_caveats.py`.

- **Productize the synthesis selection loop (weakness #8 — the probe pile).** `pystrider/emit.py` (+
  `emit.cnl`, the realization bank as data) lifts the shared realize-iff-provides-all + CHOOSE +
  provenance loop the probes re-implemented into the package — `emit.select(spec, required, candidates)`
  / `emit.verify_clean`. Built the ugm-vision-aligned way (`load_fact_triples` interns by name — no
  hand-rolled `ids` cache). `callgraph_synthesis` was refactored onto it (its `_graph`/`retrieve`/
  `choose`/realization-rules deleted); pinned in `tests/test_emit.py`. Remaining (per the critique):
  an end-to-end spec→source *entry point*, and migrating the other probes onto the surface.

> **Note (2026-07-13):** ugm feedback #2 (existential minting) was RESOLVED upstream — genuine
> per-match minting now works via the bound-literal skolem `<foo>?`. It does not change these probes
> (they mint in the §8 tool, demand-driven, for stable names + fuel + verify), but it opens a future
> option: rules could *grow* the candidate pool via skolem successors instead of the tool
> pre-minting it. Worth a dedicated probe to compare, not a change to the axis as built. **Done
> below** ("rule-grown vs tool-minted").

---

## Follow-up: rule-grown vs tool-minted candidate pools — an informed choice, now that #2 is resolved

Probe: `experiments/minting_comparison.py`, pinned by `tests/test_minting_comparison.py` (6 tests).
Question (reopened by ugm #2's resolution): every synthesis probe pre-mints its pool in the §8 tool
because rules *couldn't* mint — now they can (skolem `n?`). **So should the pool be grown by rules?
Verdict: for synthesis, keep tool-minting — but now by reason, not by force.**

The task is the canonical case that *drove* #2: generate a chain of `k` successor slots and emit a
depth-`k` value-threading function (`v0 = x; v1 = v0 + 1; … ; return vk`). Built **both** ways; both
emit **byte-identical** source and both **verify by execution** (`chain(0) == k`) — interchangeable
as generators. The difference is in four dimensions that matter for synthesis:

1. **#2's fix is real and retires the state-threading workaround for reasoning.** A one-line skolem
   rule (`?p has_next n? …`, the successor `is_a slot` so it recurses) grows the chain generatively
   under `run_bank` — the exact "mint a successor" case that used to force intake to pre-materialize
   the state lattice.

2. **But minting moves the cost from *enumerating* the pool to *re-addressing* it.** The rule-minted
   nodes are name-**collided** (all named `n`; identity is the anchoring relation), so every emit /
   verify / recognize step must thread **by node id**, and the demand-path goal API is name-addressed
   — you cannot ask for "the successor of THIS slot" by name (ugm #8c). Synthesis, which must
   name-emit and name-verify, pays exactly that tax. **#2 (minting) is only as useful for synthesis as
   #8 (addressing) is answered** — the two feedbacks are coupled. (Pinned: `nodes_named("slot_3")` is
   1 node for the tool pool, but `nodes_named("n")` is `k` for the rule pool.)

3. **Minting is not self-limiting.** The skolem's idempotent convergence bounds *re-asks of the same
   goal*, not the depth of generative growth; `max_rounds` (forward) or the tool's pool size supplies
   the real budget. #2's fix does **not** retire the fuel discipline — "agent, not theorem prover"
   still lives outside the rule, exactly where the tool-minted pool size already put it.

4. **Net — an informed choice.** Rule-minting is right for open-ended structure the rules must reason
   over *in place* (state threading, graph growth). Tool-minting is right for synthesis *targets* you
   must emit, name, and verify. The constraint that shaped the whole axis is gone, and the design
   choice it forced turns out to be the right one for this use anyway. **Still open:** an id-addressed
   emit/verify path would let synthesis use rule-grown pools without the naming tax — i.e. this
   probe's conclusion flips only when ugm #8 (id-addressed goals + stable skolem labels) lands.

---

## Follow-up: benchmarked the Session path (critique rec #3) — and killed a 65% self-inflicted cost

Critique.md's top undone recommendation (#3, "benchmark the Session path") and the empirical test of
whether ugm's `seed_from_focus` (feedback #7, adopted in `analysis.py`/`session.py`) actually helps us.
Probe: `experiments/session_benchmark.py` (scoped vs. global focus, one variable — attention-scope
size — driven through the identical productized `analyze(kb=shared, focus_scope=…)` path as a Session
accretes N namespaced functions), pinned by `tests/test_semantics_cache.py` (4).

1. **The measured "wall" was mostly redundant work, not engine cost.** `build_rule_graph`/`rule_list`
   re-ran `load_machine_rules(SEMANTICS)` on EVERY detect (7× per `repair_all`), and that call
   *validates the bank by running it* (`machine_rule_defects`) — so it was ~65% of every `analyze`.
   The bank is static, so `semantics.py` now parses it ONCE and memoizes (`_parsed_rules`), still
   assembling a FRESH rule graph per call (no shared graph-state hazard). Measured, 138/138 green:
   **`repair_all` 8220ms → 213ms (~39×), per-`analyze` 1372ms → 497ms (~2.8×), suite 376s → 31s (~12×)**.

2. **`seed_from_focus` is load-bearing — provably, once the constant was gone.** With the masking
   validation cost removed, scoped focus stays ~flat (**×1.67** as the graph grows ×7.95) while global
   goes **super-linear (×13.22)** — the flat-vs-superlinear curve the ISA-control-machine doc §7.4/§8
   claims, now reproduced on *our* facts. The scope→cost link is direct: per-analysis cost tracks the
   function under analysis, not the accreted session. The answer to "does it benefit us?" is emphatically
   yes, and increasingly so as a Session grows.

3. **The remaining lever is ugm's per-triple Python constant** (§7 "Rust for the constant") — an engine
   property, not ours. Fed back below.

4. **The perf headroom paid for a correctness fix.** With verification now cheap, the repair path was
   hardened (critique #6 residuals a+c): `choose_repair`/`candidate_edits` verify via `analyze_all`
   (every effect, not just the target's) and both regression checks compare a stable outcome key
   `(kind, base_var, label)` — stable across the re-intake that renumbers `site` ids — instead of the
   bare label. A return-None fix can no longer hide a still-broken deref. Pinned in
   `tests/test_repair_verification.py`. The perf lever and the correctness lever compose: (1) enabled (4).

---

## Follow-up: conformance strider — proving code implements a POLICY (the critique's top-rated direction)

Probe: `experiments/conformance_strider.py`, pinned by `tests/test_conformance_strider.py` (6). The
critique's §"The unification play" calls this "the strongest version of the whole project": a CNL
business POLICY and the CODE's decision logic co-resident in one graph, joined by a **derivable
`diverges` relation**, swept over scenarios the policy itself generates — a machine-checkable answer
to *"does this code implement this policy?"* that neither pyright, CodeQL, a DMN validator, nor an LLM
produces.

1. **The loop closes.** A planted boundary bug (code `total > 100` where the policy says `over 50`) is
   found as `diverges` on **exactly** the gold scenarios with total in (50, 100] — verified against a
   plain-Python oracle (`test_...match_the_python_oracle`). `diverges` is an ordinary derived fact
   (`?sc diverges yes when ?sc policy_outcome ?x and ?sc code_outcome ?y and not ?x same_outcome ?y`),
   so the spec-vs-code comparison is a JOIN, not imperative glue — queryable and explainable.

2. **One trace spans both worlds.** The `why {sid} diverges` proof interleaves the business-rule
   firing (`policy_hit` ← `over_policy` + `has_tier gold`) and the code-logic firing (`code_outcome
   deny`) from one provenance journal — the artifact the critique says a developer, auditor, and LLM
   each need and no tool emits.

3. **Repair is spec-DIRECTED and proven by re-sweep.** `align_threshold` reads the POLICY constant and
   rewrites the CODE constant (a real edit — the threshold is DATA in the model); re-sweeping the same
   scenarios yields **zero** divergence, CHOSEN over a decoy edit that fails verification. Semantics
   preservation ("code's outcomes == policy's on every swept scenario") is the verification condition
   by construction — the root-level answer to weakness #6 the critique predicted.

4. **The design's cost, paid the cheap way.** ugm's §8 "comparison-as-calculator" boundary keeps the
   arithmetic in a Python calculator (each swept scenario is fully ground — deterministic interpretation,
   no path explosion) while the LOGIC (AND, branch outcome, the judge) stays in rules. The sweep is the
   **hypothesis generator** (policy vocabulary × boundary constants), dissolving weakness #2 for this
   domain. Deliberate edge (per the critique's "what it costs"): the code is REIFIED directly, not
   intaken from Python text — growing `intake.py` with constants + comparisons is the separate,
   named cost; this probe answers the conformance-LOOP question, and the threshold-as-data makes the
   repair loop real even with a hand-reified body.

## ugm issues found

Nine bugs / limitations / surprises hit while building this are written up with minimal repros in
[`../../ugm/docs/feedback_from_pystrider.md`](../../ugm/docs/feedback_from_pystrider.md) — most
are **silent-failure** modes (mis-parsed rule clauses, undropped facts, case-folded queries,
un-minted existentials); the latest (#9) is a **hidden cost** — `load_machine_rules` re-validates the
bank by running it on every call (~65% of every `analyze` until we memoized the parse). None blocked
the spike, but a strict/verbose mode and a load-without-revalidate path would have saved most of the
debugging and runtime.

---

## Reproduce

```bash
pip install -e ../ugm -e .      # ugm sibling + this spike
python -m pystrider.demo        # the five-step walkthrough
pytest -q                       # the behaviour pins
```
