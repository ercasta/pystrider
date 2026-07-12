# pystrider

A **dynamic, hypothesis-driven code analyzer** built on the [`ugm`](../ugm) graph machine.
Instead of matching static bug patterns, it reasons about a Python function the way a human
does: *suppose* a value for a parameter, symbolically *run* the code by applying an operational
semantics expressed as UGM rules, and read what *happens* — with a human-readable trace behind
every conclusion.

This repo is currently a **feasibility spike**. It proves the vertical slice of
[`docs/code_reasoning_design.md`](docs/code_reasoning_design.md); the verdict and evidence are
in [`docs/spike_findings.md`](docs/spike_findings.md) — **the core bet holds.**

## What it does (today)

For `def f(x): y = x; return y.bar()`:

- **intake** (`ast` → AST+CFG facts), then
- under **SUPPOSE `x = None`**, CHAIN the semantics → derive `y.bar` **raises AttributeError**,
- render the **RECORD trace** (real UGM provenance: `x=None → y binds None → y.bar on None → AttributeError`),
- a benign hypothesis (`x = object`) fires **nothing** (no false positive), and
- runs the full **means-ends repair loop**: **retrieves** applicable edit operators from an
  effect-keyed library by backward-CHAIN, **materializes** each as real Python (AST rewrite),
  **verifies** each by re-intaking + re-analyzing the edited source, and **CHOOSEs** the
  smallest/most-local one (`if y is not None: return y.bar()`).

## Layout

| Path | Role |
|---|---|
| `pystrider/intake.py` | the §8 code-intake tool — `ast` → graph facts (materializes structure; *not* CNL) |
| `pystrider/semantics.py` | the operational semantics as 6 Horn rules (machine-rule CNL — data) |
| `pystrider/analysis.py` | the hypothesis loop on the public UGM firmware (`suppose` / `ask_goal`) + `repair` / `choose_repair` |
| `pystrider/operators.py` | effect-keyed transformation-operator library, retrieved by backward-CHAIN |
| `pystrider/transform.py` | transformation mechanism — rewrites the AST to materialize an edit as real source |
| `pystrider/demo.py` | end-to-end five-step walkthrough |
| `tests/test_spike.py` | behaviour pins (6, green) |
| `docs/` | the design sketch + the spike findings |

## Run

```bash
pip install -e ../ugm -e .
python -m pystrider.demo
pytest -q
```

UGM is imported as a library; pystrider owns **no** engine code — the intake tool, the
semantics rule bank, and the analysis loop, nothing below the firmware.
