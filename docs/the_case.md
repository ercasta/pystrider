# The case — trustworthy code generation without a load-bearing language model

*The standing argument for what this project is and why it holds. This is the readable synthesis; the
substantiation lives in [`docs/understanding_findings.md`](understanding_findings.md) (the findings, tier by
tier), [`docs/deep_dive.md`](deep_dive.md) (the technical tour), and the runnable probes under
`experiments/`. Every claim below points at code that runs and a test that pins it. Written in the project's
own discipline: **describe what you can prove, name the residual, abstain on the rest** — so the boundaries
are foregrounded, not buried.*

---

## The claim, stated so it can be attacked

> For the class of software that is **composed of known operations plus policy-shaped decisions** — the
> orchestration-and-decision code that is most enterprise software — trustworthy code can be **generated and
> checked by a symbolic core plus execution**, with a language model **nowhere load-bearing**. The model's
> only jobs are optional and gated: translate free English into CNL at the input surface, propose a default
> or a decomposition for an open decision, and prompt for completeness. None of these reaches the guarantee,
> because everything that carries the guarantee is a rule-derivation or an execution.

Three words in that sentence are load-bearing and are defended below: **class** (the claim is scoped, not
universal), **nowhere load-bearing** (the model can be wrong without the guarantee moving), and **gated**
(a model proposal is always disposed by a check it does not control).

What the claim is **not**: it is not "language models are useless for code," and it is not "any Python can be
generated this way." A genuinely novel algorithm inside a leaf fragment is exactly the residue where a model
(or a human) fills a *declared hole* — gated by execution like everything else. The claim is about where the
**trust** lives, not about who types the first draft.

---

## The substrate, in one breath

