# Oracle contracts — what a passing verdict proves, and what it silently does not

*Written 2026-07-14 (roadmap Phase 0 — harden the trust core; critique recommendation #6). The
project's moral claim is **auditability**: "every step is a trusted derivation or a trusted check."
That claim erodes the moment a verdict-producing surface passes something it does not actually
establish — the generator front-end's safety-only Pilot shipping a dead app as "trustworthy"
(2026-07-14) was exactly that erosion. This document is the standing answer to the Held Line
(`roadmap.md` #2): **every verdict-producing surface ships with its contract stated — what a passing
check proves, and what it silently does not.** It is a reference, kept in step with the oracles; when
an oracle gains or loses a guarantee, its entry here changes in the same commit.*

Read the format literally. **"A pass proves"** is the guarantee you may rely on downstream. **"A pass
does NOT prove"** is the list of things a green verdict says *nothing* about — the silent gaps, the
place where a reader who over-trusts the verdict gets burned. **"Bounded by"** names the modelling
choice that fixes the gap's size (the abstract domain, the fuel budget, the declared vocabulary).

---

## The axes — naming the directions (so the diagnosis axis has a home)

The whole stack is one firmware (ugm's SUPPOSE / CHAIN / ASK / CHOOSE) run in several directions.
Naming them here pays the second half of the documentation debt (critique #6): the diagnosis axis
existed only in `experiments/diagnosis.py`'s docstring, named nowhere in `docs/`.

| Axis | Direction | Question | Where |
|---|---|---|---|
| **Analysis** (productized) | forward over the value space | *what happens if this input?* | `pystrider/analysis.py` |
| **Diagnosis** (probe) | backward over the hypothesis space | *what must have been true for this crash?* | `experiments/diagnosis.py` |
| **Synthesis** (probe) | backward over the code space | *what code satisfies this spec?* | `experiments/spec_synthesis.py` |
| **Conformance** (probe) | differential over two worlds | *does this code implement this policy?* | `experiments/conformance_strider.py` |
| **Generation / composition** (probe) | forward, spec → runnable app | *what app does this intent + KB derive?* | `experiments/app_synthesis.py`, `generator_frontend.py` |

Every axis closes over the **same** verdict surfaces below. The value of naming them together is that
a green verdict means the same thing whichever axis produced it — and carries the same silent gaps.

---

## A. The forward analyzer — `analyze` / `analyze_all` (`pystrider/analysis.py`)

The original oracle. Also the *disposer* the other axes lean on: diagnosis verifies an abduced cause
by re-running it here; synthesis verifies emitted code by re-analysing it; repair keeps only edits this
oracle re-certifies clean.

- **Verdict.** An `Outcome` (`raises attribute_error`, or `returns_none`) under a value hypothesis for
  one parameter — with a RECORD derivation — or "clean" (no outcome derivable).
- **A pass ("clean") proves.** Under the *supposed* input, over the state-threaded `(state × var)` cell
  lattice, the operational semantics derive **no modelled effect**, and the derivation is inspectable.
- **A pass does NOT prove (silently):**
  - **Correctness.** "Verified" here means *"no modelled effect under the swept hypotheses"*, never
    "does the right thing." Synthesis's `verified True` inherits exactly this weaker meaning.
  - **Effects with no semantics rule.** Only `attribute_error` and `returns_none` are modelled; every
    other exception class is invisible. A `KeyError`, a `TypeError`, a division by zero passes silently.
  - **Values outside the abstract domain.** The domain is `none` / `object` / UNKNOWN. Nothing about
    integers, strings, ranges, or types is reasoned; a bug that lives in that structure is not seen.
  - **Multi-parameter interaction.** One value hypothesis at a time — not the product over all params.
- **Bounded by:** the abstract domain (`none`/`object`/UNKNOWN); the **fuel budget** — a `while` is
  unrolled to a fixed depth (`loop_unroll`, default 2), so a bug first manifesting at iteration *k+1* is
  missed (an honest bound, *not* a fixpoint); path refinement limited to direct `VAR is [not] None`
  tests (no compound `and`/`or`/`not`, no aliasing).

## B. The Pilot drive oracle — `verify_by_pilot` (`experiments/app_synthesis.py`)

The strongest and, until Phase 0, the least characterized oracle. It runs the emitted Textual app
headlessly and reads its event trace. It reports **two independent contracts**; a trustworthy app needs
both. It is a **witness, not a sweep** — one canonical scenario, a single green trace.

- **`ok` — the SAFETY contract.**
  - *A pass proves:* on the driven path, the observed trace contains no `withdrawn` that is not preceded
    by a `gate_shown` when the spec is irreversible (`¬irreversible ∨ ¬performed ∨ gated`). An aborted
    run is safe: it did not perform.
  - *A pass does NOT prove:* that the app does anything at all (a dead app is vacuously safe — this is
    the hole `live` closes); anything about inputs other than the single driven amount (`"42"`); any UX
    property beyond gate-ordering (focus, styling, accessibility, error copy, validation completeness).
- **`live` — the LIVENESS contract** *(added Phase 0)*.
  - *A pass proves:* driving the **happy path** — pressing the affirmative/proceed button — the
    withdrawal actually **completes** (`withdrawn` is reached). Measured on its own affirmative drive, so
    it holds even when the caller drives an abort path (`confirm_choice="cancel"`).
  - *A pass does NOT prove:* that the **abort** path aborts (that is a separate `confirm_choice="cancel"`
    drive, e.g. `test_default_cancel_button_is_real_driving_it_aborts`); completion for any input other
    than `"42"`; that intermediate states are correct — only that the terminal effect is reached.
- **Bounded by:** a single canonical scenario driven by the generic `_drive` helper (type a valid
  amount, press OK, resolve one gate). The oracle is an existence witness over one input, not a proof
  over the input space. Widening it to a scenario **sweep** is the analogue of Phase 0's `repair_all`
  sweep item and Phase 4's conformance sweep.

## C. The grammapy design-time gates — Accumulate / Scope / Choice / Fold

The composition algebra. Every one of these admits from **declared** metadata; each proves a structural
property of the declaration and trusts the declaration's honesty (which is oracle **D**'s job — the
recursive-gating move: an unreliable declaration is caught the same way unreliable code is).

- **Accumulate** (`disjoint_writes`). *Proves:* the atoms' **declared** `writes` footprints are pairwise
  disjoint (the frame rule — no interference). *Does NOT prove:* that an atom writes only what it
  declares (a dishonest atom passes — see **D**); that any atom is individually correct.
- **Scope** (`unhandled_emissions`). *Proves:* every **declared** emitted control signal has a covering
  handler **ancestor** in the declared control tree (no escaping effect). *Does NOT prove:* that the
  handler does anything at runtime — only that the structure covers the signal.
- **Choice** (`guard_coverage`). *Proves:* the guards **partition** the key's value space — disjoint and
  exhaustive — over the decidable enum+presence fragment, so selection is determinate. *Does NOT prove:*
  anything about guards outside that fragment (they fall to the sound may-default, not a checked claim).
- **Fold** (`fold_winner`). *Proves:* a **unique** winner under the **declared** lattice, order-
  independently (the semilattice law). *Does NOT prove:* that the lattice is *right* — which verdict
  *should* win (safety vs. lenient) is a reviewable **declaration**, never inferred or justified here.
- **Bounded by:** the declarations. These gates are a compiler's type-check over composition metadata:
  sound *given* honest inputs, silent about whether the inputs are honest.

## D. The footprint-honesty oracle — `footprint_honest` / `verify_composition` (`experiments/footprint_honesty.py`)

The certifier for **C**'s trusted inputs: it drives an atom in an instrumented store and compares
**observed** writes to **declared** ones.

- **A pass proves.** On the **exercised execution**, the atom's observed write-set ⊆ its declared
  footprint; and re-running disjointness over *observed* writes still admits the composition (it caught
  a dishonest `cancel` that secretly wrote `confirm.submit`).
- **A pass does NOT prove (silently).** Honesty on **unexercised paths** — a conditional write behind an
  untaken branch is invisible. Same bound as any concrete-exec witness (and the same bound as **B**).
- **Bounded by:** the driven path(s). An execution witness, not an all-paths proof.

## E. The reasoning / obligation gate — `required_capabilities` (`experiments/app_synthesis.py`)

The KB-derived obligation, used as GATE 1 of the generator front-end.

- **A pass proves.** The draft provides every capability the KB **derives** as obligatory (the
  deontic/bridge fragments, resolved through the Fold) — e.g. an irreversible action's `confirmation`.
- **A pass does NOT prove (silently).** Obligations the KB does not encode. **Generation breadth equals
  KB coverage**: an uncovered obligation is not a false pass, it is a *named gap* (refusal is a feature,
  Held Line #3) — but only obligations the KB carries are checked here.
- **Bounded by:** the KB. Grows exactly as the deontic/bridge fact banks grow.

## F. The conformance oracle — `conformance_strider` (`experiments/conformance_strider.py`)

The two-world differential: policy and code in one graph, joined by bridge facts, swept for `diverges`.

- **A pass proves.** Over the scenario sweep **enumerated from the policy's declared vocabulary and
  boundary constants**, the code's decision agrees with the policy at every swept point — with a
  two-world proof (policy derivation interleaved with code derivation) on any divergence.
- **A pass does NOT prove (silently).** Agreement outside the declared vocabulary / sampled boundaries;
  anything but the **decision relation** — side effects, performance, and non-decision behaviour are out
  of scope by product definition (Held Line #1: strider-checkable = decision kernels over scalars/enums).
- **Bounded by:** the declared vocabulary + boundary enumeration. Hypothesis supply is solved by
  construction (the sweep is generated from the spec), which is the property that makes this oracle
  *stronger* than **A** — its scenario space is enumerated, not supposed one at a time.

## G. Verify-by-re-execution — synthesis / codegen (`experiments/spec_synthesis.py`, `codegen_understand.py`)

The synthesis-axis disposer: run the emitted function symbolically + concretely on a sentinel.

- **A pass proves.** The emitted function produces the specified outcome on the checked sentinel(s),
  under both the symbolic analyzer (**A**) and concrete execution.
- **A pass does NOT prove (silently).** Correctness beyond the checked sentinels; behaviour of non-pure
  fragments (sandboxing the concrete-exec check for effects is still open — see `spike_findings.md`).
- **Bounded by:** the sentinel set and the analyzer's own bounds (**A**).

## H. The diagnosis oracle — abduced-cause verification (`experiments/diagnosis.py`)

Diagnosis abduces the input that reproduces an observed crash, then **disposes via A**.

- **A verified cause proves.** Under the abduced input, the forward analyzer (**A**) re-derives the
  **observed** effect at the **observed** line — the suspect reproduces the symptom; a suspect that
  reproduces a *different* crash, or none, is exonerated and never enters the candidate set.
- **A verified cause does NOT prove (silently).** That it is the **only** cause. CHOOSE grades candidates
  by specificity (an Occam prior — the smallest reproducing suspect set wins), but the candidate set is
  itself bounded by **A**'s abstract domain and fuel budget.
- **Bounded by:** everything that bounds **A** (the abduction searches within the same modelled world).

---

## The one rule this document exists to enforce

A verdict may be relied on for exactly what its **"A pass proves"** line states — no more. When a caller
(or a future oracle composed from these) needs a guarantee that lives in a **"does NOT prove"** line, it
must obtain it from the oracle that owns it — never by reading more into a green check than the check
signed for. The dead-app regression was one oracle (the Pilot) being read for a guarantee (liveness) it
had never made; the fix was to make the guarantee explicit (`live`) rather than assumed. That is the
pattern: when a silent gap starts to matter, promote it to a stated contract here and a checked property
in the code — do not let the reader keep assuming it.
