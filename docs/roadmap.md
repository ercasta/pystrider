# Roadmap — from research vehicle to useful tool

*Written 2026-07-14, against the working tree at that date (generator front-end landed; all five
grammapy convergence phases done; 254 tests green). Revised the same day after review: the
pure-derivational generation mode — succinct CNL spec expanded by KB rules into a detailed spec and
then into code, no LLM at runtime — was promoted from an implicit part of Phase 4 to the first
wedge, and the fragment library became a first-class kind of KB. This is the strategic layer: which
product the stack should become and in what order to build it. The tactical layer (what to build
next session) stays in `implementation_plan.md`; the critical assessment that motivates these
choices is `critique.md`.*

**Standing assumption** (the premise this roadmap is conditioned on): appropriate knowledge bases
exist in CNL — some *extracted* mechanically from library surfaces (type stubs, API declarations),
some *one-time authored* by LLMs from prose and then validated, and some *authored as fragment
libraries* (the code-level building blocks generation composes). Phase 2 is where that assumption
is made real; everything after consumes it.

---

## Positioning: what this is, and what it is not

**The tool is a compiler from CNL specs to code, where the KB is the instruction set — plus the
conformance layer that checks code (generated or foreign) against those same specs.** The central
identity, stated honestly:

> **Generation breadth equals KB coverage.** The rules select, expand, and compose; they do not
> invent. Every emitted line traces to a fragment, recipe, or scaffold the KB supplies — which is
> exactly why every emitted line carries a derivation.

So: do not position it as a *general-purpose* code generator — that category invites a
head-to-head with LLM assistants on "write me any Python," which loses on breadth. And do not
position it as a generic bug-finder — pyright and LLMs own that field. Position it where the
KB-coverage identity is a strength, not a ceiling:

- *Generating:* a succinct CNL spec + a domain KB derive the detailed spec (obligations fire,
  bridges admit realizations, defaults apply unless overridden, §12 resolves the cross-cutting
  decisions) and then the code — deterministically, with a proof bundle
  (demonstrated by the playground: reason → compose → emit → drive).
- *Checking:* a machine-checkable proof that a piece of code implements a piece of policy — and a
  verified minimal edit when it doesn't (`conformance_strider`, built).

The economics that make "KB as instruction set" a feature rather than a tax: **many instances per
KB** (a bank's 200 decision services, an insurer's product family, a fleet of workflow apps — one
KB, N programs); **specs that change often** (a policy change re-derives the code, and the diff
comes with a derivation of what changed and why); **correctness that is priced** (regulated and
high-stakes decision logic, where "why does this code exist" must have an auditable answer). A
point in generation's favor that is easy to undervalue: most enterprise code is not novel
algorithms — it is orchestration of known operations plus policy-shaped decisions, and both are
KB-expressible (the decisions via policy rules, the operations via absorbed API facts). The
residue — a genuinely novel algorithm inside a fragment — is rare, and is exactly where the
LLM-fills-a-declared-hole mode (Phase 5) or a human plugs in.

