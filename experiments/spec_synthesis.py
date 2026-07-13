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
because the code is CHECKED, never because the generator claims correctness. This probe checks two
ways — the honest point of the richer example below:

  * SYMBOLIC — the existing `analyze_return_none` re-intakes the emitted source and confirms the
    `nonnull_return` requirement (no returns-None under a None input).
  * CONCRETE — the design's future "concrete-exec tool" in miniature: for a property the symbolic
    domain does NOT track (`preserves_input`: a non-None input must come back unchanged), the probe
    RUNS the emitted function on a falsy-but-non-None sentinel and checks the result. Safe because
    the skeletons are our own pre-minted, pure, side-effect-free bodies.

**The strictness flip (the non-trivial part).** `return v or {}` and `return v if v is not None
else {}` are NOT equivalent: on a *falsy* non-None input (`0`, `""`, `[]`), `v or {}` silently
returns `{}` — it fails to preserve the input. So a spec that requires BOTH `nonnull_return` AND
`preserves_input` must realize ONLY the ifexp form: adding one word (`strict`) to the spec flips
CHOOSE's winner away from the more compact `coalesce_or`, because compactness no longer buys
correctness. This forces the refinement rules to handle a **conjunction of required features** (a
skeleton must provide EVERY one) — expressed as stratified negation (`realizes` iff it `misses`
nothing), the honest hard part. And the CONCRETE check confirms the flip is real: `coalesce_or`
passes the symbolic returns-None check yet returns `{}` for input `0`, which is exactly why the
strict spec excludes it — the rule-level `provides preserves_input` annotation is validated by
execution, never merely trusted.

**The pre-mint constraint reappears (and that is the reassuring part).** Generating fresh code
nodes (new statements, new variables) is the SAME existential-minting wall the state-succession
probe hit: ugm rules cannot Skolem-mint. So, exactly as intake pre-mints the state x var lattice,
the emit tool pre-mints a bounded pool of candidate code SKELETONS; the refinement rules only
*select* among them (CHOOSE grades). The skeleton-pool size IS the synthesis fuel budget, the
mirror of the state-pool = unroll budget. This keeps the honest scope of a first slice at
**template/skeleton synthesis over a tiny intent vocabulary**, not free-form codegen.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Callable

import ugm as h
from ugm import load_machine_rules, ask_goal, set_candidate, choose, explain_choice

from pystrider.intake import intake_function
from pystrider.analysis import analyze_return_none, Outcome


# the two properties a lookup-with-default spec can demand of the code that realizes it.
FEATURES = ("nonnull_return", "preserves_input")


# --- the succinct spec (DATA) --------------------------------------------------------------

@dataclass(frozen=True)
class Spec:
    """A technical specification, deliberately terse. `intent` names an entry in the skeleton
    library; everything else is a hole the emitter fills, or a flag the refinement rules expand.
    The whole point is that this is SHORT — the CNL rules expand `intent` (+ `strict`) into the
    concrete requirements code must satisfy."""
    name: str                    # graph id for this spec, e.g. "lookup_spec"
    intent: str                  # "lookup_with_default"
    fn_name: str                 # emitted function name
    input_var: str               # the possibly-None input parameter, e.g. "v"
    strict: bool = False         # also require that a non-None input is preserved unchanged


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
    # naive `return v` — preserves the input but is NOT nonnull; pinned to FAIL the nonnull check.
    Skeleton("naive", "lookup_with_default", frozenset({"preserves_input"}), 1.0,
             lambda sp: _fn_source(sp.fn_name, sp.input_var, _name(sp.input_var))),
    # `return v or {}` — compact + nonnull, but drops a FALSY non-None input (not preserves_input).
    Skeleton("coalesce_or", "lookup_with_default", frozenset({"nonnull_return"}), 1.0,
             lambda sp: _fn_source(sp.fn_name, sp.input_var,
                                   ast.BoolOp(op=ast.Or(), values=[_name(sp.input_var), _empty_dict()]))),
    # `return v if v is not None else {}` — nonnull AND preserves every non-None input (falsy too).
    Skeleton("coalesce_ifexp", "lookup_with_default", frozenset({"nonnull_return", "preserves_input"}), 0.7,
             lambda sp: _fn_source(sp.fn_name, sp.input_var, ast.IfExp(
                 test=ast.Compare(left=_name(sp.input_var), ops=[ast.IsNot()],
                                  comparators=[ast.Constant(value=None)]),
                 body=_name(sp.input_var), orelse=_empty_dict()))),
]
_BY_NAME = {s.name: s for s in SKELETONS}


