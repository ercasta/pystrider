# Roadmap — from research vehicle to useful tool

*Written 2026-07-14, against the working tree at that date (generator front-end landed; all five
grammapy convergence phases done; 254 tests green). This is the strategic layer: which product the
stack should become and in what order to build it. The tactical layer (what to build next session)
stays in `implementation_plan.md`; the critical assessment that motivates these choices is
`critique.md`.*

**Standing assumption** (the premise this roadmap is conditioned on): appropriate knowledge bases
exist in CNL — some *extracted* mechanically from library surfaces (type stubs, API declarations),
some *one-time authored* by LLMs from prose and then validated. Phase 2 is where that assumption is
made real; everything after consumes it.

---

## Positioning: what this is, and what it is not

**Do not position it as a bug-finder or a code generator.** Both markets are owned: pyright +
typeshed already know `dict.get` returns `Optional`; LLMs already fix null derefs and write real
code from real specs, with vast breadth and zero proofs. Competing there loses on breadth and
speed, and the critique has said so since the first version.

**Position it as the conformance and trust layer for decision logic** — with bugfixing and
generation as the two entry points into the same loop:

- *Checking:* a machine-checkable proof that a piece of code implements a piece of policy — and a
  verified minimal edit when it doesn't (`conformance_strider`, built).
- *Generating:* code produced by an untrusted drafter but shipped only through trusted gates —
  derived obligations, composition algebra, execution oracle — with the proof bundle attached
  (`generator_frontend`, built).

The buyer this converges on is whoever runs regulated or high-stakes decision logic — eligibility,
pricing, claims, limits — where "the code matches the policy, provably, with an audit trail" is
something people already pay for and currently assemble by hand.

**Held lines (throughout, non-negotiable):**

1. **No heap modeling, no whole-repo ambitions.** The checkable subset is scoped *by product
   definition* — decision-kernel functions over scalars/enums ("strider-checkable functions",
   Phase 3) — so the heap wall is avoided on purpose, never hit. This is the framework-saver, not
   a limitation to apologize for.
2. **Every verdict-producing surface ships with its contract stated** — what a passing check
   *proves* and what it silently does not. The project's moral claim is auditability; the
   generator-front-end verification (2026-07-14: a safety-only drive oracle shipped a dead app as
   "trustworthy") showed how quietly that claim erodes otherwise.
3. **Effects grow only where provenance matters** — semantic/temporal contracts the type checkers
   cannot express — never in competition with what pyright does for free.

---

## Phase 0 — Harden the trust core *(weeks; do first)*

The entire pitch is "untrusted proposer, trusted disposer." The disposers must be beyond reproach
before anything is built on them, and today they are not: the verification of the generator
front-end found the Pilot oracle is safety-only (`ok = ¬irreversible ∨ ¬performed ∨ gated`,
`app_synthesis.py`), GATE 4 is currently unreachable-as-rejector, and Accumulate certifies the
*drafted* button set while emission ships a *different* one.

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

