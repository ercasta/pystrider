"""Feasibility probe — spec -> code by CNL rule expansion (the SYNTHESIS axis).

This probe asks the question raised at the start of the post-slice-C session: is there a *third
axis* worth building — a succinct **technical specification** that is EXPANDED by CNL rules into
real code? It is a **probe, not integrated intake/analysis** (mirrors `experiments/state_threading.py`):
it stands up the smallest end-to-end spec->code->verify loop to prove the axis is real before
productizing.

The finding, in one line: **synthesis is the mirror of analysis, and it reuses the whole firmware.**

    analysis  (built)                         synthesis  (this probe)
    ----------------------------------------  ------------------------------------------
    ast  -> facts            (intake, a tool) spec-facts -> ast -> source   (emit, a tool)
    operational semantics as Horn rules       REFINEMENT rules expand a succinct spec
    operator lib keyed by effect PREVENTED    skeleton lib keyed by intent REALIZED
    SUPPOSE value -> CHAIN -> CHOOSE repair    (spec) -> CHAIN refine -> CHOOSE expansion
    RECORD -> execution trace                 RECORD -> spec->code RATIONALE trace
    verify a repair by re-execution           verify a spec by re-execution (SAME analyzer)

The epistemic move that defines this project transfers exactly: the generator is trusted only
because the *analyzer* confirms its output. Here the refinement rules PROPOSE which skeletons
realize the spec (by matching each skeleton's declared `provides` against the spec's derived
`requires`); the existing `analyze_return_none` DISPOSES — it re-intakes the emitted source and
checks the spec really holds. The probe pins that the naive skeleton the rules (correctly) do NOT
retrieve is exactly the one that FAILS verification, so the rule-level `provides` annotation is
validated by execution, never merely trusted.

**The pre-mint constraint reappears (and that is the reassuring part).** Generating fresh code
nodes (new statements, new variables) is the SAME existential-minting wall the state-succession
probe hit: ugm rules cannot Skolem-mint. So, exactly as intake pre-mints the state x var lattice,
the emit tool pre-mints a bounded pool of candidate code SKELETONS; the refinement rules only
*select* among them (CHOOSE grades). The skeleton-pool size IS the synthesis fuel budget, the
mirror of the state-pool = unroll budget. This keeps the honest scope of a first slice at
**template/skeleton synthesis over a tiny intent vocabulary**, not free-form codegen.

Intent used: `lookup_with_default` — return a possibly-None input, or a non-None `{}` fallback,
NEVER None. The naive body `return v` violates the spec (returns None when v is None); the two
realizing skeletons are exactly the coalesce shapes the repair library already ships:
`return v or {}` (compact) and `return v if v is not None else {}` (explicit).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Callable

import ugm as h
from ugm import load_machine_rules, ask_goal, set_candidate, choose, explain_choice

from pystrider.intake import intake_function
from pystrider.analysis import analyze_return_none, Outcome


# --- the succinct spec (DATA) --------------------------------------------------------------

@dataclass(frozen=True)
class Spec:
    """A technical specification, deliberately terse. `intent` names an entry in the skeleton
    library; everything else is a hole the emitter fills. The whole point is that this is SHORT —
    the CNL refinement rules expand `intent` into the concrete requirements code must satisfy."""
    name: str                    # graph id for this spec, e.g. "lookup_spec"
    intent: str                  # "lookup_with_default"
    fn_name: str                 # emitted function name
    input_var: str               # the possibly-None input parameter, e.g. "v"


# --- the emit tool: a BOUNDED pool of pre-minted code skeletons (the §8 boundary, in reverse) ---
# Rules cannot MINT fresh code nodes (the existential-minting wall). So the tool pre-mints the
# candidate bodies; the rules only SELECT among them. Each skeleton declares the features it
# `provides` (matched against the spec's derived `requires`) and emits real source from a spec.

def _fn_source(name: str, arg: str, ret: ast.expr) -> str:
    """Assemble `def name(arg): return <ret>` and unparse to real Python (mirror of intake's ast)."""
    fn = ast.FunctionDef(
        name=name,
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=arg)], vararg=None,
                           kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=[ast.Return(value=ret)], decorator_list=[])
    mod = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(mod)
    return ast.unparse(mod)


