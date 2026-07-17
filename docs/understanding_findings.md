# Understanding real code — findings

**Verdict: understanding does not require naming.** A step-by-step chain of statements is already
fully meaningful and fully operable by the symbolic core (execute, footprint, trace, repair) *without*
a named concept. Named concepts (`sum`, `map`, `filter`) are a **compression** layer — a shortcut that
also carries a certificate of properties — laid over a base tier that is complete on its own. Measured
over the Python standard library, that compression layer covers about **half** of real loops with three
rules and then **plateaus**, and the coverage it claims is majority **conditional**. The uncovered
residual is not a hole the core can't reach — it is base-tier code with no compressing concept, handled
by the same base-tier mechanisms as everything else. And the intent→spec boundary is, in this substrate,
**CNL a technical user already writes** (business/UX/library rules → checked working code), not model
output. So a language model is **nowhere load-bearing**: its only jobs are optional and gated — translate
free English into CNL at the input surface, and propose a name for a base-tier chunk when compression or
reuse is worth it.

This doc records the arc that produced that conclusion (2026-07-17). Every claim is backed by a runnable
probe under `experiments/` and pinned by tests under `tests/`.

---

## 0. The reframe that started it — the humble target

The earlier arc (the `footprint-synthesis` / composability work)
built a machine to **prove composability**: grammapy's combinators, footprints, disjoint-writes, Scope,
soundness sweeps, abstention. Useful — but it is one heavyweight *checker*, and it captured the agenda.

The actual (humbler) goal, from the start: **represent patterns as rules** (not static templates),
**compose** them by intent, and **repair** composition issues — the way humans write code, who use
almost none of that machinery. The load-bearing insight:

