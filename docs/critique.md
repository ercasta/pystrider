# A critique of pystrider (and the ugm engine under it)

*Written 2026-07-12, against the working tree at that date (49 tests green, including the
uncommitted path-refinement slice; README still says 44). Empirical checks: full suite runs in
~75s; a single `analyze` of the 4-line README example takes ~1.3s over 74 facts.*

---

## Verdict up front

The engineering discipline is unusually good, the intellectual honesty of the docs is rare, and
the loop that has been closed (hypothesize → derive → explain → repair → verify → choose) is a
real, coherent thing that few systems offer end-to-end. But the "dynamic, hypothesis-driven, not
static Datalog" framing is partly a story the system tells about itself: what has actually been
built — and this is not an insult — is a **demand-driven, flow-sensitive may-dataflow analysis
expressed in Datalog, with first-class provenance and a generate-and-validate repair loop**.
That is a known family. The genuinely novel part is not the analysis semantics; it is that the
*entire* loop, including repair retrieval and choice, runs on one auditable substrate where
every conclusion is a proof object. Whether the system is useful depends on building toward the
place where that property is the product.

---

## Strengths

**1. The provenance is real, and that is the crown jewel.** The trace in the README is not a
rendered narrative — it is the RECORD journal of actual rule firings (`ask_goal("why …")`).
Mainstream tools cannot do this: CodeQL gives a path, mypy gives an error string, an LLM gives
plausible prose. A derivation tree that a machine can re-check and a human can read is a
differentiated artifact.

**2. The spike methodology is exemplary.** `spike_findings.md` maps claims to evidence,
documents walls (existential heads are not Skolem-minted), records workarounds with their
design implications ("mint moves to intake"), and keeps negative results
(`experiments/state_threading.py` preserved as the probe). The boundary-guard test that pins
"intake emits no reasoning predicates" keeps the structure/behavior separation
machine-enforced — the kind of discipline that prevents slow architectural rot.

**3. The repair loop is architecturally right.** Retrieve operators by effect key via
backward-CHAIN, materialize as real AST rewrites, verify by re-intake and re-analysis, CHOOSE
graded-best with losers retained. "The edit is trusted because it clears on the actual
transformed code, not because the operator claims it will" is exactly the right trust model.

**4. The pre-materialized cell lattice discovery is a good constraint, honestly absorbed.**
Turning "rules can't mint states" into "the state pool *is* the fuel budget" unified two open
questions into one knob. That is the sign of a design listening to its implementation.

**5. Layer discipline.** pystrider genuinely owns no engine code; the CNL/tool/mechanism split
(the three-tier table in `code_reasoning_design.md`) is principled and consistently applied.
The seven-item feedback doc to ugm, with minimal repros, most already fixed, shows the two-repo
loop working.

---

## Weaknesses

**1. The "dynamic vs. static" distinction has quietly collapsed, and the docs haven't fully
caught up.** The design's central move was "the DFG dissolves — value flow is computed by
executing." But the state-threading wall forced intake to pre-materialize the entire
`(program-point × variable)` cell lattice, after which the rules are pure Datalog binding
pre-existing structure. At that point the hypothesis is just a seeded entry fact, and what runs
is flow-sensitive dataflow with magic-sets demand. The DFG did not dissolve; it got renamed to
"cells." The *driver* is demand-driven and the *UX* is hypothesis-shaped, and those are real
differences — but the semantics is classic abstract interpretation with bounded unrolling
instead of widening. The pitch should be reframed around what is actually distinctive
(provenance + the closed repair loop + demand-boundedness) rather than a static/dynamic
dichotomy the spike itself refuted.

**2. The hypothesis must be supplied, which means the bug must already be suspected.** Real
symbolic execution derives path conditions and *discovers* which inputs matter; here the caller
enumerates `{"raw": "none"}` by hand from a two-value domain. For None-analysis every param can
be brute-forced cheaply, so this is survivable today — but the system is a *hypothesis
checker*, not a *bug finder*, and the docs occasionally blur that line.

**3. The flagship effect is the one existing tools already solve.** `pyright --strict` catches
the README's None-deref instantly, at repo scale, on annotated code. The honest answer is that
pystrider targets *unannotated* code and adds the trace and the repair — but that positioning
should be explicit, because "finds None-derefs" invites a comparison it loses on coverage,
speed, and maturity.

**4. Performance is a wall being walked toward.** 1.3s for a 4-line function with 74 facts;
75s for 49 toy tests. The costs compound multiplicatively: the cell lattice is
O(states × vars), loop unrolling multiplies states, sessions multiply functions, and every
triple in ugm is a node plus two untyped edges matched by a pure-Python fold. Soufflé-class
engines compile Datalog to specialized C++ joins; this is perhaps four orders of magnitude
away. For "a few functions reasoned about deeply" this is fine *today*, but the
inter-procedural Session ambition and this cost curve are on a collision course. Benchmark
before building the next slice, not after.