def _name(v: str) -> ast.Name:
    return ast.Name(id=v, ctx=ast.Load())


def _empty_dict() -> ast.Dict:
    return ast.Dict(keys=[], values=[])                       # the concrete non-None default `{}`


@dataclass(frozen=True)
class Skeleton:
    name: str                    # graph id / library key
    for_intent: str              # the intent this skeleton is a candidate body for
    provides: frozenset[str]     # the features it guarantees (matched to the spec's `requires`)
    compactness: float           # graded fit dimension (DATA) — smaller/simpler edit is better
    emit: Callable[[Spec], str]  # spec -> real source (the tool mechanism; the only Python here)


SKELETONS: list[Skeleton] = [
    # the naive body — NOT retrieved (provides no nonnull guarantee); pinned to FAIL verification.
    Skeleton("naive", "lookup_with_default", frozenset({"passthrough"}), 1.0,
             lambda sp: _fn_source(sp.fn_name, sp.input_var, _name(sp.input_var))),
    # `return v or {}` — compact realizer (mirror of the coalesce_or repair operator).
    Skeleton("coalesce_or", "lookup_with_default", frozenset({"nonnull_return"}), 1.0,
             lambda sp: _fn_source(sp.fn_name, sp.input_var,
                                   ast.BoolOp(op=ast.Or(), values=[_name(sp.input_var), _empty_dict()]))),
    # `return v if v is not None else {}` — explicit realizer (mirror of coalesce_ifexp); wider edit.
    Skeleton("coalesce_ifexp", "lookup_with_default", frozenset({"nonnull_return"}), 0.7,
             lambda sp: _fn_source(sp.fn_name, sp.input_var, ast.IfExp(
                 test=ast.Compare(left=_name(sp.input_var), ops=[ast.IsNot()],
                                  comparators=[ast.Constant(value=None)]),
                 body=_name(sp.input_var), orelse=_empty_dict()))),
]
_BY_NAME = {s.name: s for s in SKELETONS}


# --- the refinement rules (CNL) — the EXPANSION of a succinct spec ---------------------------
# Two steps, both pure Datalog (they only bind pre-existing skeleton/spec nodes, mint nothing):
#   R1 DECOMPOSE: the intent `lookup_with_default` expands into a concrete required feature.
#   R2 REALIZE:   a skeleton realizes a spec when it is for that intent and provides the feature.
# `who realizes <spec>` backward-CHAINs both — the mirror of `who applies_to <site>` retrieval.
REFINEMENT_RULES = "\n".join([
    "?spec requires nonnull_return when ?spec is_a spec and ?spec intent lookup_with_default",
    "?sk realizes ?spec when ?sk is_a skeleton and ?sk for_intent ?k and ?spec intent ?k "
    "and ?spec requires ?feat and ?sk provides ?feat",
])


def _retrieval_graph(spec: Spec) -> "h.Graph":
    """Materialize the spec + the skeleton library as facts (the one direct-authoring boundary)."""
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    def rel(s: str, p: str, o: str) -> None: g.add_relation(n(s), p, n(o))

    rel(spec.name, "is_a", "spec")
    rel(spec.name, "intent", spec.intent)
    for sk in SKELETONS:
        rel(sk.name, "is_a", "skeleton")
        rel(sk.name, "for_intent", sk.for_intent)
        for feat in sk.provides:
            rel(sk.name, "provides", feat)
    return g


def retrieve(spec: Spec) -> list[Skeleton]:
    """Backward-CHAIN the refinement rules: which skeletons REALIZE this spec? Runs entirely
    through the public `ask_goal` — the mirror of `operators.retrieve`."""
    rules = load_machine_rules(REFINEMENT_RULES)
    g = _retrieval_graph(spec)
    answers = ask_goal(g, f"who realizes {spec.name}", rules)       # "coalesce_or realizes lookup_spec"
    names = {a.split(" ", 1)[0] for a in answers}
    return [_BY_NAME[nm] for nm in names if nm in _BY_NAME]


def realize_trace(spec: Spec, skeleton: str) -> list[str]:
    """The RECORD provenance for WHY a skeleton realizes the spec — a spec->code rationale trace
    (the mirror of the execution trace). Threads back through the derived `requires`."""
    rules = load_machine_rules(REFINEMENT_RULES)
    g = _retrieval_graph(spec)
    return ask_goal(g, f"why {skeleton} realizes {spec.name}", rules)


