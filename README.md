# pystrider

A **dynamic, hypothesis-driven code analyzer, bug-fixer, and code generator** built on the [Universal Graph Machine](https://github.com/ercasta/Universal-Graph-Machine) library.
Instead of matching static bug patterns, it reasons about a Python function the way a person does:
*suppose* a value for a parameter, symbolically *run* the code by applying an operational semantics
expressed as UGM rules, and read what *happens* — with a human-readable trace behind every
conclusion. Then it *repairs* the code and *verifies* the fix by re-running the analysis.

The same firmware runs in **both directions**. Reading code (**analysis**) is the productized loop
above. Writing code (**synthesis**) is its mirror — a succinct spec *expanded* by CNL rules into
real Python, then *verified by re-execution* exactly as a repair is. That third axis is proven
end-to-end as a probe (see [_A third axis: spec → code_](#a-third-axis-spec--code-synthesis)).

pystrider owns **no** engine code. Intake materializes graph structure from `ast`; everything
downstream reasons through the public UGM firmware (`suppose` / `ask_goal` / `choose`).

## What it does (today)

The vertical loop is proven and productized across four analysis/repair slices; a **third axis —
spec → code synthesis** — is proven across six probes (compositional codegen from a business rule,
control-flow synthesis gated by the analyzer, multi-function synthesis verified cross-call, and the
call-graph shape itself), with its shared **selection loop now productized** in `pystrider/emit.py`.
A **fourth axis — crash → root cause (diagnosis)** is proven as a seventh probe: the loop run backwards
over the *hypothesis* space, abducing the input that reproduces an observed exception, then handing the
cause to the repair axis. All green (138 tests):

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
- **A third axis — spec → code.** The same SUPPOSE / CHAIN / CHOOSE / RECORD firmware runs in
  **reverse**: a terse spec is *expanded* by CNL refinement rules into real Python and *verified by
  re-execution*. Proven across six probes ([_below_](#a-third-axis-spec--code-synthesis)); the shared
  **selection loop is now productized** in [`pystrider/emit.py`](pystrider/emit.py) (`select` /
  `verify_clean` + `emit.cnl`) — the §8 boundary run in reverse.

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

For the multi-function / inter-procedural version, see [`demos/03_session_interprocedural.py`](demos/03_session_interprocedural.py).

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

## A third axis: spec → code (synthesis)

Analysis reads code; **synthesis writes it** — and it is the *same loop run backwards*, over the
same firmware:

| analysis (productized) | synthesis (this probe) |
|---|---|
| `ast → facts` (intake, a tool) | `spec-facts → ast → source` (an *emit* tool — the boundary in reverse) |
| operational semantics as rules | **refinement** rules *expand* a succinct spec |
| operator library, keyed by *effect prevented* | skeleton library, keyed by *intent realized* |
| SUPPOSE → CHAIN → **CHOOSE** a repair | (spec) → CHAIN refine → **CHOOSE** an expansion |
| RECORD → execution trace | RECORD → **spec→code rationale** trace |
| verify a repair by re-execution | verify a spec by re-execution (the *same* analyzer) |

```python
from experiments.spec_synthesis import Spec, synthesize

base = dict(name="lookup_spec", intent="lookup_with_default", fn_name="lookup", input_var="v")

# a lenient spec — "return the input, or a non-None {} default; never None":
lenient = synthesize(Spec(**base))
print(lenient.winner, "→", lenient.source.splitlines()[-1].strip())
#   coalesce_or → return v or {}                    (the most COMPACT realizer wins)

# one stricter word — ALSO preserve a non-None input unchanged:
strict = synthesize(Spec(**base, strict=True))
print(strict.winner, "→", strict.source.splitlines()[-1].strip())
#   coalesce_ifexp → return v if v is not None else {}     (the winner FLIPS)
```

The flip is the interesting part. `return v or {}` and `return v if v is not None else {}` are
**not** equivalent: on a *falsy but non-None* input (`0`, `""`, `[]`), `v or {}` silently returns
`{}` — it fails to *preserve* the input. So the moment the spec also requires `preserves_input`, the
compact form stops being a realizer at all, and CHOOSE must pick the explicit ifexp — the refinement
rules handle the **conjunction of requirements** (a skeleton must provide *every* one) as stratified
negation. The generated code is trusted only because it is **checked two ways**: `nonnull_return`
**symbolically** (re-intake + the existing `analyze_return_none`) and `preserves_input`
**concretely** (running the emitted function on a falsy sentinel — the design's concrete-exec tool in
miniature, safe on our own pure skeletons). `coalesce_or` *passes* the symbolic check yet *fails* the
concrete one, which is exactly why the strict spec excludes it — the rule-level annotation is
validated by execution, never merely trusted.

Like `experiments/state_threading.py`, this is a **probe** — it re-confirms the project's core
constraint (rules cannot mint fresh nodes, so the emit tool pre-mints a bounded skeleton pool and the
rules only *select*; the pool size is the synthesis fuel budget, the mirror of the unroll budget) and
is not yet productized into the package. Run it: `python -m experiments.spec_synthesis`.

### Going compositional: a business rule, and understanding the result

`spec_synthesis` chose among whole-function *templates*. A follow-on probe
([`experiments/codegen_understand.py`](experiments/codegen_understand.py)) pushes the axis two steps
further — from a **business rule** to code by *recursive subgoal expansion*, and back again by
*recognition*:

```python
from experiments.codegen_understand import Spec, synthesize, recognize

base = dict(name="accrual_spec", intent="accrual", fn_name="compute_accrual")

# "compute accrual" (principal * rate * days / 365) decomposes into a subgoal tree of recipes,
# written BOTTOM-TO-TOP and verified by re-execution. Lenient spec -> the compact inline form:
print(synthesize(Spec(**base)).winner)          # plan_inline   (accrual = principal*rate*days/365)

# one word (`readable`) requires `named_steps` -> the winner FLIPS to named intermediates:
r = synthesize(Spec(**base, readable=True))
print(r.winner)                                 # plan_stepwise (annual_interest, day_fraction, ...)

# UNDERSTANDING is synthesis run backwards: recognize code the system itself generated ->
print(recognize(Spec(**base, readable=True), "plan_stepwise", "compute_accrual"))
#   ['compute_accrual computes accrual']        (the business term bridged back to the code)
```

The **readability flip** is the compositional mirror of the strictness flip above: two decompositions
compute the *same number*, so CHOOSE prefers the compact one — until an added requirement
(`named_steps`) excludes it, exactly as `preserves_input` excluded `return v or {}`. The recursive
subgoal expansion is checked as stratified Datalog (a plan is `complete` iff every sub-need bottoms
out at a parameter), the winner is emitted leaves-first, and it is trusted only because it
**re-executes** to the accrual formula. Recognition adds one rule to attribute the generated function
`computes accrual`; a function the system did *not* generate has no fingerprint, so the fact is
**supplied directly in CNL** (`mystery is_a sort_function`) — the round-trip escape hatch. Still a
probe. Run it: `python -m experiments.codegen_understand`.

### Control flow, minted on demand and verified by the analyzer

The next frontier is code that needs a **conditional** — and whether the pre-minted pool then blows
up. A third synthesis probe ([`experiments/controlflow_synthesis.py`](experiments/controlflow_synthesis.py))
synthesizes a *total* `fetch(x)` (never raise, never return None) and answers both worries:

```python
from experiments.controlflow_synthesis import Spec, synthesize

r = synthesize(Spec(name="fetch_spec", fn_name="fetch", input_var="x"))
print(r.winner, "| minted", r.minted, "of", r.eager_pool, "| verified", r.verified)
#   s_guarded | minted 5 of 8 | verified True
print(r.source)
#   def fetch(x):
#       if x is not None:
#           return x.value
#       return {}
```

Three results. **(1) Control flow is synthesizable** under the no-rule-mint rule: the guard is one
more pre-minted *skeleton with holes* the tool fills (exactly as intake pre-mints an unrolled loop's
state chain) — rules only select it. **(2) The pool is minted demand-driven**, so control flow does
*not* blow it up: strategies are minted one goal-layer at a time and an out-competed branch's whole
sub-tree is never minted (here 5 nodes vs. the 8 an eager pre-mint would materialize — the saved 3
are the un-explored cross-product). This is the concrete answer to "would letting rules mint fresh
nodes help?" — **no**; lazy minting *in the tool* is the lever, with no ugm change. **(3) Verification
gates selection using the productized analyzer as the oracle**: CHOOSE prefers the compact
`return x.value`, but the real `analyze` rejects it (`AttributeError` under `x=None`), so synthesis
falls back to the guarded form that `analyze`/`analyze_return_none` clear. The generator proposes; the
analyzer disposes — synthesis is verified by re-running the *same* productized analysis loop, both
directions on one firmware. Run it: `python -m experiments.controlflow_synthesis`.

### Across a call boundary: emit a helper, verify cross-call

The frontier after that is a subgoal satisfied by *emitting a helper and calling it* — correctness
now spans a **call boundary**. A fourth synthesis probe
([`experiments/multifunction_synthesis.py`](experiments/multifunction_synthesis.py)) synthesizes a
total `process(x)` that delegates to a helper `extract(v)`, verified through the **productized
inter-procedural analyzer** (`Session.analyze_across_call`):

```python
from experiments.multifunction_synthesis import Spec, synthesize

r = synthesize(Spec(name="process_spec", caller="process", helper="extract", input_var="x"))
print(r.winner, "| verified", r.verified)          # guard_caller | verified True
print(r.helper_src)   # def extract(v):  return v.value
print(r.caller_src)   # def process(x):  if x is not None: return extract(x) \n  return {}
```

Two emitted functions, loaded into a `Session` (each namespaced, identity by `(function, name)`), the
call `link_calls`-wired, and `analyze_across_call` seeds `x=None` and reads outcomes *inside the
callee* — the value crosses the boundary through the exact machinery the analyzer ships. The
verification is **path-sensitive across the call**: CHOOSE prefers the compact `naive` (delegate +
deref) and the analyzer rejects it (None genuinely crosses into the deref); but it **certifies**
`guard_caller` (guard, *then* delegate), because `Session.link_calls` stamps `refine_nonnull` on a
call inside `if arg is not None:` and a refined cross-call assign carries only the non-None value into
the callee — so the compact caller-side guard *wins* over the defensive `total_helper`. This was the
axis's sharpest move: an earlier *path-insensitive* link rejected `guard_caller` too (a false
positive) — **synthesis surfaced that precision boundary, and the refinement (now productized, pinned
in `tests/test_session.py`) moved it**, while a real cross-call bug (`naive`) stays caught. Because
each function is emitted independently and joined only inside the `Session`, no shared *synthesis*
graph is built, so the ugm addressing footgun is routed around, not blocked on. Run it:
`python -m experiments.multifunction_synthesis`.

### Should rules mint the pool? An informed choice

All four probes above pre-mint their candidate pool in the emit *tool* and let rules only *select* —
originally a workaround for "ugm rules cannot mint fresh nodes". That constraint was since **resolved
upstream** (genuine per-match minting via the skolem `n?`), so a fifth probe
([`experiments/minting_comparison.py`](experiments/minting_comparison.py)) asks the fair question it
reopens — *should* the pool now be grown by rules? It generates a depth-`k` value-threading chain
**both** ways (a tool-minted pool with stable names, and a rule-grown pool where a one-line skolem
rule mints each successor); both emit **byte-identical, verified** source. The difference is the part
that matters: rule-minted nodes are name-**collided** (identity is structural, so emit/verify must
thread by id — `nodes_named("n")` is `k`-way ambiguous), and the fuel bound is still external
(`max_rounds`). **Conclusion:** rule-minting is right for open-ended structure the rules reason over
*in place*; **tool-minting stays right for synthesis targets you must emit, name, and verify** — now
by reason, not by force. It flips only when ugm gains id-addressed goals. Run it:
`python -m experiments.minting_comparison`.

### Synthesizing the call-graph shape

The deepest frontier is making the program's *shape* — how many functions and the call edges among
them — the synthesis decision, which answers the question the codegen sketch opened with: *when do we
put statements in a subfunction vs a sequence?* A sixth probe
([`experiments/callgraph_synthesis.py`](experiments/callgraph_synthesis.py)) synthesizes `report(x)`,
a computation with a **shared** sub-part `normalize(x)`, and lets DRY requirements force the factoring:

```python
from experiments.callgraph_synthesis import Spec, synthesize

for spec in [Spec("r"), Spec("r", dry_source=True), Spec("r", dry_source=True, dry_runtime=True)]:
    r = synthesize(spec)
    print(r.winner, "->", r.graph["report"])
#   inline_dup   -> []                                   (1 function, 0 call edges)
#   helper_twice -> ['scale', 'shift', 'normalize', 'normalize']   (normalize called at 2 sites)
#   helper_once  -> ['normalize', 'scale', 'shift']      (normalize bound once, reused)
```

All three shapes compute the same figure (pinned by re-execution), so the choice is purely
**structural**. Adding `dry_source` (no duplicated logic) forces a shared `normalize` helper (0 → 3
helpers); adding `dry_runtime` (compute it once) flips the winner again to the shape that reuses the
shared *result* (2 call sites → 1). The epistemic move holds: a shape only *claims* its structure, and
verification **re-parses the emitted program** to derive the real call graph from the AST and checks
it against the spec's requirements — trust by inspection of the artifact, never the claim. Run it:
`python -m experiments.callgraph_synthesis`.

## A fourth axis: crash → root cause (diagnosis)

Analysis reads code; synthesis writes it; **diagnosis explains a crash**. Analysis runs the loop
*forward* — you SUPPOSE an input and it derives what happens. But a real debugging session starts at
the other end: you have a **traceback** — `AttributeError`, one line — and *no* input, and you must
work out *what must have been true* for that to happen. That is **abduction**, and it is the analysis
loop run **backwards over the hypothesis space** (as synthesis is it run backwards over the *code*
space). A seventh probe ([`experiments/diagnosis.py`](experiments/diagnosis.py)) proves it:

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
a probe (see [`tests/test_diagnosis.py`](tests/test_diagnosis.py)); run it:
`python -m experiments.diagnosis`.

## Layout

| Path | Role |
|---|---|
| `pystrider/intake.py` | the §8 code-intake tool — `ast` → graph facts (structure only, *not* CNL); CFG + `(state×var)` cell lattice; per-function `namespace` for shared graphs |
| `pystrider/semantics.cnl` | the operational semantics — Horn rules, authored CNL data (`semantics.py` loads it) |
| `pystrider/analysis.py` | the hypothesis loop on the public UGM firmware (`suppose(commit=False)` / `ask_goal`) + `analyze` / `analyze_return_none` / `analyze_all` / `choose_repair` / `repair_all` (whole-function auto-fix) + `caveats` (surface unmodelled statements) |
| `pystrider/emit.py` + `emit.cnl` | the §8 **emit** boundary (intake in reverse), productized: `select` (realize-iff-provides-all-required + CHOOSE) / `verify_clean`; the realization rule bank as CNL data |
| `pystrider/session.py` | a **Session** — several functions in one graph, per-function focus, cross-call value-flow linking |
| `pystrider/operators.py` + `operators.cnl` | effect-keyed transformation-operator library, retrieved by backward-CHAIN |
| `pystrider/transform.py` | transformation mechanism — rewrites the AST to materialize an edit as real source |
| `pystrider/demo.py` | end-to-end packaged walkthrough (`python -m pystrider.demo`) |
| `demos/` | five focused, runnable walkthroughs (`python demos/run.py`) — see [`demos/README.md`](demos/README.md) |
| `experiments/` | feasibility probes — `state_threading.py` (state-succession), `spec_synthesis.py` (the spec→code synthesis axis), `codegen_understand.py` (compositional codegen from a business rule + round-trip recognition), `controlflow_synthesis.py` (control-flow synthesis, demand-driven minting, analyzer-gated), `multifunction_synthesis.py` (emit + call a helper, verified cross-call), `minting_comparison.py` (rule-grown vs tool-minted candidate pools), `callgraph_synthesis.py` (synthesizing the call-graph shape / factoring), and `diagnosis.py` (the fourth axis — abduce a crash's root cause from an observed exception, then fix) |
| `tests/` | behaviour pins (138 green): `test_spike.py`, `test_state_threading.py`, `test_session.py`, `test_effects.py`, `test_repair.py`, `test_spec_synthesis.py`, `test_codegen_understand.py`, `test_controlflow_synthesis.py`, `test_multifunction_synthesis.py`, `test_minting_comparison.py`, `test_callgraph_synthesis.py`, `test_diagnosis.py`, `test_caveats.py`, `test_emit.py` |
| `docs/` | the design (`code_reasoning_design.md`), the plan (`implementation_plan.md`), the spike findings |

## Run

```bash
pip install -e ../ugm -e .    # the ugm sibling + this package
python -m pystrider.demo             # the packaged end-to-end walkthrough
python demos/run.py                  # the five focused demos
python -m experiments.spec_synthesis # the spec → code synthesis probe (the third axis)
python -m experiments.codegen_understand # compositional codegen from a business rule + recognition
python -m experiments.controlflow_synthesis # control-flow synthesis, demand-driven + analyzer-gated
python -m experiments.multifunction_synthesis # emit + call a helper, verified cross-call
python -m experiments.minting_comparison # rule-grown vs tool-minted candidate pools
python -m experiments.callgraph_synthesis # synthesizing the call-graph shape / factoring
python -m experiments.diagnosis      # the fourth axis: crash -> root cause (abduction) + fix
pytest -q                            # the behaviour pins (138 green)
```