**5. "Honest partiality" in intake is quieter than the docs suggest.** `stmt()` returns the
state unchanged for unsupported statements (`intake.py`). That is not just a missed check — a
skipped statement that reassigns a variable (via `x.attr = …`, tuple unpacking, `del`, or an
augmented assign) leaves the *stale* value framed forward, producing confidently wrong
derivations, not UNKNOWN ones. Same for `unknown_expr`: a deref of it silently derives nothing.
The design promises "UNKNOWN when fuel runs out" but no UNKNOWN is surfaced anywhere yet —
outcomes are either derived or absent, and absence conflates "proved safe," "not modelled," and
"fuel exhausted." This is the single most important semantic gap: the system's whole moral
claim is auditability, and unmodelled-as-silent undermines it.

**6. The repair verification contract is narrower than it reads.** Verification only checks
residual outcomes *under the same hypothesis and the same effect*. A guard insertion that
clears the AttributeError makes the function silently return None instead — which is literally
the Slice C effect, unchecked during a Slice A repair. And in the README example the *actual*
bug is the clobbering `data = raw` line; the winning repair wraps the deref and preserves the
clobber. No operator can express "delete the stray assignment," and CHOOSE can only pick among
what the template library can say. Cross-effect verification (a repair must not introduce any
known effect) would be cheap and would materially strengthen the trust story.

**7. `link_calls` is context-insensitive in the classic way.** Every call site writes into the
callee's single entry cell (`session.py`), so two callers' values merge and flow back out to
both — spurious cross-caller flows the moment a Session has two calls to the same function.
This is the oldest problem in inter-procedural analysis; it need not be solved now, but the
docs should register it as a known imprecision rather than presenting call-linking as done.

---

## Risks

- **The heap.** There is no aliasing, no attribute store, no container model — `none`/`object`
  values with no structure. Every analysis framework in history got hard exactly here, and most
  "interesting" Python bugs live in mutation-through-alias territory. Decide *deliberately*
  whether pystrider ever models the heap or permanently scopes to value-flow bugs; drifting
  into it incrementally is how frameworks die.
- **Semantics authoring at scale.** Real Python semantics (descriptors, `__getattr__`,
  exceptions, truthiness, dynamic dispatch) is enormous — the "Python: The Full Monty"
  formalization effort is a cautionary tale. Seven Horn rules cover the current subset; the
  curve from here is steep, and ugm's historically silent authoring failures (feedback #1, now
  fixed, but the class of risk remains) make a 200-rule semantics bank scary without a
  rule-testing harness.