> The strength of check you need is a function of how *unreliable* your writer is. grammapy's proving
> exists for an unreliable **LLM** proposer. A **symbolic** rule-based composer is reliable by
> construction (rules don't hallucinate), so the check downsizes to what humans use — **run it** — and
> grammapy becomes an *optional* strong check, not the spine.

`experiments/pattern_compose.py` (+ `tests/test_pattern_compose.py`, 7) demonstrates the humble target
directly: patterns are intent-tagged rules (a domain-blind engine formats them), composition is
recursive subgoal expansion, the check is **execution against the intent's meaning**, and repair is a
**local** pattern swap at the sub-intent whose output betrayed its intent — no grammapy, no proofs.

---

## 1. Recognition — the mirror half, and its two failure modes

Writing composes patterns you already have (closed world). *Understanding* means recognizing code
**someone else wrote**, spelled however they chose — the open-world "normalization tax"
(`docs/codegen_understand.md`). `experiments/understand_robustness.py` (+7 tests) measures it for one
intent (`average` = `sum(xs)/len(xs)`) across many human spellings. Two failure directions appear, and
they are the recognition analogs of the footprint findings:

- **Over-recognition (silent mis-ID).** Naive wildcard matching accepts `sum(xs) / len(ys)` as a mean,
  because its two holes are independent. Fixed by **hole-consistency**: a repeated hole must bind the
  *same* sub-expression.
- **Under-recognition (the tax).** An intermediate variable, a library call, an accumulator loop are all
  missed by exact-spelling matching. A **band** is reclaimed by small normalization rules (inline a temp,
  de-alias `statistics.mean`); beyond it is a cliff.

## 2. The cliff is climbable — semantic idiom rules

The cliff was an artifact of a purely **syntactic** recognizer. A **semantic** (dataflow) rule reaches
the summing loop: `experiments/understand_semantic.py` (+7 tests), `recognize_fold` —

> an accumulator initialized to the operator's **identity** (0 for `+`, 1 for `*`), then `acc <op>= f(e)`
> over a `for e in it`, computes `sum` / `prod`.

**One** rule recognizes the summing loop across spellings (`s += e`, `s = s + e`, renamed vars), and stays
honest: a product is not a sum, a non-identity init is not a clean sum, a loop with control flow inside is
the *next* cliff (abstain, not guess). So a cliff is **the top of the current rule tier**, not a wall; you
climb it tier by tier, and abstention holds the floor beyond the top rule.

---

## 3. The reclaim curve over real code — holistic is flat

`experiments/understand_curve.py` runs holistic idiom recognizers (fold / map / filter / dict-build, each
conservative → 0 mis-ID) over **the Python standard library** (152 files, 1271 `for` loops):

```
fully recognized  ~4%      |  96% CLIFF
```

And the cliff is **genuinely imperative**, not a strictness artifact (only ~3% headroom): 43%
multi-statement bodies, 12% bare side-effect (`foreach`) loops, 25% single-`if`. Whole-loop recognition
of foreign code has a real long tail. This **corrects the toy-case optimism** — hand-picked
comprehension-shaped loops had suggested fast reclaim.

## 4. Partial recognition — the aspect is the right unit

Holistic matching is all-or-nothing: a loop is `map` only if the *whole* body is the append, so compound
loops (43%) score zero. The fix (an idea raised in-session): recognize **aspects** independently.
`experiments/understand_partial.py` (+4 tests) walks a loop body (through control flow) classifying each
leaf statement — `accumulate`, `collect`, `index-set` are value aspects; side-effect / scalar-assign /
control are honest residual:

```
holistic (one whole idiom)     ~4%
partial  (>=1 value aspect)    ~52%      (14x)
per-action: ~27% of all loop leaf-statements are nameable value-aspects
```

**The right unit of recognition is the aspect — a *partial* description — not the whole loop.** This is
*exactly the footprint move*: a footprint is a partial description of what code **writes**; an aspect is
a partial description of what a loop **does**. The write-side (footprint synthesis) and the understand-side
(aspect recognition) are the **same discipline**: describe what you can prove, name the residual, abstain
on the rest.

## 5. Does the partial curve keep climbing, and is it honest?

`experiments/understand_partial_curve.py` (+4 tests) measures the two things that actually carry
information (naming aspects into a summary would be mere semantic chunking):

**(1) Marginal reclaim curve — it plateaus hard.**

```
+ collect        -> 28.2%  (+28.2%)
+ index-set      -> 44.5%  (+16.4%)
+ accumulate     -> 51.5%  (+ 7.0%)
+ minmax-reduce  -> 51.6%  (+ 0.1%)   <- the 4th rule buys nothing
```

Three rules do essentially all the work; more rules barely move it. Partial-aspect coverage **saturates
~52%** with a tiny rule set — it does not keep climbing. Beyond the core value-builders the residual is
genuine effects/state/control.

**(2) Faithfulness — the 52% was over-claimed.**

**59% of the recognized value-aspects sit under a guard.** The flat walker reported `if p: out.append(e)`
as an unconditional `collect`, silently dropping the condition — the same silent over-claim the footprint
and recognition sweeps caught. Faithful partial recognition must carry *the aspect **and** its condition*
(`collect(cond)`), or it lies. So the honest read is ~41% unconditional value-aspects plus a guarded
remainder — not a flat 52%. The irreducible residual: scalar-assign 51%, side-effect 26%, control 23%.

---

## 6. The base-tier reframe — the residual is not a hole

The pessimistic reading of §3–§5 would be "understanding is membrane-dominated." That reading is wrong,
and it comes from silently equating **understood** with **has a named concept**. Separate the two:

- **Understanding ≠ naming.** A statement chain is fully meaningful by *being* what it is. The symbolic
  core already operates on it with no concept name: execute/trace it (trust-by-execution), **derive its
  footprint** (works on *any* statements — this is base-tier understanding), summarize its effects,
  repair it locally by intent-mismatch.
- **Named concepts are compression + a property certificate.** `sum` is shorter than the loop *and*
  advertises associativity/commutativity/order-independence (so it is parallelizable, reorderable, safe
  to fuse). The unrolled chain has the same *behavior* but does not *advertise* the properties — to
  transform it safely at a high level you would re-derive them (on demand).
- **So naming's value is task-dependent:** low for analysis/checking (base tier suffices), high for
  intent-level transformation and reuse-with-guarantees (the certificate is what makes the rewrite sound).
  But the properties are only *un-advertised*, never absent — recoverable on demand, the agent-not-
  theorem-prover stance.

**Consequence — the membrane shrinks, twice.** It is *not* "the ~48% we could not name." Everything
about the residual — reasoning about it, checking it, footprinting it, and even **reusing** it as a
black-box fragment with a *derived* interface — stays in the symbolic core, no model. The flat
recognition curve is therefore **compression-vocabulary saturation** (expected: most real code lives at
the base tier), **not** a scaling wall.

And the *other* half of the membrane — intent→spec — is smaller than "an LLM writes the spec" too. In
this substrate the spec is **CNL a technical user already writes**: `demos/playground/` carries
`business.cnl`, `ux.cnl`, a library's `textual.cnl`, and a `bridge.cnl` crosswalk, all facts and rules
in one graph, and a deontic UX rule flips an app's screen to a confirm gate — *working, checked code from
authored rules, no model in the loop* (see the README). Per ugm's own "CNL as surface, not engine input"
stance, a language model's job at the intent boundary is only to *translate free English into CNL* — a
convenience at the outer edge, not a load-bearing component. So the honest, fully-reduced role of an LLM
is: (a) optionally translate free NL → CNL at the input surface, and (b) optionally propose a name for a
base-tier chunk when compression/reuse is worth it. It is **nowhere load-bearing**; everything that
carries the guarantee is symbolic + execution.

**The residual is operable — demonstrated.** `experiments/base_tier.py` (+ `tests/test_base_tier.py`, 4)
takes the stdlib loops with **no** recognized value-aspect (the unnamed residual, 616 of them) and shows:
**0% named, 100% base-summarized** — every one has a derivable footprint (iterate / read / write /
effect), and 89% write or call. It then **reuses** a genuinely bespoke loop (a line-continuation joiner,
no `sum`/`map`/`filter` fits) as a black-box fragment: derive its interface (inputs = free reads,
produces = written state) *without naming it*, and invoke it on real input to the right output. Reuse
needs an interface, not a name — the base tier already provides it.

---

## 7. The checker's honest boundary — a red-team

The whole guarantee rests on the checker (derive a footprint + verify by execution), so the credible move
is to attack it hardest. `experiments/soundness_redteam.py` (+ `tests/test_soundness_redteam.py`, 5) is an
adversarial battery that tries to make the checker certify wrong code, and maps exactly where it is blind:

- **Footprint oracle** — of 9 adversarial writes, plain writes are SOUND, the dict methods `update` /
  `setdefault` are now **MODELED** (their key-writes derived exactly), and every genuine store-escape is
  **CAUGHT by abstention** (honest UNKNOWN): helper-mutation, direct-aliasing, operator-mutation
  (`out |= {…}`), and container-aliasing across an untaken branch. The two that once *slipped* were closed
  by **productizing** abstention into `pystrider.footprint.modelable`, which now models known container
  methods (subscripts, `update`/`setdefault`/`append`/`add`/…, and reads) and abstains on everything else
  (an unknown method, a callee, an alias, a comprehension). So the footprint oracle has **no remaining
  silent slip** in this battery; `footprint_of` carries the `unknown` flag, and the compose check
  **refuses** on it rather than admit an under-approximation.
- **Execution oracle** — verifying on one input is not verification (a falsy-but-valid input is silently
  dropped: `v or 'default'` "passes" at `v=5`, drops `v=0`), and a single run certifies a
  non-reproducible value (`random.random()`). Fixes: multi-input / property-based verification, and a
  determinism check.

The point is not that the checker is unbreakable — it is that it breaks in **named, bounded** ways, each
with a known mitigation. "The guarantee holds up to *this enumerated boundary*" is a credible claim; "the
guarantee always holds" is not. This is the same discipline as the rest of the doc: state the limit
precisely, and abstain (or extend) rather than over-claim.

## 8. The economic limit — a compression, but a platform bet

The make-or-break: did authoring CNL *reduce* the work, or just move it? `experiments/economic_test.py`
(+ `tests/test_economic_test.py`, 5) measures it on the real `demos/playground/`, no rigging:

- **The compression is real.** ~**10 rule-lines** of per-app spec (business + ux + bridge, plus 4 reused
  library lines) emit an *unbounded* family of verified apps — every knob setting a different app of
  **50–78 lines** of driven-green Textual source. The CNL is the irreducible decisions (the discount rule,
  the confirm obligation, the bridge); the emitted lines are those decisions *plus* derived
  widgets/wiring/gate/verify. It is **not** relocated boilerplate — it compresses to the decision content
  and derives the rest.
- **The platform is *given*, not the author's cost.** ugm 9,750 + grammapy 644 + pystrider 1,586 + brew
  356 ≈ 12,336 sloc is reusable infrastructure adopted once — you no more count it against 10 spec-lines
  than you count CPython against a script. (Counting the platform's own source against the author's spec
  was a framing error, corrected here.) The author's ledger is simply: **10 spec-lines in → 50–78 verified
  lines out, × an unbounded family** — a clear compression.
- **The real economic variable is bundle-composability *coverage*, not platform LOC.** The
  10-lines-in win holds only *within* the coverage of the composable bundle library. The open question —
  the write-side analog of the reclaim curve — is how much of a *new* app is "compose existing bundles + a
  few spec lines" vs. "author new bundles." A first *illustrative* read
  (`experiments/composability_coverage.py`): over a spectrum of new requirements against the 23-token
  bundle vocabulary, ~58% are cheap (compose-existing or a-few-rule-lines) and ~42% need a new bundle —
  and even a re-target reuses the business/ux decisions. That re-target is now a **driven fact**, not a
  vocabulary read (`experiments/retarget_family.py` + `tests/test_retarget_family.py`, 5): the *same*
  `business.cnl` + `ux.cnl` (7 decision-lines) drive **two** independent, driven toolkits — the existing
  Textual app *and* a headless CLI family — and a whole spectrum of carts satisfies the **same** behavioral
  contracts on **both** (a confirm gate precedes completion iff irreversible; the discount shows iff
  granted). The 7 decision-lines are reused **verbatim** across targets; only a 5-line library port is
  re-authored. So the economics reduce to the bundle library's *coverage* — the same ecosystem question any
  framework faces — which a real corpus of app specs would measure.
- **And the LOC model *understates* the win** — now **demonstrated**, not argued
  (`experiments/interaction_scaling.py` + `tests/test_interaction_scaling.py`, 5, on grammapy's real
  `Accumulate` and by running the emitted programs): as a feature library grows to *F*, the author's ledger
  stays **linear** (one bundle per feature) while the interaction-audit surface grows **quadratically**
  (`C(F,2)` pairs that could clobber a shared slot) — and grammapy's frame rule bears that quadratic
  **automatically**. At *F*=32 the injected collider is **caught structurally in one pass** (the author wrote
  zero interaction code), while the naive additive program **silently clobbers** the shared slot at runtime —
  the exact bug hand-additive code ships. The structural check's boundary is named (it audits *resource*
  collisions, not *semantics*); a semantic interaction on disjoint slots falls to the **second automatic
  layer, driven execution** — not to the author. Plus: the same business/ux rules re-target a new library for
  a few rule-lines, and every change is re-derived, re-verified, and carries a why-trace for free.