# --- the refinement rules (CNL) — the EXPANSION of a succinct spec ---------------------------
# Stratified, pure Datalog (binds pre-existing spec/skeleton nodes, mints nothing):
#   R1 DECOMPOSE : the intent (and the `strict` flag) expand into concrete required features.
#   R2 LACKS     : a skeleton lacks a feature it does not provide (NAC over the feature vocab).
#   R3 MISSES    : a skeleton misses a spec if it lacks any feature that spec requires.
#   R4 REALIZE   : a skeleton realizes a spec iff it is for that intent and misses nothing
#                  (conjunction-of-requirements as `not ... misses`, the honest hard part).
# `who realizes <spec>` backward-CHAINs all four — the mirror of `who applies_to <site>` retrieval.
REFINEMENT_RULES = "\n".join([
    "?spec requires nonnull_return when ?spec is_a spec and ?spec intent lookup_with_default",
    "?spec requires preserves_input when ?spec is_a spec and ?spec strict yes",
    "?sk lacks ?feat when ?feat is_a feature and ?sk is_a skeleton and not ?sk provides ?feat",
    "?sk misses ?spec when ?spec requires ?feat and ?sk lacks ?feat",
    "?sk realizes ?spec when ?sk is_a skeleton and ?sk for_intent ?k and ?spec intent ?k "
    "and not ?sk misses ?spec",
])


def _retrieval_graph(spec: Spec) -> "h.Graph":
    """Materialize the spec + the skeleton library + the feature vocab as facts (the one
    direct-authoring boundary)."""
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    def rel(s: str, p: str, o: str) -> None: g.add_relation(n(s), p, n(o))

    for feat in FEATURES:
        rel(feat, "is_a", "feature")
    rel(spec.name, "is_a", "spec")
    rel(spec.name, "intent", spec.intent)
    if spec.strict:
        rel(spec.name, "strict", "yes")
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


def requirements(spec: Spec) -> set[str]:
    """The concrete features the refinement rules DERIVE this spec to require — the expansion of the
    succinct `intent` (+ `strict` flag) into checkable requirements. Each is proved through the
    public firmware (`is <spec> requires <feature>`)."""
    rules = load_machine_rules(REFINEMENT_RULES)
    g = _retrieval_graph(spec)
    return {f for f in FEATURES
            if ask_goal(g, f"is {spec.name} requires {f}", rules) == ["yes"]}


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


# --- verify by re-execution: SYMBOLIC (re-analyze) + CONCRETE (run it) -----------------------

def verify_nonnull(source: str, spec: Spec) -> list[Outcome]:
    """SYMBOLIC check of `nonnull_return`: re-intake the emitted `source` and run the EXISTING
    `analyze_return_none` under the worst-case hypothesis (the input IS None). An empty result
    means 'never returns None' holds under execution — trust by the analyzer, not the claim."""
    return analyze_return_none(intake_function(source), {spec.input_var: "none"})


class _Falsy:
    """A falsy-but-non-None sentinel: `bool(x) is False`, `x is not None`. Distinguishes
    `v or {}` (drops it -> {}) from `v if v is not None else {}` (keeps it)."""
    def __bool__(self) -> bool:
        return False


