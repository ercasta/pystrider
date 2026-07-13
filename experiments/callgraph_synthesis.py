"""Feasibility probe — synthesize the CALL-GRAPH SHAPE itself (how a computation is factored).

Every synthesis probe so far fixed the program's *shape*: `controlflow_synthesis` emitted one
function, `multifunction_synthesis` a fixed caller+helper pair. This probe makes the **shape the
synthesis decision** — how many functions to emit and the call edges among them — answering the
question `docs/codegen_understand.md` raised at the outset: *"where and when do we decide whether to
put statements in a subfunction vs a sequence?"* **Verdict: the factoring is synthesizable, driven by
checkable requirements, and verified by re-execution + structural inspection of the emitted graph.**

This probe also **uses the productized selection surface `pystrider.emit`** rather than re-deriving
realize/choose/rules (docs/critique.md #8 — paying down the probe-pile divergence tax): the shape
library is a list of `emit.Candidate`, and `emit.select` does the realize-iff-provides-all-required +
CHOOSE. Only what genuinely varies stays here — the spec, the source-emitting templates, and the
*structural* verification (this probe verifies by re-executing AND by re-parsing the emitted call
graph, not by the None-effect analyzer).

The task has a genuinely shared sub-computation: `report(x)` needs two figures that both consume
`normalize(x)` — `scale(normalize(x))` and `shift(normalize(x))`. Three candidate SHAPES realize the
same behaviour but differ in call-graph structure:

    shape          call graph                                    normalize is…
    -------------  --------------------------------------------  ---------------------------
    inline_dup     {report}                       (0 helpers)    inlined TWICE (duplicated)
    helper_twice   report -> normalize (x2), -> scale, -> shift  a helper, CALLED at 2 sites
    helper_once    report -> normalize (x1), -> scale, -> shift  a helper, called ONCE + bound

All three compute the same number (pinned by re-execution) — so the choice is purely about
*structure*, which is the point. Two spec requirements progressively FORCE more structure (the
mirror of the earlier strict/readable flips, now over the call graph):

  * lenient          -> `inline_dup` wins (most compact — fewest functions).
  * `dry_source`     -> forbids duplicating logic in source => only the helper shapes realize;
                        `helper_twice` wins (a `normalize` helper, called at two sites).
  * `dry_runtime`    -> forbids computing `normalize` twice => ONLY `helper_once` realizes — a flip.

The epistemic move is unchanged and is the honest part: a shape only *claims* `provides factored /
single_eval`; verification **re-parses the emitted program** and DERIVES those properties from the
actual AST (is `normalize` a function? how many call sites?), then checks the winner's real structure
satisfies the spec's requirements — trust by inspection of the artifact, never by the claim. And
every candidate is **run** and must return the same figure, so the shape choice never changes meaning.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

from pystrider import emit


# the two STRUCTURAL features a factoring can provide (checked against the emitted AST, not trusted).
FEATURES = ("factored", "single_eval")


@dataclass(frozen=True)
class Spec:
    name: str                    # graph id, e.g. "report_spec"
    dry_source: bool = False     # forbid duplicating the shared computation's logic in source
    dry_runtime: bool = False    # forbid evaluating the shared computation more than once at run time


def required(spec: Spec) -> set[str]:
    """The structural features this spec's DRY flags demand — `dry_source` a factored helper,
    `dry_runtime` the shared result evaluated once. The domain-specific bit `emit.select` consumes."""
    req: set[str] = set()
    if spec.dry_source:
        req.add("factored")
    if spec.dry_runtime:
        req.add("single_eval")
    return req


# --- the emit tool: pre-minted whole-program SHAPE templates (rules select, tool authors source) ---

_HELPERS = (
    "def normalize(v):\n    return v + 10\n\n"
    "def scale(v):\n    return v * 2\n\n"
    "def shift(v):\n    return v + 1"
)


def _inline_dup(_sp: Spec) -> str:
    """Monolith: everything inlined into `report`; the `normalize` logic (`+ 10`) appears TWICE."""
    return "def report(x):\n    return (x + 10) * 2 + ((x + 10) + 1)"


def _helper_twice(_sp: Spec) -> str:
    """`normalize` factored into a helper, but CALLED at two sites (recomputed at run time)."""
    return _HELPERS + "\n\ndef report(x):\n    return scale(normalize(x)) + shift(normalize(x))"


def _helper_once(_sp: Spec) -> str:
    """`normalize` factored AND its result bound once, then reused — one definition, one evaluation."""
    return _HELPERS + "\n\ndef report(x):\n    n = normalize(x)\n    return scale(n) + shift(n)"


# the shape library as productized `emit.Candidate`s — the pre-minted pool the shared rules select.
SHAPES: list[emit.Candidate] = [
    emit.Candidate("inline_dup", frozenset(), 1.0, _inline_dup),
    emit.Candidate("helper_twice", frozenset({"factored"}), 0.7, _helper_twice),
    emit.Candidate("helper_once", frozenset({"factored", "single_eval"}), 0.6, _helper_once),
]
_BY_NAME = {s.name: s for s in SHAPES}


# --- verify by re-execution + STRUCTURAL re-derivation from the emitted AST --------------------

def call_graph(program: str) -> dict[str, list[str]]:
    """The synthesized call-graph SHAPE, read back from the emitted source: function -> the names it
    calls (with multiplicity). This is the artifact this probe synthesizes."""
    tree = ast.parse(program); g: dict[str, list[str]] = {}
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        g[fn.name] = [c.func.id for c in ast.walk(fn)
                      if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)]
    return g


def actual_features(program: str) -> set[str]:
    """DERIVE the structural features from the emitted AST — never trust the shape's claim. `factored`
    iff `normalize` is its own function; `single_eval` iff it is also invoked at most once."""
    tree = ast.parse(program)
    defs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    ncalls = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "normalize")
    feats: set[str] = set()
    if "normalize" in defs:
        feats.add("factored")
        if ncalls <= 1:
            feats.add("single_eval")
    return feats


def behaves(program: str) -> bool:
    """TRUST BY EXECUTION: every shape must compute the same figure (report(5) == 46), so the
    call-graph choice never changes meaning."""
    ns: dict[str, object] = {}
    exec(compile(program, "<emitted>", "exec"), ns)
    return ns["report"](5) == 46 and ns["report"](0) == 31


# --- the loop: select via the productized surface, emit, verify -------------------------------

@dataclass
class Synthesis:
    spec: Spec
    required: set[str]
    retrieved: list[str]
    winner: str | None
    source: str
    graph: dict[str, list[str]]
    behaves_ok: bool             # re-executes to the same figure
    features_ok: bool            # the winner's REAL structure (from AST) meets the spec's requirements
    verified: bool
    choose_trace: list[str] = field(default_factory=list)


def synthesize(spec: Spec) -> Synthesis:
    req = required(spec)
    sel = emit.select(spec.name, req, SHAPES)                  # <- the productized realize + CHOOSE
    winner = sel.winner_candidate
    source = winner.emit(spec) if winner else ""
    behaves_ok = bool(winner) and behaves(source)
    features_ok = bool(winner) and req <= actual_features(source)   # verified from the emitted AST
    return Synthesis(
        spec=spec, required=req, retrieved=sel.realizing,
        winner=sel.winner, source=source, graph=call_graph(source) if winner else {},
        behaves_ok=behaves_ok, features_ok=features_ok,
        verified=behaves_ok and features_ok, choose_trace=sel.choose_trace)


# --- live walkthrough ------------------------------------------------------------------------

def _shape_summary(g: dict[str, list[str]]) -> str:
    edges = [f"{c}->{callee}" for c, callees in g.items() for callee in callees]
    return f"{len(g)} function(s); edges: {edges or '[]'}"


def _show(spec: Spec, label: str) -> None:
    r = synthesize(spec)
    print(f"=== {label} — requires {sorted(r.required) or '[]'} ===")
    print(f"  select -> realizing shapes: {r.retrieved}   winner: {r.winner}")
    print(f"  call graph: {_shape_summary(r.graph)}")
    print(f"  verify -> behaves={r.behaves_ok}  structure(from AST)={r.features_ok}"
          f"  => {'SPEC HOLDS' if r.verified else 'SPEC VIOLATED'}\n")


def main() -> None:
    base = "report_spec"
    print("Synthesizing the CALL-GRAPH SHAPE — how to factor a computation with a shared sub-part.")
    print("(selection via the productized `pystrider.emit` surface — no re-implemented loop)\n")
    _show(Spec(base), "lenient (compact allowed)")
    _show(Spec(base, dry_source=True), "dry_source (no duplicated logic)")
    _show(Spec(base, dry_source=True, dry_runtime=True), "dry_runtime (compute normalize once)")

    print("The flip is over STRUCTURE: adding `dry_source` forces a `normalize` helper (0 -> 3\n"
          "functions); adding `dry_runtime` forces the shared RESULT to be reused (2 call sites -> 1).\n"
          "Each winner is checked two ways — it re-executes to the same figure, and its structure is\n"
          "re-derived from the emitted AST (not trusted from the shape's claim). Winning source:\n")
    r = synthesize(Spec(base, dry_source=True, dry_runtime=True))
    for line in r.source.splitlines():
        print(f"    {line}")


if __name__ == "__main__":
    main()