**Verdict:** for a platform user the compression is real and repeatable, the platform given like any
framework. The approach did not move the work — the CNL is the irreducible decisions, the rest is derived.
The open economic question is the bundle library's **coverage**, not the platform's size.

## 9. The vagueness limit — the last redoubt, and it falls on the leaves

Real requirements are underspecified, and "read what they *really* meant" is an LLM's clearest pitch — so
vagueness is the last place a model could be load-bearing. `experiments/membrane_vagueness.py`
(+ `tests/test_membrane_vagueness.py`, 6) pushes it, grounded in the real `demos/playground/` engine (every
claim brewed and driven, not asserted). The decisive move is a **scope line**: "underspecified" is in scope
as the symbolic core's job *only* when it means **rule-expandable semantic chunking** — a compressed spec a
known rule set unrolls to the concrete one (the spec-side of the "concept = compression" finding). The probe
implements exactly that as **backward-chaining over the real CNL rules**, and the vagueness splits cleanly:

- **The structure is rule-expandable — no model.** The vague chunk `requires_feature highlighted_discount`
  ("show the discount loyal customers earn") unrolls, rule by rule, to `has_benefit ← grants_discount ←
  {customer_tier, order_qualifies}`. The whole derivation is pinned by known rules; nothing is inferred.
- **It bottoms out at LEAVES that are open decisions, not vagueness the core resolves.** No rule fills "is
  *this* customer loyal?" or "is *this* sale final?" — these are facts about the world the author supplies.
  The honest move is to **surface** them (abstain), not guess.