# --- CHOOSE the graded-best realizer (mirror of analysis._choose) ---------------------------

def choose_skeleton(cands: list[Skeleton]) -> tuple[Skeleton | None, list[str]]:
    """Run the public CHOOSE firmware over realizing skeletons, graded by compactness; return the
    winner + the auditable `explain_choice` trace. Losers are retained (monotone)."""
    g = h.Graph()
    goal = g.add_node("synth_goal")
    node_of: dict[str, Skeleton] = {}
    for c in cands:
        opt = g.add_node(c.name)
        node_of[c.name] = c
        set_candidate(g, goal, opt, c.compactness)
    winners = choose(g, goal, alpha=0.01)
    trace = explain_choice(g, goal)
    return (node_of[g.name(winners[0])] if winners else None), trace


# --- verify by round-trip: emit -> re-intake -> re-analyze (the SAME analyzer) ----------------

def verify(source: str, spec: Spec) -> list[Outcome]:
    """Does the emitted `source` satisfy the spec? Re-intake it and run the existing
    `analyze_return_none` under the worst-case hypothesis (the input IS None). An empty result
    means the spec ('never returns None') holds under execution — trust by the analyzer, not by
    the generator's claim. This is the exact discipline `repair()` lives by, run in reverse."""
    intake = intake_function(source)
    return analyze_return_none(intake, {spec.input_var: "none"})


# --- the whole loop --------------------------------------------------------------------------

@dataclass
class Synthesis:
    spec: Spec
    retrieved: list[str]
    winner: str | None
    source: str
    verified: bool               # emitted winner satisfies the spec under re-execution
    residual: list[Outcome]      # spec violations still present in the winner (want [])
    realize_trace: list[str]     # RECORD: why the winner realizes the spec
    choose_trace: list[str]      # CHOOSE: why it beat the alternatives
    candidates: list[Skeleton] = field(default_factory=list)


def synthesize(spec: Spec) -> Synthesis:
    """spec -> RETRIEVE realizing skeletons -> CHOOSE the graded-best -> EMIT source -> VERIFY by
    re-execution. The full mirror of the analyze/repair loop, over one shared firmware."""
    cands = retrieve(spec)
    winner, choose_trace = choose_skeleton(cands)
    source = winner.emit(spec) if winner else ""
    residual = verify(source, spec) if winner else []
    return Synthesis(
        spec=spec, retrieved=sorted(c.name for c in cands),
        winner=winner.name if winner else None, source=source,
        verified=bool(winner) and not residual, residual=residual,
        realize_trace=realize_trace(spec, winner.name) if winner else [],
        choose_trace=choose_trace, candidates=cands)


# --- live walkthrough ------------------------------------------------------------------------

def main() -> None:
    spec = Spec(name="lookup_spec", intent="lookup_with_default",
                fn_name="lookup", input_var="v")
    print("SPEC (succinct):")
    print(f"  {spec.name}: intent={spec.intent}, fn={spec.fn_name}({spec.input_var}), "
          f"'never return None'\n")

    r = synthesize(spec)
    print(f"REFINE -> realizing skeletons: {r.retrieved}   (naive correctly excluded)\n")
    print(f"CHOOSE -> winner: {r.winner}   (graded-best by compactness)")
    for line in r.choose_trace:
        print(f"    {line}")
    print("\nEMIT (real Python):")
    for line in r.source.splitlines():
        print(f"    {line}")
    print(f"\nVERIFY by re-execution (input IS None): "
          f"{'SPEC HOLDS (no returns_none)' if r.verified else 'SPEC VIOLATED'}")

    naive_src = _BY_NAME["naive"].emit(spec)
    naive_bad = verify(naive_src, spec)
    print(f"  control — naive `return v`: "
          f"{'returns_none FIRES (correctly rejected by the rules)' if naive_bad else '??'}")

    print("\nRECORD -> spec->code rationale (why the winner realizes the spec):")
    for line in r.realize_trace:
        print(f"    {line}")


if __name__ == "__main__":
    main()