**The generation ladder** (each mode adds variance the previous mode's gates must already absorb):

1. **Mode 1 — pure derivation.** No LLM at runtime. The spec expands by KB rules; emission
   composes KB fragments; every step is a derivation. What the KB doesn't cover is *refused and
   named*, never improvised. — Phase 3, the first wedge.
2. **Mode 2 — declared holes.** The KB names the holes (an atom body, an expression); an LLM
   fills them; each fill is gated individually (footprint honesty by execution, drive oracle).
   — Phase 5.
3. **Mode 3 — free drafting.** An LLM drafts the whole design; the gates dispose
   (an untrusted proposer behind trusted disposers). — Phase 5.

**Held lines (throughout, non-negotiable):**

1. **No heap modeling, no whole-repo ambitions.** The checkable/generatable subset is scoped *by
   product definition* — decision kernels and KB-composed orchestrations — so the heap wall is
   avoided on purpose, never hit. This is the framework-saver, not a limitation to apologize for.
2. **Every verdict-producing surface ships with its contract stated** — what a passing check
   *proves* and what it silently does not. The project's moral claim is auditability; the
   generator-front-end verification (2026-07-14: a safety-only drive oracle shipped a dead app as
   "trustworthy") showed how quietly that claim erodes otherwise.
3. **Refusal is a feature.** An uncovered spec region surfaces as a *named gap* with the shape of
   the KB entry that would fill it — "forced where unique, declared where preferred, surfaced
   where ambiguous, never inferred" applies to generation as a whole, not just §12.
4. **Effects grow only where provenance matters** — semantic/temporal contracts the type checkers
   cannot express — never in competition with what pyright does for free.

---

## Phase 0 — Harden the trust core *(weeks; do first)*

The entire pitch is "every step is a trusted derivation or a trusted check." The disposers must be
beyond reproach before anything is built on them. An early finding: a drive oracle that is safety-only
(`ok = ¬irreversible ∨ ¬performed ∨ gated`) certifies a dead app as "trustworthy" unless liveness is a
separate, stated contract.

**Work:**
- State each oracle's contract in `docs/` — which trace properties a passing drive proves, which
  it does not. (Critique recommendation #6; also covers naming the diagnosis axis, which today
  exists only as a probe docstring.)
- Add **liveness** to the drive oracle: the happy path must *complete*, not merely never violate
  the gate ordering. The no-affirmative-button draft (`("cancel", "back")`) is the ready-made pin.
- **Gate the emitted artifact, not the draft**: the composition check must attach to the button
  set that ships (`_emit_spec`'s `draft.buttons or None` substitution is the hole).
- Close repair residual (b) from the critique: verify repairs under a **swept hypothesis space**,
  not one seeded dict — the conformance sweep machinery already shows the shape.

**Exit criteria:** a draft that passes every gate demonstrably works end-to-end (safety *and*
liveness pins); every oracle has a written contract; no gate certifies an artifact other than the
one emitted; `repair_all` verifies under a sweep.

---

## Phase 1 — The performance floor *(parallel to everything; mostly upstream in ugm)*

Per-candidate gating and per-derivation expansion are the product's hot loop, and a CNL check
currently costs ~1150× the Python check it replaced (ugm feedback #13), with the per-triple
pure-Python fold under everything. Interactive and CI use are impossible at that constant; nothing
downstream ships without this, which is why it runs in parallel rather than after. Mode-1
generation raises the stakes: deep spec expansion is *made of* derivations, so the constant
multiplies against KB depth, not just candidate count.

**Work:**
- The ugm per-triple constant: a compiled core, or at minimum a load-without-revalidate +
  interned fast path for rule banks (the downstream memoization already proved how much of the
  cost was avoidable).
- Eventually: incremental intake — an edit re-derives only the affected region, instead of full
  re-intake per candidate.

**Exit criteria (concrete targets):** a gate check in single-digit milliseconds; an `analyze` of
the README example under 100ms; a full spec expansion + emission for the withdrawal app under a
second. Measured by extending `experiments/session_benchmark.py`, which is already the honest
measuring device.

---

## Phase 2 — The KB pipeline *(the standing assumption, made real — and the moat)*

Three tracks. The key design decision: **the gating pattern applies recursively to the knowledge
itself** — an unreliable producer of KBs is acceptable for exactly the same reason an unreliable
generator of code is.

**Track A — extracted KBs.** Productize `absorb(module)`
(`api_absorption` slices 3–4, designed in `api_absorption_design.md`): type stubs and API surfaces
→ versioned, regenerable fact banks per library. Prioritize the facts stubs *cannot* express —
ordering contracts ("commit after begin"), resource lifecycles ("close what you open"),
value-conditional behavior ("returns None on missing key but raises on type error") — because
facts typeshed already carries are pyright's territory (held line #4). These are also generation's
operation vocabulary: mode-1 emission composes calls to absorbed APIs, so every absorbed fact
widens what can be generated, not just what can be checked.

**Track B — authored KBs (policies and domain rules).** An LLM drafts CNL policy from prose
documents; it lands only through a validation gate. **This is where rulestrider stops being a side
spike and becomes product-critical**: the anomaly checks the critique designed (contradiction
pairs, dead/shadowed rules, coverage gaps swept over the declared vocabulary, behavioral
subsumption) become the *ingestion gate* for LLM-written knowledge. A KB that survives the anomaly
checker plus human review is trustworthy by the same argument the codegen loop uses. Build
rulestrider here, as KB QA — not later, as a demo.

**Track C — the fragment library (new; generation's instruction set).** Today the code-level
building blocks — atoms, recipes, scaffolds — are Python objects with declared footprints, living
in probe modules. Make them **shippable data**:
- A KB representation for fragments: CNL facts naming each fragment, its `provides`, its declared
  footprint, and its holes; bodies stored as AST/source. (grammapy's footprint declarations are the
  soundness metadata; `pystrider.footprint_of` derives the footprint from the fragment's own code.)
- **Spec intake in CNL**: retire the `Spec` dataclass as the public face — the conformance side
  already takes policy as CNL facts, and the generation spec must enter the same way, so "succinct
  spec" means a few CNL sentences, not a Python constructor call.
- Fragment honesty at ingestion: `footprint_honesty`'s execution check runs when a fragment enters
  the KB, not just at composition time — the same recursive-gating move as Track B.

**Also here:** grow the effect table with what the KBs unlock — `method_not_found` (from
`has_method`), invalid-enum-value, lifecycle violations. Each new effect rides on absorbed facts
plus the existing generic rules, which `api_absorption` proved is the cheap path. And build the
**rule-authoring harness** (the critique's long-standing ask): Tracks B and C both die at scale
without a way to test a rule bank in isolation.

**Exit criteria:** one real library absorbed end-to-end with its fact bank checked in and
regenerable; one real policy document LLM-drafted into CNL and admitted through the rulestrider
gate; the withdrawal app's atoms/scaffold re-expressed as a shippable fragment KB (engine code
untouched); a spec written as CNL sentences drives the existing loop.

---

## Phase 3 — The generation wedge: mode 1, pure derivational spec→code

The first wedge, and the direct continuation of what just landed: the grammapy convergence closed
the loop reason → compose → emit → drive, and the playground already demonstrates the two-stage
expansion (a KB → derived features → a runnable, driven app). This phase turns that demo into
the product. No LLM at runtime: expansion is derivation, emission is composition, and the output
carries the proof bundle end to end. This ordering is deliberate — mode 1 is the *lowest-variance*
generation mode, so it exercises the KB pipeline and the gates with no untrusted proposer in the
loop at all.

**Work:**
- **Expansion as derivation, deepened.** Today's chains are shallow (one obligation, one bridge,
  one scaffold family). Grow the KB depth — more deontic rules, more bridges, more decision points
  — on the Phase 2 harness, and keep §12's discipline as the spine: forced where unique, declared
  where preferred, surfaced where ambiguous, never inferred.
- **Emission across scaffold families**, from the Track C fragment KB: a second app family
  generated *without touching engine code* is the proof that the fragment KB, not the probe, is
  doing the work.
- **The refusal UX** (held line #3): an uncovered spec region yields a named gap — "no fragment
  provides `X`; a KB entry of shape `Y` would fill it" — engineered as a good experience (the
  on-ramp to Track C authoring, and later the hole that mode 2 hands to an LLM), not a dead end.
- **The re-derivation diff:** change one spec sentence, re-derive, and present what changed in the
  code *with the derivation of why* — the "policy change → verified code change" artifact, which
  no LLM regeneration can produce.

**Deliverable — and the generation demo that makes the stack legible:** one domain family (e.g.
decision services from eligibility/pricing policies, or the workflow-app family the withdrawal app
belongs to), N instances generated from one KB, each with its proof bundle; then one policy
sentence changed, and the re-derived diff shown with its justification.

**Exit criteria:** a second family from KB-only authoring; a spec change re-derives with a
proof-diff; an uncovered spec refuses with a named gap, not a guess; someone other than the KB's
author writes a working spec in CNL unaided.

---

## Phase 4 — The conformance wedge: checking code against the same specs

The second wedge, sharing everything with the first: the same policy KBs, the same sweep
machinery, the same provenance. Two jobs: it is how **foreign code** (the code the tool did not
generate) enters the story, and it closes the honesty loop on generated code — mode-1 output can
be conformance-checked *as if foreign*, which is the strongest self-audit the stack can perform.
The bug class is "the code does not implement the policy" — the one class where this stack has no
incumbent.

**Work:**
- Wire `intake_growth` into `conformance_strider` (slice 1b, designed, unbuilt): check real Python
  decision functions — intaken from source text, constants and comparisons as data — against CNL
  policies, with the scenario sweep enumerated from the spec's declared vocabulary and boundary
  constants. Hypothesis supply is solved by construction here.
- Define and lint **"strider-checkable functions"** (held line #1): decision kernels over
  scalars/enums. The tool defines the discipline, like design-by-contract did, rather than chasing
  arbitrary Python.
- Spec-directed repair on divergence (the `align_threshold` shape, generalized), verified by
  re-sweep.

**Deliverable:** a CI gate. *"This PR's eligibility logic diverges from policy v3 on the
(gold, 50–100] band — here is the two-world trace (policy derivation interleaved with code
derivation), and here is the verified fix."*

**Exit criteria:** the CI gate runs on a repo not written for the tool, over functions matching
the checkable discipline; a planted boundary bug is found, traced, and repaired with the re-sweep
proof; a mode-1-generated artifact round-trips through the checker clean; a developer who has
never seen ugm can read the divergence trace unaided.

---

## Phase 5 — The generation ladder, rungs 2 and 3: LLMs enter the loop

Only now does an untrusted proposer join at runtime — after the gates are liveness-aware and
artifact-faithful (Phase 0), the KBs are validated (Phase 2), and the deterministic mode has
battle-tested the whole path (Phase 3). A real LLM makes mistakes nobody enumerated; everything
before this phase exists to make that survivable.

**Mode 2 — declared holes.** The refusal UX's named gaps become the LLM's work orders: it fills an
atom body or an expression the KB declares but does not supply. Each fill is gated individually —
footprint honesty by execution, then the composed drive. libcst becomes load-bearing here
(round-tripping user-owned fragment bodies), as the convergence plan already names.

**Mode 3 — free drafting.** A generator seam (`Generator = Callable[[Spec], Draft]`)
with a real model drafting whole deviation specs; gates dispose; repair back-edge on rejection.
The shipped artifact is **code plus its proof bundle**: derived obligations, composition
admission, drive trace — the differentiator over raw LLM output, packaged as such.

**Exit criteria:** an intent → app run where the LLM's first draft is *rejected by a gate the
scripted generators never triggered*, repaired, re-gated, and shipped with the bundle — the loop
earning its keep against a real adversary. Track the rejection taxonomy; it is the empirical
answer to "what do the gates actually buy."

---

## Phase 6 — One surface

Collapse the entry points into one CLI: `strider generate` (Phases 3/5), `strider check`
(Phase 4), `strider fix` (repair on either), `strider explain` (the why-trace, both worlds).
Render the proof object for humans — the why-trace is the *review artifact*, and its readability
is a feature with the same priority as correctness, because the audit trail is what the buyer is
paying for.

**Exit criteria:** a user who installs one package and writes zero ugm code can run all four verbs
against their repo, a spec, and a KB.

---

## Sequencing rationale, in one paragraph

Trust core first because it is the pitch (Phase 0); performance in parallel because it is the
floor everything stands on, and spec expansion multiplies the constant against KB depth (Phase 1);
the KB pipeline before either wedge because both consume it, the fragment library is generation's
instruction set, and the KBs are the moat (Phase 2); pure-derivational generation as the first
wedge because it is the direct continuation of the loop that just closed, the lowest-variance
generation mode, and the one product no one else can offer at all — deterministic spec→code with a
proof per line (Phase 3); conformance second because it shares the KBs, admits foreign code, and
closes the honesty loop by checking generated output as if foreign (Phase 4); the LLM rungs last
because they are the highest-variance components and everything before them exists to make their
unreliability survivable (Phase 5); one surface at the end so the loop is sellable rather than
assemblable (Phase 6).

## What would falsify this roadmap

Honest kill-criteria, in the project's own spirit:

- **Phase 1 fails** (the constant won't come down by orders of magnitude): the interactive product
  dies; the fallback is batch/CI-only positioning, which weakens but does not kill Phases 3–6.
- **Fragment granularity fails** (Phase 3: real domains need fragments so fine-grained or so
  instance-specific that KB authoring costs more than writing the code directly): the mode-1
  compiler bet was wrong for that domain — mode 2 becomes load-bearing earlier than planned, and
  the KB's value concentrates in the policy/constraint layer rather than the fragment layer.
- **Phase 2 Track B fails** (LLM-drafted CNL cannot pass the anomaly gate without hand-holding
  that costs more than writing the KB by hand): the standing assumption collapses and the tool's
  addressable scope shrinks to hand-authored KBs — still viable in regulated niches, but the moat
  thins.
- **Phase 4's discipline is rejected by users** (real decision logic won't factor into
  strider-checkable kernels): the scoping bet was wrong, and that must be learned from a design
  partner's codebase, not assumed — which is an argument for finding that partner during Phase 2,
  not after.