- **A leaf has no truth to infer — proven by brewing.** For the `customer_tier` leaf, *both* authored values
  (`premium`, `basic`) drive **green**, as genuinely **different apps**. So there is no "correct" value for
  an engine — or a model — to recover; whatever an LLM "infers" is a guess dressed as knowledge. The
  load-bearing operations, **decide** (author) and **check** (execution), are structurally where the model
  is not. It may *propose a default* for a surfaced leaf, but that is a knob: confirmed, re-derived, driven.
- **The anti-pattern is silent-default — the model sneaking in.** Guess a leaf (`premium`) when the world is
  `basic`: both green, so the guessed app **ships, drives clean, and is wrong**, with no signal. This is the
  intent-side twin of unsound-silent footprint derivation. The surfaced membrane refuses to emit while any
  decision is open (`pin` returns `REFUSE` naming the open knobs), so the decision is made **on the record**,
  never defaulted.
- **Articulation-vagueness ("make the checkout trustworthy") is pre-CNL.** No rule and no knob names it. The
  model's role is to propose a **decomposition** into articulable decisions — but two candidate decompositions
  each brew valid apps, so the decomposition is itself a *proposal* (no unique truth), author-confirmed, and
  once confirmed it collapses to the leaf case. The model turns unarticulated → articulated; never
  under-decided → correctly-decided.