- **Niche squeeze.** Above sit LLMs, which do the whole "reason like a human, explain, propose
  a fix" loop today with vast coverage and zero soundness; below sit pyright/CodeQL/Infer with
  maturity and scale. The defensible niche is the one neither occupies: **machine-checkable
  reasoning with provenance**. Concretely, the most promising future is pystrider as the
  *verification and grounding substrate for an LLM agent* — the LLM proposes hypotheses and
  repair operators (solving weakness #2 and the library-breadth problem), ugm checks them and
  returns proofs. That is a genuinely open lane.

---

## Literature positioning

- **Datalog-based program analysis** (Doop, Soufflé, CodeQL, bddbddb): the closest kin,
  whatever the docs say. Distinguishing features against them: demand-driven with honest
  fuel/UNKNOWN semantics (they saturate), first-class derivation provenance, and repair in the
  same substrate. Deficits: performance and language coverage by orders of magnitude.
- **Demand-driven dataflow** (Reps–Horwitz–Sagiv IFDS; Duesterwald's demand inter-procedural
  analysis): the `suppose` + `chain_sip` combination is essentially demand-driven dataflow with
  a query seeded at entry. IFDS's summary edges are the standard answer to the
  context-sensitivity problem in weakness #7.
- **Bounded model checking** (CBMC): loop unrolling with the bound as fuel is exactly BMC's
  move; they too are "honest bound, not fixpoint."
- **Symbolic execution** (KLEE, angr; Rosette for the solver-aided-DSL angle): shared
  vocabulary but not mechanism — no path conditions, no constraint solving. The planned
  SMT-as-CALL tool would move toward Rosette's territory.
- **Automated program repair**: the retrieve/materialize/verify/CHOOSE loop is template-based
  generate-and-validate (PAR, TBar lineage; SemFix/Angelix for the semantic branch). The
  preconditioned, effect-keyed operator retrieval is more principled than most template
  systems; the verification oracle (one hypothesis, one effect) is weaker than their test
  suites.
- **Means-ends analysis**: the operator library with preconditions and effects is
  straightforwardly STRIPS/GPS (Newell & Simon), which the design acknowledges. Fine lineage;
  the known risk is that operator libraries are forever incomplete.
- **Truth maintenance** (de Kleer's ATMS): SUPPOSE's pencil/ink scopes are assumption contexts;
  RECORD is a justification network. ugm has quietly rebuilt an ATMS with better ergonomics.

---

## On ugm itself

ugm is the more interesting of the two artifacts, and also the bigger gamble.

**What is genuinely good.** The "everything is a node, edges are typeless" commitment is held
with impressive consistency, and it buys real things — homoiconic rules, RECORD woven through
every mode for free, SUPPOSE without possible-worlds machinery. The nine-mode inventory is a
tasteful cognitive-architecture take (it reads like SOAR/ACT-R distilled through Datalog rather
than production-rule chaos, and it is a cleaner design than OpenCog's AtomSpace, its nearest
structural relative). Keeping the logic fragment small and formally anchored — definite Horn +
stratified demand-driven NAF + defeasibility + grades — instead of chasing expressiveness is
the mark of a designer who has read the failure modes. The fuel/UNKNOWN honesty ("a truncated
closure means the absence read is not trustworthy," `chain.py`) is exactly right and rarer than
it should be. And the responsiveness to pystrider's feedback — five of seven items fixed with
tests — shows the two-repo loop working.

**What is worrying.** Three things. First, *the substrate purity has a permanent price*:
relation-as-node means every fact is 3 nodes / 2 edges and every join is a pure-Python state
fold. "No seams" is philosophically beautiful, but Soufflé's seams (compiled relations, B-tree
joins) are why it is fast, and there is no obvious path to competitive performance that does
not compromise the one-substrate identity. Decide early whether ugm's ambition is *correct and
explicable at session scale* (defensible) or *a real analysis engine* (probably unreachable in
pure Python on this representation). Second, the engine's historical failure mode is *silence*
— misparse silently, drop facts silently, collapse existentials silently. The recent
strict-mode fixes are the right direction, but the underlying culture ("quietly do less") needs
to invert to "loudly refuse" everywhere, because consumers author rules programmatically.
Third, the missing existential heads are not a small gap: value invention is the difference
between Datalog and Datalog±/the chase, and "pre-materialize the pool in a tool" works only
when a tool can statically know the pool. pystrider got lucky (CFGs are static); the next
consumer may not.

---

## What to do next, in order

1. **Surface UNKNOWN.** Make unmodelled statements, unknown expressions, and fuel exhaustion
   produce a visible verdict, not silence. Cheap, and it protects the system's core claim.
2. **Cross-effect repair verification.** A repair must clear its outcome without introducing
   any other known effect. Both analyzers exist; it is a loop.
3. **Benchmark the Session path** before widening it — cell-lattice size vs. analyze time on a
   realistic 10-function working set. If the curve is bad, that is an ugm conversation to have
   now.
4. **Prototype the LLM-in-the-loop experiment**: an LLM proposes hypotheses and operators,
   pystrider verifies with provenance. If that works even crudely, it is the demo that makes
   the whole stack legible to the outside world — and it is the niche neither pyright nor an
   LLM alone can occupy.

**Is it useful?** As a bug-finder competing with typed tooling: no, and it probably never wins
that race. As a research vehicle it is already earning its keep (the state-minting finding
alone is a real result about rule-engine expressiveness). As a substrate for *auditable machine
reasoning about code* — where every conclusion and every proposed fix carries a checkable proof
— it is the most promising small system of its kind, and that lane has growing demand.

---

## A second domain: detecting and fixing bugs in CNL business rules

*(Added in response to: "what about using the tools to detect and fix semantics bugs, where
semantics is business rules expressed in CNL?")*

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
passing cases (fixing weakness #6's single-hypothesis/single-effect gap). CHOOSE then picks the
minimal edit that clears the failures without breaking any passing scenario — with the losers
retained and the whole selection auditable, which in a compliance setting is itself a feature.

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

---

## The unification play: spec and implementation on one substrate

*(The intended question, clarified: not "analyze rulebases instead of Python" but "put the CNL
business rules AND the Python code's semantics in the same graph and reason across them." The
rulebase-debugging section above is a component of this; what follows is the composed system.)*

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
  align the code's threshold (100) to it. This answers the critique's weakness #6 at the root:
  the repair target is no longer "make this one outcome disappear" but "make the code's
  derived outcomes equal the spec's on every swept scenario" — semantics preservation is the
  verification condition by construction.
- **Scenario generation comes from the spec.** The declared finite vocabulary plus the spec's
  own constants (boundary values: 49/50/51) enumerate the sweep. This dissolves the critique's
  weakness #2 (hypothesis-must-be-supplied): the spec is the hypothesis generator.
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
