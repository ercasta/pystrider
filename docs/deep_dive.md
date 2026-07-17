# pystrider — deep dive

> This is the full technical tour. For the friendly front door — bring your rules, bridge them, brew a
> working UI — see the [README](https://github.com/ercasta/pystrider/blob/main/README.md). Everything below is what powers that, in detail.

A **hypothesis-driven code analyzer, bug-fixer, and policy-conformance checker** built on the [Universal Graph Machine](https://github.com/ercasta/Universal-Graph-Machine) library.
Instead of matching static bug patterns, it reasons about a Python function the way a person does:
*suppose* a value for a parameter, symbolically *run* the code by applying an operational semantics
expressed as UGM rules, and read what *happens* — with a human-readable trace behind every
conclusion. Then it *repairs* the code and *verifies* the fix by re-running the analysis.

**The unusual part:** every conclusion — every bug, every fix, every policy-violation — is a
**replayable proof object**, and the *same small rule engine* runs in several **directions** on it:
reading code (analysis), fixing it (repair), explaining a crash (diagnosis), and **checking it against a
business policy** (conformance). Nothing is trusted because a tool claimed it — everything is checked by
re-running the reasoning.

The reasoning also drives a full **generation loop** — the [playground](https://github.com/ercasta/pystrider/tree/main/demos/playground/) composes a
knowledge base into a *runnable, verified application* (**reason → compose → emit → drive**), where the
**soundness of composition is itself CNL**: a second in-repo package (`grammapy`) supplies a
composition algebra whose every check is a rule-module over the same graph, and the emitted app is
trusted because pystrider **drives** it (a real Textual app, observed to behave). Change one sentence of
the spec and the code **re-derives with a proof of what changed and why** — the "policy change →
verified code change" artifact no LLM regeneration can produce.

Analysis + repair are **productized**; diagnosis and conformance are proven **end-to-end as probes**. A
library's API surface is now **absorbed as data** (`pystrider.absorb`, from live type hints), and the same
anomaly-checking loop turns on **rule banks themselves** (rulestrider) — the KB-ingestion gate that makes
authored knowledge trustworthy.

pystrider owns **no** engine code. Intake materializes graph structure from `ast`; everything downstream
— the analysis semantics, the four composition combinators, and cross-cutting constraint resolution —
reasons through the public UGM firmware (`suppose` / `ask_goal` / `choose`) as CNL rules. Python is
confined to its proper role: the tool boundaries (intake, `absorb`), AST emission, and execution.

## What it does (today)

The vertical loop is proven and productized across four analysis/repair slices. A **third axis —
crash → root cause (diagnosis)** is proven as a probe: the loop run backwards over the *hypothesis*
space, abducing the input that reproduces an observed exception, then handing the cause to the repair
axis. A **fourth axis — code ⟷ policy conformance** is proven as a probe: a business policy and the code
in one graph, joined by a declarative **bridge** across their vocabularies, with spec-vs-code divergence
derived as a fact and repaired spec-directed. And the reasoning drives a **generation loop** (the
playground) — a knowledge base composed into a runnable app, verified by driving it:

- **Slice A — correct value flow.** Value lives in a per-`(program-point, variable)` **cell
  lattice**, so reassignment (`y = a; y = b`), **branch-merge** (union of both arms), bounded
  **loop unrolling**, and **path-sensitive refinement** (a `if v is not None:` fork narrows `v` per
  branch, so the deref on the safe branch is not a false positive) are all correct. Every value
  union at a join is a rule *derivation* (the frame rule firing once per edge), never a Python meet.
- **Slice B — a Session.** Several functions coexist in **one shared graph** (identity by
  `(function, source_name)`), each analyzed under its own `focus_scope`, detection read-only so
  functions/hypotheses never contaminate one another — and a **value flows across a call boundary**
  into the callee.
- **Slice C — a second effect.** Beyond None-derefs (`AttributeError`), a `returns_none` outcome
  ("returns None when a non-None was intended") is authored as one more semantics rule + two library
  operators — reusing the whole retrieve / verify / CHOOSE loop with **no new machinery**.
- **Means-ends repair.** For any effect: **retrieve** applicable edit operators from an effect-keyed
  library by backward-CHAIN, **materialize** each as real Python (AST rewrite), **verify** each by
  re-intaking + re-analyzing the edited source, and **CHOOSE** the graded-best.
- **Whole-function auto-fix.** `repair_all` drives repair to a fixpoint — fix *every* outcome (of any
  effect), each edit verified to make progress **and** introduce no regression, until the function is
  clean — returning the edited source plus an audit log of what it changed and why.
- **Honest "clean" — no building on silence.** Intake emits a visible `not_modelled` marker for any
  statement kind it can't thread (aug-assign, attribute store, tuple unpack, bare call, …) instead of
  silently framing a stale value forward; `caveats()` surfaces them and `repair_all` *qualifies* its
  verdict — "repaired to clean **(modulo N unmodelled statements)**", `fully_modelled=False` — so
  "clean" means "checked and clear", never "nothing derived".

## A small, nontrivial example

```python
from pystrider import intake_function, analyze, choose_repair

src = """
def pipeline(raw):
    data = validate(raw)   # data is now the validated (non-None) result
    data = raw             # ...but a stray second assignment clobbers it with the raw input
    return data.rows()     # so on a None input this dereferences None
"""

ik = intake_function(src)

# SUPPOSE the input is None, then symbolically RUN the semantics (no pattern matching):
[outcome] = analyze(ik, {"raw": "none"})
print(outcome.headline())
#   assuming raw=None: data.rows (line 5) -> AttributeError

# every conclusion carries its real UGM provenance trace (abbreviated):
print("\n".join(outcome.trace))
#   attr9 raises attribute_error   <- rule.?e.raises.attribute_error
#     e8 eval_to none              <- rule.?e.eval_to      (data is None at the deref's program point)
#       c_p2_data has_value none   <- rule.?c2.has_value   (the LAST write — data = raw — wins)
#   ...

# retrieve + materialize + verify + CHOOSE a repair (smallest / most-local wins):
sel = choose_repair(ik, {"raw": "none"}, outcome)
print(sel.winner.v2_source)
#   def pipeline(raw):
#       data = validate(raw)
#       data = raw
#       if data is not None:
#           return data.rows()
```

This is exactly the case a "one variable, one value" (SSA) model or a pattern matcher gets wrong:
`data` is assigned twice, and only the **last** write (`data = raw`) reaches the deref. pystrider
threads value through a per-`(program-point, variable)` cell lattice, so it reads the value that is
actually live at the return — and if you **swap the two assignments** (`data = raw` first), the
outcome soundly disappears (no false positive).

For the multi-function / inter-procedural version, see [`demos/03_session_interprocedural.py`](https://github.com/ercasta/pystrider/blob/main/demos/03_session_interprocedural.py).

## Fixing, not just finding

The point of running the semantics is that it also tells you how to *repair* the code — and
`repair_all` drives that to a fixpoint, fixing **every** outcome (across all effects) one verified
edit at a time:

```python
from pystrider import intake_function, repair_all

buggy = """
def process(cfg, data):
    conn = cfg
    a = conn.open()      # AttributeError if cfg is None
    rows = data
    return rows          # returns None if data is None   (a different bug, different effect)
"""

plan = repair_all(intake_function(buggy), {"cfg": "none", "data": "none"})

print("\n".join(plan.summary()))
#   2 edit(s) -> repaired to clean
#     1. fix 'conn.open' (attribute_error, line 4) via guard_base [fit 1.00] -> 1 left
#     2. fix 'return rows' (returns_none, line 6) via coalesce_or [fit 1.00] -> 0 left

print(plan.source)          # the edited, now-clean Python you can apply
#   def process(cfg, data):
#       conn = cfg
#       if conn is not None:
#           a = conn.open()
#       rows = data
#       return rows or {}
```

Each candidate edit is **materialized as real Python** (an AST rewrite) and accepted only if
re-analyzing the edited source shows it removed the target **and introduced no new problem**
(regression-checking) — the graded-best survivor is applied, then the loop re-analyzes and repeats
until the function is clean (or reports an honest `stuck`). So the fix is trusted because the code
*re-runs clean*, not because an operator claimed it would. `plan.source` is source you can apply;
`plan.steps` is the audit log of what changed and why. (For a single site with the full CHOOSE
trace, use `choose_repair`, above.)

## A third axis: crash → root cause (diagnosis)

Analysis reads code; **diagnosis explains a crash**. Analysis runs the loop
*forward* — you SUPPOSE an input and it derives what happens. But a real debugging session starts at
the other end: you have a **traceback** — `AttributeError`, one line — and *no* input, and you must
work out *what must have been true* for that to happen. That is **abduction**, and it is the analysis
loop run **backwards over the hypothesis space**. A probe
([`experiments/diagnosis.py`](https://github.com/ercasta/pystrider/blob/main/experiments/diagnosis.py)) proves it:

```python
from experiments.diagnosis import Observation, diagnose, diagnose_and_fix

src = (
    "def pipeline(raw):\n"
    "    data = validate(raw)\n"     # data is the validated (non-None) result ...
    "    data = raw\n"               # ... clobbered by the raw input
    "    return data.rows()\n"       # line 4: this is where AttributeError was seen
)

# given ONLY "AttributeError at line 4" — no input — abduce the cause:
dx = diagnose(Observation(source=src, line=4, exc="AttributeError"))
print(dx.explanation()[0])
#   root cause: AttributeError at line 4 happens when raw is None

# ...and hand the abduced cause straight to the productized repair axis:
_dx, plan = diagnose_and_fix(Observation(source=src, line=4, exc="AttributeError"))
print(plan.summary()[0])            # 1 edit(s) -> repaired to clean
```

The mirror is exact — same firmware, run the other way:

| analysis (forward, productized) | diagnosis (this probe) |
|---|---|
| SUPPOSE input → derive every outcome | OBSERVE one outcome → abduce the inputs that entail it |
| the value hypothesis is **given** | the value hypothesis is the **unknown**, solved for |
| RECORD trace = why this input crashes | RECORD trace = why **this** crash happened (the reaching write) |
| CHOOSE the graded-best **repair** | CHOOSE the graded-best **explanation** (Occam: the most specific cause) |
| verify a repair by re-execution | verify a cause by re-execution (the *same* forward analyzer) |

Three moves make it real. **(1) The root cause is *abduced*, not supplied** — `analyze` requires you
to name the None parameter; diagnosis is handed only the crash and searches the hypothesis space
(subsets of parameters supposed None, minimal-first) for the input that reproduces it, recovering
`raw` plus the reaching-write chain that carried its None past the *second* assignment to the deref.
**(2) CHOOSE picks the minimal cause** — many hypotheses reproduce a crash ("everything is None"
always does); the *root* cause is the smallest set that still does, so an Occam prior is realized as a
graded selection over the public CHOOSE firmware, a single-variable cause outgrading a
supposing-everything one. **(3) A suspect is exonerated by re-execution** — in a two-parameter
`process(cfg, data)` where each None crashes a *different* line, the cause of the line-3 crash is
`cfg` alone: `data`'s None derives a line-*5* crash, so the forward semantics never derive the
observed outcome under it and it never enters the candidate set (trust by the checker, as everywhere
else). And because the abduced cause is a value hypothesis of exactly `repair_all`'s shape,
**"understand the root cause" flows straight into "and fix it, verified by re-execution"** — the front
half of a debugger wired to the productized repair axis as its back half, with no new machinery. Still
a probe (see [`tests/test_diagnosis.py`](https://github.com/ercasta/pystrider/blob/main/tests/test_diagnosis.py)); run it:
`python -m experiments.diagnosis`.

## A fourth axis: does the code implement the policy? (conformance)

Analysis asks "does this code have a bug?"; **conformance asks "does this code do what the *business
rule* says?"** — and answers with a machine-checkable proof. A business **policy** (in business
vocabulary) and the **code** (in its own vocabulary) live in one graph, joined *only* by a small
declarative **bridge**; scenarios are swept from the policy's own boundary constants; and where the two
disagree, a **`diverges`** fact is derived — with a two-world proof and a spec-directed fix. This is the
one thing neither `pyright`, nor CodeQL, nor a DMN validator, nor an LLM produces: *a checkable proof
that a piece of code implements a piece of policy — and a verified minimal edit when it doesn't* (a
probe: [`experiments/conformance_strider.py`](https://github.com/ercasta/pystrider/blob/main/experiments/conformance_strider.py)).

```python
from experiments.conformance_strider import Model, check_and_repair

# a business POLICY and its CODE speak DIFFERENT vocabularies, joined ONLY by a bridge:
#   policy (business):  a member gets_discount when member_tier is premium and order_spend is over 50
#   code   (code):      def discount(rank, amount): return rank == 'gold' and amount > 100   # ← bug
#   bridge:  member_tier→rank, order_spend→amount, premium→gold, discount_true→gets_discount

r = check_and_repair(Model())
print(r.divergences)
#   ['s_premium_100', 's_premium_51', 's_premium_99']
#   (the code DENIES a discount the policy GRANTS, for premium members with spend in (50, 100])

print(r.winner, "→ code_threshold", r.repaired.code_threshold, "| re-sweep:", r.residual_after_repair)
#   align_threshold → code_threshold 50 | re-sweep: []   (PROVEN: the repaired code implements the policy)
```

Three moves make it real. **(1) The comparison is a JOIN, not glue** — `diverges` is an ordinary
derived fact (`?sc diverges yes when ?sc policy_outcome ?x and ?sc code_outcome ?y and not ?x
same_outcome ?y`), so it is queryable and explainable, unlike the brittle imperative glue any
two-tool (rules-engine + tests) architecture would need. **(2) The bridge is IN the proof** — the
policy and code share no vocabulary; the `why {scenario} diverges` trace interleaves the business-rule
firing (`policy_grants ← member_tier premium`), the code-logic firing (`code_return discount_false`),
*and* the bridge rule translating between them (`discount_false bridges_outcome no_discount`). Swap the
bridge and the same policy re-targets a different implementation. **(3) Repair is spec-DIRECTED and
proven by re-sweep** — `align_threshold` reads the policy's constant and rewrites the code's, then
re-sweeps to *zero* divergence (chosen over a decoy edit that fails verification); semantics
preservation ("the code's outcomes equal the policy's on every swept scenario") is the verification
condition by construction. Run it: `python -m experiments.conformance_strider`.

**The value domain that makes this possible — and where it points.** Conformance needs the code to
reason about **constants and comparisons** (`amount > 100`), which the None-analysis domain
(`{none, object}`) cannot express. A companion probe
([`experiments/intake_growth.py`](https://github.com/ercasta/pystrider/blob/main/experiments/intake_growth.py)) grows exactly that: it intakes a real
Python decision function, reifies its constants + comparisons as **data**, and derives its return value
by reasoning — pinned against Python execution itself as the oracle. That is the first step of a larger
idea ([`docs/api_absorption_design.md`](api_absorption_design.md)): move analysis *knowledge* out
of the rules and into the graph as facts generic rules consume — so that a library's API surface
(`dict.get returns_optional`, `DataFrame has_method groupby`) can be **absorbed as data**, and the
*same* bridge that maps business terms onto code names maps them onto absorbed library names. Run it:
`python -m experiments.intake_growth`.

### Absorbing a real library, and a bug class it unlocks

That idea is now built: `pystrider.absorb`
reflects a live, annotated module's declared surface into matchable facts — `<Type>.<method>
returns_optional yes|no`, `<Type> has_method <method>` — reading only type hints, never running library
code, and *conservatively* (an undecidable return is **omitted and surfaced**, never guessed). It runs
on a real dependency: `absorb(textual.Widget)` yields 73 optional-returning methods, and a **generated**
`returns_optional` fact drives the *unchanged* None-deref effect. On the same facts a second
library-shaped effect falls out — **`method_not_found`**: a method call whose receiver type (given, or
inferred through an absorbed return) does not declare the method
([`experiments/api_absorption.py`](https://github.com/ercasta/pystrider/blob/main/experiments/api_absorption.py), `pystrider/absorb.py`).

### Checking the knowledge itself: rulestrider

Because rules are just more graph structure, the same
sweep-and-derive loop turns on a **rule bank** — the KB-ingestion QA gate that makes LLM-authored policy
trustworthy. A probe ([`experiments/rulestrider.py`](https://github.com/ercasta/pystrider/blob/main/experiments/rulestrider.py)) plants a **dropped body
condition** in a CNL discount policy (the loyalty rule ships requiring only `big_spender`, not `premium
AND big_spender`), sweeps an expected-outcome suite, and catches the resulting **over-firing** on the one
scenario that isolates it — with the `why`-trace showing the rule firing with the dropped condition
*absent*: the provenance is the diagnosis. Run it: `python -m experiments.rulestrider`.

## Layout

| Path | Role |
|---|---|
| `pystrider/intake.py` | the §8 code-intake tool — `ast` → graph facts (structure only, *not* CNL); CFG + `(state×var)` cell lattice; per-function `namespace` for shared graphs |
| `pystrider/semantics.cnl` | the operational semantics — Horn rules, authored CNL data (`semantics.py` loads it) |
| `pystrider/analysis.py` | the hypothesis loop on the public UGM firmware (`suppose(commit=False)` / `ask_goal`) + `analyze` / `analyze_return_none` / `analyze_all` / `choose_repair` / `repair_all` (whole-function auto-fix) + `caveats` (surface unmodelled statements) |
| `pystrider/absorb.py` | the API **absorber** — reflect a live module's declared type surface into `has_method` / `returns_optional` / `returns` facts (reads hints only, never runs library code; conservative) |
| `pystrider/session.py` | a **Session** — several functions in one graph, per-function focus, cross-call value-flow linking |
| `pystrider/operators.py` + `operators.cnl` | effect-keyed transformation-operator library, retrieved by backward-CHAIN |
| `pystrider/transform.py` | transformation mechanism — rewrites the AST to materialize an edit as real source |
| `grammapy/` | the in-repo **composition algebra** — `Choice` / `Accumulate` / `Scope` / `Fold` + §12 `resolve`, each soundness check a CNL rule-module over the graph (`_cnl.py`); the "compose" half of the generation loop |
| `pystrider/demo.py` | end-to-end packaged walkthrough (`python -m pystrider.demo`) |
| `demos/playground/` | the **playground** — four swappable CNL blocks (business / UX / library / bridge) brewed into a runnable, Pilot-verified Textual checkout UI; edit a knob and the UI re-derives ([`README`](https://github.com/ercasta/pystrider/blob/main/demos/playground/README.md)) |
| `demos/` | five focused, runnable walkthroughs (`python demos/run.py`) — see [`demos/README.md`](https://github.com/ercasta/pystrider/blob/main/demos/README.md) |
| `experiments/` | feasibility probes. **The humble writer (patterns as rules):** `pattern_compose.py` (compose patterns by intent, repair by intent-mismatch), `compose_recover.py` / `scope_recover.py` (compose → check → recover, gated by grammapy + re-execution), `footprint_synthesis.py` / `footprint_scalability.py` / `footprint_honesty.py` (derive a fragment's write-footprint from code + know when it can't). **Understanding real code:** `understand_robustness.py` / `understand_semantic.py` / `understand_curve.py` / `understand_partial.py` / `understand_partial_curve.py` / `base_tier.py` (recognize code by aspect, over the stdlib corpus). **Scale + limit-tests:** `interaction_scaling.py` / `retarget_family.py` (the win at scale), `soundness_redteam.py` / `economic_test.py` / `composability_coverage.py` / `membrane_vagueness.py` (the thesis pushed to its edges). **Other axes:** `diagnosis.py` (crash → root cause), `conformance_strider.py` (code⟷policy across a bridge), `versioned_recovery.py` / `versioned_software.py` (a program as a build DAG), `intake_growth.py`, `api_absorption.py` (**absorb** a real library + the `method_not_found` effect), `rulestrider.py` (anomaly-check a rule bank) |
| `tests/` | behaviour pins (284 green) across 42 files — the productized loop (`test_spike.py`, `test_session.py`, `test_effects.py`, `test_repair.py`, `test_repair_verification.py`, `test_caveats.py`, …), the grammapy combinators (`test_resolution.py`, `test_scope.py`, `test_choice.py`, `test_fold.py`, `test_disjointness.py`), the humble-writer + understanding probes (`test_pattern_compose.py`, `test_footprint*.py`, `test_compose_recover.py`, `test_understand_*.py`, `test_base_tier.py`), the scale + limit-tests (`test_interaction_scaling.py`, `test_retarget_family.py`, `test_membrane_vagueness.py`, …), and the KB pipeline (`test_absorb.py`, `test_method_not_found.py`, `test_rulestrider.py`) |
| `docs/` | the strategic **roadmap** (`roadmap.md`), the design (`code_reasoning_design.md`), the **understanding findings** (`understanding_findings.md` — the base/concept/intent tiers + limit-tests), the **oracle contracts** (`oracle_contracts.md` — what each verdict proves), the API-absorption direction (`api_absorption_design.md`) |

## Run

```bash
pip install -e ../ugm -e .    # the ugm sibling + this package (grammapy ships in-repo, no extra install)
pip install textual                  # only for the playground (the driven Textual app)
python -m pystrider.demo             # the packaged analysis/repair walkthrough

# the generation loop (reason → compose → emit → drive):
python demos/playground/playground.py      # a runnable Textual app, verified by driving; turn a knob, re-derive

# the humble writer, understanding, and scale:
python -m experiments.compose_recover      # compose → check → recover, gated by grammapy + re-execution
python -m experiments.interaction_scaling  # author O(F) vs interaction-audit O(F^2), borne by the checker
python -m experiments.retarget_family      # the same decisions drive two libraries, both driven green

# the other reasoning directions and the KB pipeline:
python -m experiments.diagnosis            # crash → root cause (abduction) + fix
python -m experiments.conformance_strider  # code ⟷ policy conformance across a vocabulary bridge
python -m experiments.api_absorption       # absorb a real library + the method_not_found effect
python -m experiments.rulestrider          # anomaly-check a CNL rule bank (KB-ingestion QA)

python demos/run.py                  # the focused analysis/repair demos
pytest -q                            # the behaviour pins (284 green)
```