- **The honest boundary — unknown-unknowns.** Surfacing only reaches *articulated* decisions: a concept no
  rule and no knob names (`sales_tax`) is invisible — you don't know to ask. That residual is aided by any
  completeness proposer (a model, a domain expert, a checklist), still gated by author-decision + check. The
  guarantee holds up to **this enumerated boundary**, named not hidden — the soundness red-team's discipline.

**Verdict:** the last redoubt falls the same way as the rest. CNL pins the rule-expandable part of a vague
requirement outright; beneath it the open decisions are **surfaced, not resolved** — and there a model can
only guess, which surface-and-check strictly dominates. The model **proposes**; the author **decides**;
execution **checks**. It is nowhere load-bearing, up to the named unknown-unknown boundary.

## The picture, in one line per tier

| Tier | What it is | Coverage of real loops | Needs a model? |
|---|---|---|---|
| **Base** | statements + derived footprint/effect + execution | 100% (everything is operable) | no |
| **Concept (compression)** | named aspects with property certificates | ~52% with 3 rules, then plateaus; ~60% of it conditional | no (rules); optional name-proposal |
| **Intent** | what the code *should* do (the spec) | CNL a technical user writes; vague chunks unroll by known rules (§9) to open decisions the core *surfaces* | no — model only *translates* free NL → CNL, *proposes* a default/decomposition, or *prompts* completeness — all gated by author-decision + execution |

The symbolic core owns the base tier (which is all of it) and *compresses* the fraction that has a known
concept, honestly labelling conditions and abstaining where a claim would over-reach. At the intent tier
the spec is authored CNL, not model output. A language model is therefore **nowhere load-bearing**: it is
an optional surface translator (free NL → CNL) and an optional proposer of names for reuse — both gated by
execution/checking, so its unreliability never reaches the guarantee.

## Next

The base tier and the intent tier are both demonstrated (`experiments/base_tier.py`; `demos/playground/`
in the README). The open, additive directions — none of which change the conclusion — are: compose
faithful (guard-carrying) aspects into a readable loop summary (semantic chunking, now a downstream
convenience); round-trip aspects to the write side (recognize → reuse → recompose); and grow the concept
vocabulary opportunistically where compression pays. grammapy stays an *optional* strong check for when a
strong guarantee is wanted, not the spine.

Related: `docs/the_case.md` (the readable synthesis of the whole argument), `docs/codegen_understand.md`
(the questions this answers), `docs/critique.md` (§8 composition, §5 unsurfaced-unknown). Memory:
`pattern-writer`, `footprint-synthesis`.