def verify_preserves_input(source: str, spec: Spec) -> bool:
    """CONCRETE check of `preserves_input` (the design's concrete-exec tool, in miniature): a
    property the symbolic none/object domain does NOT track. RUN the emitted function on a falsy,
    non-None sentinel and require it back unchanged. Safe: the skeletons are our own pre-minted,
    pure, side-effect-free bodies — the 'scope to pure fragments first' the design calls for."""
    ns: dict[str, object] = {}
    exec(compile(source, "<emitted>", "exec"), ns)
    sentinel = _Falsy()
    return ns[spec.fn_name](sentinel) is sentinel


# --- the whole loop --------------------------------------------------------------------------

@dataclass
class Synthesis:
    spec: Spec
    retrieved: list[str]
    winner: str | None
    source: str
    nonnull_ok: bool             # SYMBOLIC: emitted winner never returns None (analyze_return_none)
    preserves_ok: bool           # CONCRETE: emitted winner returns a falsy non-None input unchanged
    verified: bool               # both checks pass (spec holds under execution)
    residual: list[Outcome]      # returns-None violations still present in the winner (want [])
    realize_trace: list[str]     # RECORD: why the winner realizes the spec
    choose_trace: list[str]      # CHOOSE: why it beat the alternatives
    candidates: list[Skeleton] = field(default_factory=list)


def synthesize(spec: Spec) -> Synthesis:
    """spec -> RETRIEVE realizing skeletons -> CHOOSE the graded-best -> EMIT source -> VERIFY by
    re-execution (symbolic + concrete). The full mirror of the analyze/repair loop, one firmware."""
    cands = retrieve(spec)
    winner, choose_trace = choose_skeleton(cands)
    source = winner.emit(spec) if winner else ""
    residual = verify_nonnull(source, spec) if winner else []
    nonnull_ok = bool(winner) and not residual
    preserves_ok = bool(winner) and verify_preserves_input(source, spec)
    # a lenient spec does not demand preservation, so it is not part of that spec's verdict.
    verified = nonnull_ok and (preserves_ok or not spec.strict)
    return Synthesis(
        spec=spec, retrieved=sorted(c.name for c in cands),
        winner=winner.name if winner else None, source=source,
        nonnull_ok=nonnull_ok, preserves_ok=preserves_ok, verified=verified, residual=residual,
        realize_trace=realize_trace(spec, winner.name) if winner else [],
        choose_trace=choose_trace, candidates=cands)


# --- live walkthrough ------------------------------------------------------------------------

def _show(spec: Spec) -> None:
    r = synthesize(spec)
    strict = "STRICT (nonnull + preserves_input)" if spec.strict else "lenient (nonnull only)"
    print(f"=== spec: {strict} ===")
    print(f"  refine -> realizing skeletons: {r.retrieved}")
    print(f"  choose -> winner: {r.winner}")
    print(f"  emit   -> {r.source.splitlines()[-1].strip()}")
    print(f"  verify -> nonnull(symbolic)={r.nonnull_ok}  preserves(concrete)={r.preserves_ok}"
          f"  => {'SPEC HOLDS' if r.verified else 'SPEC VIOLATED'}\n")


def main() -> None:
    base = dict(name="lookup_spec", intent="lookup_with_default", fn_name="lookup", input_var="v")
    _show(Spec(**base))                          # lenient: compact `v or {}` wins
    _show(Spec(**base, strict=True))             # strict: the flip — only the ifexp form realizes

    print("Why the flip: `return v or {}` PASSES the symbolic nonnull check but DROPS a falsy "
          "non-None\ninput — the concrete check catches it, which is exactly why the strict spec "
          "excludes it:")
    lenient_src = _BY_NAME["coalesce_or"].emit(Spec(**base))
    print(f"    coalesce_or preserves a falsy input? {verify_preserves_input(lenient_src, Spec(**base))}"
          "   (returns {} for input 0)")

    print("\nRECORD -> spec->code rationale for the strict winner (note the derived conjunction):")
    for line in realize_trace(Spec(**base, strict=True), "coalesce_ifexp"):
        print(f"    {line}")


if __name__ == "__main__":
    main()
