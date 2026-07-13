"""Feasibility probe — MULTI-FUNCTION synthesis (emit + call a helper), verified CROSS-CALL.

The next frontier after `controlflow_synthesis.py`: a subgoal satisfied not by an expression or a
guarded statement but by **emitting a helper function and calling it** — the compositional unit
becomes a *function*, and the program becomes *two* functions that must be correct *together*. The
question: does the synthesis loop still close when correctness spans a call boundary, and can the
**productized inter-procedural analyzer** be its oracle? **Verdict: yes — and the verifier's
precision boundary visibly shapes what the synthesizer certifies.** Mirrors the other probes.

Three findings:

  1. A SUBGOAL CAN BE A HELPER.  A `program` goal expands into a composition that emits a helper
     `extract(v)` AND a caller `process(x)` that *calls* it — two pre-minted function skeletons the
     tool fills, rules only selecting. Multi-function synthesis is compositional synthesis one level
     up (function, not statement), and it needs no new machinery on the emit side.

  2. VERIFICATION IS CROSS-CALL, through the PRODUCTIZED `Session`.  Each candidate is emitted as two
     real functions, loaded into a `Session` (each under its own namespace — identity by
     `(function, name)`), the call is `link_calls`-wired, and `analyze_across_call` seeds a hypothesis
     about the CALLER's input and reads outcomes INSIDE the CALLEE. The value crosses the call
     boundary through the exact same inter-procedural machinery the analyzer ships — no bespoke
     oracle. A composition that lets a None flow across the call into an unguarded deref is REJECTED.

  3. VERIFICATION IS PATH-SENSITIVE ACROSS THE CALL — and synthesis both FOUND the boundary and MOVED
     it.  Three compositions are proposed in CHOOSE order:
        naive        : `process` delegates, `extract` derefs        -> None genuinely crosses -> REJECTED
        guard_caller : `process` guards THEN delegates, `extract` derefs -> CERTIFIED (see below)
        total_helper : `extract` guards its OWN input                -> also clean (never reached)
     `guard_caller` is safe at run time — the guard prevents the call on None — and the cross-call link
     now CREDITS it: `Session.link_calls` stamps `refine_nonnull` on a call sitting inside
     `if arg is not None:`, and the refined cross-call assign (semantics 2e) carries only the non-None
     value into the callee, so no false AttributeError. So CHOOSE's compact caller-side guard WINS over
     the defensive `total_helper`. This was NOT always so: an *earlier path-INSENSITIVE* link wired the
     argument unconditionally and rejected `guard_caller` too — a conservative false positive. Synthesis
     SURFACED that boundary, and the refinement (this axis) moved it; `naive`, where None really does
     cross, stays rejected — the analyzer distinguishes a real cross-call bug from a safely-guarded call.

The invariants hold, and #8 is ROUTED AROUND, not blocked on:

  * RULES NEVER MINT.  Each function is a pre-minted skeleton with holes; rules select the
    composition, the tool fills and emits real source.
  * TRUST BY EXECUTION of the productized checker — here the inter-procedural `analyze_across_call`.
  * NO SHARED SYNTHESIS GRAPH.  Each function is emitted independently and only brought together
    inside the `Session`, which namespaces identity — so the name-split-join footgun (ugm
    `feedback_from_pystrider.md` #8a) never bites: it is a *productization* prerequisite for a single
    shared synthesis graph, not a blocker for this probe (the analysis side proved the same for a
    multi-function analysis graph via banks + namespaces).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Callable

import ugm as h
from ugm import load_machine_rules, ask_goal, set_candidate, choose, explain_choice

from pystrider.session import Session
from pystrider.analysis import Outcome


# --- the succinct spec (DATA) ----------------------------------------------------------------

@dataclass(frozen=True)
class Spec:
    """Realize a TOTAL `caller(x)` that DELEGATES to a helper — never raise across the call boundary,
    even when the input is None. `input_var` is the possibly-None parameter."""
    name: str                    # graph id, e.g. "process_spec"
    caller: str = "process"      # emitted caller function name
    helper: str = "extract"      # emitted helper function name
    input_var: str = "x"         # the possibly-None parameter of the caller


# --- ast emit helpers: two pre-minted function skeletons, filled per composition --------------

def _name(v: str) -> ast.Name:
    return ast.Name(id=v, ctx=ast.Load())


def _is_not_none(v: str) -> ast.expr:
    return ast.Compare(left=_name(v), ops=[ast.IsNot()], comparators=[ast.Constant(value=None)])


def _fn(name: str, param: str, body: list[ast.stmt]) -> str:
    fn = ast.FunctionDef(
        name=name, args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=param)],
                                       vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=body, decorator_list=[])
    mod = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(mod)
    return ast.unparse(mod)


# helper (`extract(v)`) skeletons
def _extract_naive(sp: Spec) -> str:
    """Derefs its parameter unconditionally — total only if never called with None."""
    return _fn(sp.helper, "v", [ast.Return(value=ast.Attribute(value=_name("v"), attr="value", ctx=ast.Load()))])


def _extract_total(sp: Spec) -> str:
    """Guards its OWN input — robust regardless of how a caller invokes it."""
    return _fn(sp.helper, "v", [
        ast.If(test=_is_not_none("v"),
               body=[ast.Return(value=ast.Attribute(value=_name("v"), attr="value", ctx=ast.Load()))],
               orelse=[]),
        ast.Return(value=ast.Dict(keys=[], values=[]))])


# caller (`process(x)`) skeletons — each CALLS the helper
def _call_helper(sp: Spec) -> ast.expr:
    return ast.Call(func=_name(sp.helper), args=[_name(sp.input_var)], keywords=[])


def _process_delegate(sp: Spec) -> str:
    """Passes its input straight into the helper."""
    return _fn(sp.caller, sp.input_var, [ast.Return(value=_call_helper(sp))])


def _process_guarded(sp: Spec) -> str:
    """Guards its input, THEN delegates (safe at run time — but the cross-call link is path-
    insensitive, so the analyzer cannot see the guard prevents the call)."""
    return _fn(sp.caller, sp.input_var, [
        ast.If(test=_is_not_none(sp.input_var), body=[ast.Return(value=_call_helper(sp))], orelse=[]),
        ast.Return(value=ast.Dict(keys=[], values=[]))])


# --- the composition library: whole two-function programs, pre-minted, rules select -----------
# A composition is coupled (caller and helper must be correct TOGETHER), so the whole two-function
# program is the honest pre-minted unit — each bundles an emit-helper + an emit-caller-that-calls-it.

@dataclass(frozen=True)
class Composition:
    name: str
    compactness: float                       # CHOOSE grade — higher = tried first
    note: str
    build: Callable[[Spec], tuple[str, str]]  # spec -> (helper_src, caller_src)


COMPOSITIONS: list[Composition] = [
    Composition("naive", 1.0, "process delegates; extract derefs (None crosses the call)",
                lambda sp: (_extract_naive(sp), _process_delegate(sp))),
    Composition("guard_caller", 0.8, "process guards then delegates; extract derefs "
                "(safe at run time; certified by the path-sensitive refined link)",
                lambda sp: (_extract_naive(sp), _process_guarded(sp))),
    Composition("total_helper", 0.6, "extract guards its own input (robust at the boundary)",
                lambda sp: (_extract_total(sp), _process_delegate(sp))),
]
_BY_NAME = {c.name: c for c in COMPOSITIONS}


# --- selection rule (CNL) — retrieve the candidate compositions for the program goal ----------
RULES = "\n".join([
    "?comp realizes ?goal when ?comp is_a composition and ?comp for_goal ?k and ?goal wants ?k",
])


def _retrieve_and_order(rules) -> list[str]:
    """Mint the compositions as candidates, RETRIEVE via `who realizes program`, and order by
    iterated CHOOSE (winner first) — the mirror of repair_all re-choosing after each try."""
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    n("program"); g.add_relation(n("program"), "wants", n("program"))
    for c in COMPOSITIONS:
        g.add_relation(n(c.name), "is_a", n("composition"))
        g.add_relation(n(c.name), "for_goal", n("program"))
    realizers = {a.split(" ", 1)[0] for a in ask_goal(g, "who realizes program", rules)}
    cands = [c for c in COMPOSITIONS if c.name in realizers]
    order: list[str] = []
    remaining = list(cands)
    while remaining:
        gg = h.Graph(); goal = gg.add_node("sel")
        for c in remaining:
            set_candidate(gg, goal, gg.add_node(c.name), c.compactness)
        winners = choose(gg, goal, alpha=0.01)
        if not winners:
            break
        win = gg.name(winners[0]); order.append(win)
        remaining = [c for c in remaining if c.name != win]
    return order


def choose_trace() -> list[str]:
    g = h.Graph(); goal = g.add_node("sel")
    for c in COMPOSITIONS:
        set_candidate(g, goal, g.add_node(c.name), c.compactness)
    choose(g, goal, alpha=0.01)
    return explain_choice(g, goal)


# --- verify CROSS-CALL through the productized Session (the inter-procedural oracle) -----------

def verify(helper_src: str, caller_src: str, spec: Spec) -> list[Outcome]:
    """Load both emitted functions into a fresh `Session` (each namespaced), wire the call, and ask
    the PRODUCTIZED `analyze_across_call`: seeding the caller's input = None, does an AttributeError
    arise INSIDE the callee (the value crossing the call boundary)? `[]` == certified clean."""
    s = Session()
    s.add_function(helper_src)                       # extract, namespace f0_
    s.add_function(caller_src)                        # process, namespace f1_
    s.link_calls()                                    # wire process's call(x) -> extract's param cell
    return s.analyze_across_call(spec.caller, {spec.input_var: "none"}, spec.helper)


# --- the loop --------------------------------------------------------------------------------

@dataclass
class Attempt:
    composition: str
    helper_src: str
    caller_src: str
    outcomes: list[Outcome]                  # cross-call analyzer verdict ([] == certified clean)
    accepted: bool


@dataclass
class Synthesis:
    spec: Spec
    winner: str | None
    helper_src: str
    caller_src: str
    attempts: list[Attempt]
    choose_trace: list[str]
    verified: bool


def synthesize(spec: Spec) -> Synthesis:
    """Propose compositions in CHOOSE order; emit each as two functions; VERIFY each cross-call with
    the productized Session; accept the first the inter-procedural analyzer certifies clean."""
    rules = load_machine_rules(RULES)
    attempts: list[Attempt] = []
    winner = h_src = c_src = None
    for name in _retrieve_and_order(rules):
        comp = _BY_NAME[name]
        helper_src, caller_src = comp.build(spec)
        outcomes = verify(helper_src, caller_src, spec)
        ok = not outcomes
        attempts.append(Attempt(name, helper_src, caller_src, outcomes, ok))
        if ok:
            winner, h_src, c_src = name, helper_src, caller_src
            break
    return Synthesis(spec=spec, winner=winner, helper_src=h_src or "", caller_src=c_src or "",
                     attempts=attempts, choose_trace=choose_trace(), verified=winner is not None)


# --- live walkthrough ------------------------------------------------------------------------

def main() -> None:
    spec = Spec(name="process_spec", caller="process", helper="extract", input_var="x")
    r = synthesize(spec)

    print("Multi-function synthesis: a TOTAL `process(x)` that DELEGATES to `extract` — never raise")
    print("across the call boundary, even on x=None. Verified by the productized cross-call analyzer.\n")
    print("propose-and-verify (CHOOSE order; `Session.analyze_across_call` is the oracle):")
    for a in r.attempts:
        verdict = "ACCEPTED (analyzer certifies clean)" if a.accepted else \
            f"REJECTED: {a.outcomes[0].headline()}"
        print(f"  - {a.composition:13s} {_BY_NAME[a.composition].note}")
        print(f"      -> {verdict}")

    print(f"\nwinner: {r.winner}   (spec holds cross-call under symbolic re-execution: {r.verified})")
    print("  # helper:")
    for line in r.helper_src.splitlines():
        print(f"    {line}")
    print("  # caller:")
    for line in r.caller_src.splitlines():
        print(f"    {line}")

    print("\nThe honest part: CHOOSE preferred the compact `naive`, and the cross-call analyzer rejected")
    print("it (None genuinely crosses into extract's deref). But it CERTIFIES `guard_caller` -- the")
    print("path-sensitive refined link (semantics 2e) credits the caller's `if x is not None:` guard --")
    print("so the compact caller-side guard wins over the defensive `total_helper`. An earlier")
    print("path-insensitive link rejected `guard_caller` too (a false positive); synthesis surfaced that")
    print("boundary and the refinement moved it, while `naive` (None really crosses) stays rejected.")


if __name__ == "__main__":
    main()
