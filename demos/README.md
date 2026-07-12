# pystrider demos

Four runnable, self-contained walkthroughs. Unlike the [UGM demos](../../ugm/demos) (each a
`.cnl` corpus), pystrider's demos are **Python scripts** — the analysis is a program (SUPPOSE a
value, CHAIN the semantics, read the OUTCOME, CHOOSE a repair), not a corpus of facts. Each demo
narrates what the engine does at each step and ends with a **NOW TRY CHANGING IT** section.

```bash
python demos/run.py                          # run all four, in order
python demos/run.py demos/01_none_deref.py   # run just one
python demos/01_none_deref.py                # or run a demo directly
```

The runner adds the repo root to the path, so no install is required (though `pip install -e ../ugm
-e .` is the normal setup).

| # | File | Shows |
|---|------|-------|
| 1 | [`01_none_deref.py`](01_none_deref.py) | **The core loop.** SUPPOSE `env = None` → the semantics derive an `AttributeError` with a real provenance trace → retrieve + verify + CHOOSE a repair. A benign hypothesis fires nothing. |
| 2 | [`02_state_threading.py`](02_state_threading.py) | **Value flow that is correct.** Reassignment (the last write wins), branch-merge (union of both arms), and bounded loop unrolling — every join is a rule derivation, never a Python lattice meet. |
| 3 | [`03_session_interprocedural.py`](03_session_interprocedural.py) | **A Session.** Several functions in ONE shared graph (identity by `(function, source_name)`), each analyzed under its own focus, with a value flowing **across a call boundary** into the callee. |
| 4 | [`04_returns_none.py`](04_returns_none.py) | **A second effect kind.** "Returns None when a non-None was intended" — authored as one more semantics rule + two library operators, reusing the entire retrieve/verify/CHOOSE loop with no new machinery. |

Read them in order: 1 is the whole idea in one screen; 2–4 each add one capability (correct value
flow, cross-function reasoning, a second effect). Every conclusion the demos print is backed by a
UGM derivation — the traces are real provenance, not hand-built strings.

## The shape of every demo

```python
ik   = intake_function(src)          # ast -> AST+CFG graph facts (structure only; no data-flow graph)
outs = analyze(ik, {"x": "none"})    # SUPPOSE x=None, CHAIN the semantics, read the outcome + trace
sel  = choose_repair(ik, {"x": "none"}, outs[0])   # retrieve -> materialize -> verify -> CHOOSE
```

That is the entire public surface: `intake_function`, `analyze` / `analyze_return_none`,
`choose_repair`, and `Session` for the multi-function case. pystrider owns **no** engine code — the
reasoning runs on the public UGM firmware (`suppose` / `ask_goal` / `choose`).
