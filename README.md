# pystrider

A **dynamic, hypothesis-driven code analyzer** built on the [Universal Graph Machine](https://github.com/ercasta/Universal-Graph-Machine) library.
Instead of matching static bug patterns, it reasons about a Python function the way a person does:
*suppose* a value for a parameter, symbolically *run* the code by applying an operational semantics
expressed as UGM rules, and read what *happens* — with a human-readable trace behind every
conclusion. Then it *repairs* the code and *verifies* the fix by re-running the analysis.

pystrider owns **no** engine code. Intake materializes graph structure from `ast`; everything
downstream reasons through the public UGM firmware (`suppose` / `ask_goal` / `choose`).

## What it does (today)

The vertical loop is proven and productized across four slices — all green (55 tests):

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

## Layout

| Path | Role |
|---|---|
| `pystrider/intake.py` | the §8 code-intake tool — `ast` → graph facts (structure only, *not* CNL); CFG + `(state×var)` cell lattice; per-function `namespace` for shared graphs |
| `pystrider/semantics.cnl` | the operational semantics — Horn rules, authored CNL data (`semantics.py` loads it) |
| `pystrider/analysis.py` | the hypothesis loop on the public UGM firmware (`suppose(commit=False)` / `ask_goal`) + `analyze` / `analyze_return_none` / `analyze_all` / `choose_repair` / `repair_all` (whole-function auto-fix) |
| `pystrider/session.py` | a **Session** — several functions in one graph, per-function focus, cross-call value-flow linking |
| `pystrider/operators.py` + `operators.cnl` | effect-keyed transformation-operator library, retrieved by backward-CHAIN |
| `pystrider/transform.py` | transformation mechanism — rewrites the AST to materialize an edit as real source |
| `pystrider/demo.py` | end-to-end packaged walkthrough (`python -m pystrider.demo`) |
| `demos/` | five focused, runnable walkthroughs (`python demos/run.py`) — see [`demos/README.md`](demos/README.md) |
| `tests/` | behaviour pins (55 green): `test_spike.py`, `test_state_threading.py`, `test_session.py`, `test_effects.py`, `test_repair.py` |
| `docs/` | the design (`code_reasoning_design.md`), the plan (`implementation_plan.md`), the spike findings |

## Run

```bash
pip install -e ../ugm -e .    # the ugm sibling + this package
python -m pystrider.demo      # the packaged end-to-end walkthrough
python demos/run.py           # the five focused demos
pytest -q                     # the behaviour pins (55 green)
```