Per-candidate gating is the product's hot loop, and it currently costs ~1150× the Python check it
replaced (ugm feedback #13), with the per-triple pure-Python fold under everything. Interactive
and CI use are impossible at that constant; nothing downstream ships without this, which is why it
runs in parallel rather than after.

**Work:**
- The ugm per-triple constant: a compiled core, or at minimum a load-without-revalidate +
  interned fast path for rule banks (the downstream memoization already proved how much of the
  cost was avoidable).
- Eventually: incremental intake — an edit re-derives only the affected region, instead of full
  re-intake per candidate.

**Exit criteria (concrete targets):** a gate check in single-digit milliseconds; an `analyze` of
the README example under 100ms; a full repair loop under a second. Measured by extending
`experiments/session_benchmark.py`, which is already the honest measuring device.

---

## Phase 2 — The KB pipeline *(the standing assumption, made real — and the moat)*

Two tracks. The key design decision: **the gating pattern applies recursively to the knowledge
itself** — an unreliable producer of KBs is acceptable for exactly the same reason an unreliable
generator of code is.

**Track A — extracted KBs.** Productize `absorb(module)`
(`api_absorption` slices 3–4, designed in `api_absorption_design.md`): type stubs and API surfaces
→ versioned, regenerable fact banks per library. Prioritize the facts stubs *cannot* express —
ordering contracts ("commit after begin"), resource lifecycles ("close what you open"),
value-conditional behavior ("returns None on missing key but raises on type error") — because
facts typeshed already carries are pyright's territory (held line #3).

**Track B — authored KBs.** An LLM drafts CNL policy from prose documents; it lands only through a
validation gate. **This is where rulestrider stops being a side spike and becomes
product-critical**: the anomaly checks the critique designed (contradiction pairs, dead/shadowed
rules, coverage gaps swept over the declared vocabulary, behavioral subsumption) become the
*ingestion gate* for LLM-written knowledge. A KB that survives the anomaly checker plus human
review is trustworthy by the same argument the codegen loop uses. Build rulestrider here, as KB
QA — not later, as a demo.

**Also here:** grow the effect table with what the KBs unlock — `method_not_found` (from
`has_method`), invalid-enum-value, lifecycle violations. Each new effect rides on absorbed facts
plus the existing generic rules, which `api_absorption` proved is the cheap path.

**Exit criteria:** one real library absorbed end-to-end with its fact bank checked in and
regenerable; one real policy document LLM-drafted into CNL and admitted through the rulestrider
gate; at least two non-None effects live on the absorbed facts.

---

## Phase 3 — The bugfixing wedge: conformance on foreign code

The easier adoption ask of the two wedges (you check their code; you don't write it), and it
battle-tests the Phase 2 KBs before generation depends on them. The bug class is "the code does
not implement the policy" — the one class where this stack has no incumbent.

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

**Deliverable — and the demo that makes the stack legible:** a CI gate.
*"This PR's eligibility logic diverges from policy v3 on the (gold, 50–100] band — here is the
two-world trace (policy derivation interleaved with code derivation), and here is the verified
fix."* That artifact is the product.

**Exit criteria:** the CI gate runs on a repo not written for the tool, over functions matching
the checkable discipline; a planted boundary bug is found, traced, and repaired with the re-sweep
proof; a developer who has never seen ugm can read the divergence trace unaided.

---

## Phase 4 — The codegen wedge: a real LLM in the generator seam

The seam exists as of 2026-07-14 (`Generator = Callable[[Spec], Draft]` in `generator_frontend`);
the scripted generators validated the gating contract. This phase comes *after* Phase 3
deliberately: generation inherits its trustworthiness from the same KBs and oracles the
conformance wedge will have battle-tested — and a real LLM makes mistakes nobody enumerated, which
is exactly why the gates must already be liveness-aware and artifact-faithful (Phase 0) before it
arrives.

**Work:**
- A real model drafting deviation specs and atom bodies from intent + the Phase 2 policy KBs;
  gates dispose (obligation → Scope → Accumulate → drive); repair back-edge on rejection.
- libcst becomes load-bearing here (round-tripping user-owned atom bodies), as the convergence
  plan already names.
- The shipped artifact is **code plus its proof bundle**: derived obligations, composition
  admission, drive trace. The bundle is the differentiator over raw LLM output — package it as
  such.

**Exit criteria:** an intent → app run where the LLM's first draft is *rejected by a gate the
scripted generators never triggered*, repaired, re-gated, and shipped with the bundle — i.e. the
loop earns its keep against a real adversary, not a scripted one. Track the rejection taxonomy;
it is the empirical answer to "what do the gates actually buy."

---

## Phase 5 — One surface

Collapse the entry points into one CLI: `strider check` (Phase 3), `strider generate` (Phase 4),
`strider fix` (repair on either), `strider explain` (the why-trace, both worlds). Render the proof
object for humans — the why-trace is the *review artifact*, and its readability is a feature with
the same priority as correctness, because the audit trail is what the buyer is paying for.

**Exit criteria:** a user who installs one package and writes zero ugm code can run all four verbs
against their repo and a policy file.

---

## Sequencing rationale, in one paragraph

Trust core first because it is the pitch (Phase 0); performance in parallel because it is the
floor everything stands on (Phase 1); the KB pipeline before either wedge because both consume it
and it is the moat (Phase 2); checking before generating because it is the smaller trust ask, it
validates the KBs on real code, and its deliverable — the two-world trace in CI — is the single
demo that makes the whole stack legible (Phase 3); the LLM generator last because it is the
highest-variance component and everything before it exists to make its unreliability survivable
(Phase 4); one surface at the end so the loop is sellable rather than assemblable (Phase 5).

## What would falsify this roadmap

Honest kill-criteria, in the project's own spirit:

- **Phase 1 fails** (the constant won't come down by orders of magnitude): the interactive product
  dies; the fallback is batch/CI-only positioning, which weakens but does not kill Phases 3–5.
- **Phase 2 Track B fails** (LLM-drafted CNL cannot pass the anomaly gate without hand-holding
  that costs more than writing the KB by hand): the standing assumption collapses and the tool's
  addressable scope shrinks to hand-authored policies — still viable in regulated niches, but the
  moat thins.
- **Phase 3's discipline is rejected by users** (real decision logic won't factor into
  strider-checkable kernels): the scoping bet was wrong, and that must be learned from a design
  partner's codebase, not assumed — which is an argument for finding that partner during Phase 2,
  not after.