Everything runs on one small engine: the [Universal Graph Machine](https://github.com/ercasta/Universal-Graph-Machine)
reasons over a graph of facts by firing declarative rules on demand, keeping a replayable trace. Business
rules, UX rules, absorbed library facts, and cross-vocabulary bridges are all just facts and rules *in that
one graph*. "Does this cart get a discount?", "which features must the app have?", "do these widgets compose
without interference?", "did the app behave?" are the same kind of question — a backward query — answered by
the same engine. pystrider owns **no** engine code: it materializes graph structure from Python's `ast`,
emits source, and runs things (the honest tool boundaries); the composition algebra ([`grammapy/`](https://github.com/ercasta/pystrider/tree/main/grammapy))
and the analysis semantics are CNL rule-modules over the firmware. See [`deep_dive.md`](deep_dive.md).

The one epistemic move, everywhere: **the generator proposes; a check disposes; nothing is trusted because a
tool claimed it.** A bug fix is trusted because the edited code *re-runs clean*; a composed app is trusted
because it is *driven* headlessly and observed to behave. This is "trust by execution," and it is why the
reliability of whoever *proposed* a step never has to be trusted — only checked.

---

## The spine — three tiers, and the model is absent from each

The heart of the argument (full version: [`understanding_findings.md`](understanding_findings.md)) is that
"understanding or writing code" decomposes into three tiers, and a model is load-bearing in none.

| Tier | What it is | Coverage of real code | Needs a model? |
|---|---|---|---|
| **Base** | statements + derived footprint/effect + execution | 100% — everything is operable | no |
| **Concept** (compression) | named aspects carrying property certificates (`sum`, `map`, …) | ~52% of real loops with 3 rules, then plateaus; ~60% of it conditional | no (rules); optional name-proposal |
| **Intent** | what the code *should* do (the spec) | authored CNL; vague chunks unroll by known rules to open decisions the core *surfaces* | no — model only translates / proposes / prompts, all gated |

- **Base tier is complete on its own.** A chain of statements *is* meaningful by being what it is. The
  symbolic core executes it, derives its write-footprint from the code (`pystrider.footprint_of`), summarizes
  its effects, and can even **reuse it as a black-box fragment by its derived interface — without a name**
  (`experiments/base_tier.py`). Understanding does not require naming.
- **Concept tier is compression, not a hole.** A name like `sum` is shorter than the loop *and* advertises
  properties (associativity, order-independence). Measured over the Python standard library, holistic idioms
  cover only ~4% of loops but **partial, per-aspect** recognition reaches ~52% with three rules and then
  plateaus (`experiments/understand_partial*.py`). The uncovered residual is not unreachable — it is base-tier
  code with no compressing concept, handled by the same base-tier mechanisms. Naming's value is
  task-dependent (low for checking, high for intent-level rewrite), and the properties are only
  *un-advertised*, never absent — recoverable on demand.
- **Intent tier is authored CNL, not model output.** The playground (`demos/playground/`) carries
  `business.cnl`, `ux.cnl`, a library's facts, and a `bridge.cnl` crosswalk — working, checked code from
  authored rules, no model in the loop. A vague requirement is *rule-expandable chunking*: it unrolls by known
  rules to open decisions the core **surfaces** (never silently defaults). See the vagueness limit-test below.

---

## Why it is credible — the membrane is always made visible

The recurring failure mode in symbolic systems is the **silent over-claim**: a check that passes something it
did not establish. The project's answer is a single discipline applied at every seam — *derive what you can,
and when you can't, abstain with an honest "unknown" rather than guess*. The abstention boundary **is** the
membrane where the core hands off, and it is always visible:

- **Footprint derivation** misses writes on some constructs (`dict.update`, aliasing across an untaken
  branch). Rather than under-approximate silently, `modelable()` detects the un-analyzable and returns
  honest-unknown; the compose check refuses on unknown rather than admit a possible collision
  (`experiments/footprint_scalability.py`).
- **Recognition** abstains on a loop it cannot reduce to a known aspect, and carries the *condition* of a
  guarded aspect rather than reporting it as unconditional (`understand_partial_curve.py`).
- **Intent** surfaces an open decision as an explicit, required knob rather than defaulting it
  (`membrane_vagueness.py`).

"Symbolic core scales iff it **knows when it can't**" — the honest-unknown boundary is not a weakness of the
approach, it is the mechanism that keeps the guarantee sound.

---

## The four limit-tests — pushed to the edge, breaks are named and bounded

A thesis is only credible if you attack its load-bearing parts hardest. Four adversarial tests push it; each
records where it holds and, honestly, where it does not (`understanding_findings.md` §7–§9).

1. **Soundness red-team** (`soundness_redteam.py`). Can the checker certify wrong code? Yes — in **named,
   bounded** ways: operator-mutation (`out |= …`) and container-aliasing across an untaken branch slip both
   the footprint oracles and the abstention detector; the execution oracle is blind to input-dependence
   (single-input verify) and non-determinism. Each has a known fix (extend abstention; multi-input/property
   verify; a determinism check). "Holds up to *this* enumerated boundary" is the credible claim; "always
   holds" is not.
2. **Economic** (`economic_test.py`). Did authoring CNL *reduce* the work or just move it? The compression is
   real — ~10 rule-lines of per-app spec emit an unbounded family of verified 50–78-line apps — and the
   platform is *given*, like CPython to a script. The real variable is the bundle library's **coverage**, the
   same ecosystem question any framework faces.
3. **Composability coverage** (`composability_coverage.py`). Of a *new* app, how much is compose-existing vs.
   author-new? Over an illustrative spectrum, most requirements are cheap (compose or a-few-rule-lines) and a
   minority need a new bundle — and even a re-target reuses the business/UX decisions.
4. **Membrane-vagueness** (`membrane_vagueness.py`) — *the last redoubt.* Real requirements are
   underspecified, and "read what they really meant" is a model's clearest pitch. But underspecification that
   is *in scope* means **rule-expandable chunking**: a vague goal unrolls, by known rules, to open decisions
   the core surfaces. For a surfaced decision there is **no truth to infer** — two authored values both drive
   green as different apps — so a model there can only guess, and guessing silently ships a valid-but-wrong
   app, which surface-and-check strictly dominates. Articulation-vagueness ("make it trustworthy") is pre-CNL,
   resolved by a proposed-then-confirmed decomposition. The model proposes; the author decides; execution
   checks. The one genuine limit is the **unknown-unknown** — a decision no vocabulary names cannot be
   surfaced — aided by any completeness proposer, still gated.

---

## Does it pay? — the win is at scale, and both legs are demonstrated

The economic test's sharpest finding is that a line-count comparison *understates* the win, because a
hand-coder must manage a combinatorial feature-interaction surface while a CNL author grows linearly and the
checker bears the interactions. Two runnable demonstrations, on the real checker, make that concrete — and,
importantly, a one-off app *looks like a loss*, so the case must be made at scale.

- **Feature-interaction scaling** (`interaction_scaling.py`). As a feature library grows to *F*, author
  effort is **O(F)** (one bundle each) but the interaction-audit surface is **O(F²)** (pairs that could
  clobber a shared slot) — and grammapy's frame rule bears that quadratic **automatically**. At *F*=32 an
  injected collider is caught structurally in one pass (the author wrote zero interaction code) while the
  naive additive program silently clobbers the slot at runtime. The structural check's boundary is named
  (it audits *resource* collisions, not *semantics*); the semantic residual falls to the second automatic
  layer, driven execution — not to the author.
- **Re-targeted families** (`retarget_family.py`). The *same* `business.cnl` + `ux.cnl` (7 decision-lines)
  drive **two** independent, driven toolkits — the existing Textual app *and* a headless CLI family — and a
  whole spectrum of carts satisfies the *same* behavioral contracts on both. The decisions are reused
  **verbatim**; only a 5-line library port is re-authored per target. The expensive part is the decisions,
  authored once; the re-target cost is the toolkit port.

---

## The honest boundaries, collected

So they are read as one list rather than discovered one at a time:

- **Footprint derivation** is unsound-silent on operator-mutation and container-aliasing across untaken
  branches; abstention covers the rest but not yet those two.
- **The execution oracle** is a witness, not a proof: single-input verify misses input-dependence, and one
  run certifies a non-reproducible value. Multi-input/property verification and a determinism check are the
  known extensions.
- **The structural composition check** (disjoint-writes) sees resource collisions, not behavioral/semantic
  interactions; those fall to driven execution.
- **The intent surface** pins all *articulated* vagueness; **unknown-unknowns** (a decision nobody named)
  are invisible to it — aided by any completeness proposer, still gated by author-decision + check.
- **Coverage** is the real economic variable: the compression repeats only within the bundle library's
  reach, which a real corpus of app specs would measure.

None of these is a silent mystery. Each is a precise gap with a named mitigation — which is the whole point:
the guarantee is stated *up to a boundary you can see*.

---

## Where the language model actually is — the fully-reduced role

Having removed it from the trust path, the model's remaining jobs are exactly three, all optional and all
gated by author-decision or execution:

1. **Translate** free English into CNL at the input surface (a convenience at the outer edge; per ugm's "CNL
   as surface, not engine input" stance).
2. **Propose** a default for a surfaced open decision, or a decomposition for an unarticulated one — a
   proposal that becomes a knob: confirmed, re-derived, and driven.
3. **Prompt** for completeness — raise a decision nobody named (the unknown-unknown aid), which a domain
   expert or a checklist does equally well.

A wrong model output in any of these is caught the same way a wrong knob is — by the author reading the
surfaced decision and by the drive. That is what "nowhere load-bearing" means precisely: the model's
unreliability never reaches the guarantee, because a check it does not control always disposes its output.

---

## Positioning — what to sell, and what not to

Do **not** position this as a general-purpose code generator (that invites a head-to-head with LLM assistants
on "write me any Python," which loses on breadth) or as a generic bug-finder (pyright and LLMs own that).
Position it where the identity **"generation breadth equals KB coverage"** is a strength:

- **Generating** decision-and-orchestration code from a succinct CNL spec + a domain KB — deterministically,
  with a proof bundle, where every emitted line traces to a rule or a fragment.
- **Checking** that a piece of code implements a piece of policy — and a verified minimal edit when it does
  not (`conformance_strider`).

The economics that make "KB as instruction set" a feature rather than a tax: **many instances per KB**,
**specs that change often** (a policy change re-derives the code *with a diff of what changed and why*), and
**correctness that is priced** (regulated logic where "why does this code exist" must have an auditable
answer). The strategic sequencing lives in [`roadmap.md`](roadmap.md); the standing contract of what each
verdict proves lives in [`oracle_contracts.md`](oracle_contracts.md).

---

## In one line

A small rule engine, run in many directions, with **execution as the final arbiter** and **abstention as the
visible membrane**, generates and checks the orchestration-and-decision code that is most software — carrying
the trust itself, and leaving a language model only optional, gated work at the edges. The claim holds up to
a set of boundaries that are named, not hidden — which is the strongest form the claim can honestly take.
