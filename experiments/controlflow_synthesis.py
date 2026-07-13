"""Feasibility probe — CONTROL-FLOW synthesis by DEMAND-DRIVEN pre-minting, verified SYMBOLICALLY.

This probe pushes the synthesis axis to its next frontier and answers the worry left open by
`codegen_understand.py`: recursive subgoal expansion emitted straight-line dataflow — does it break
once the generated code needs **control flow** (a conditional), and does the pre-minted pool then
blow up combinatorially? **Verdict: no on both, and the analysis half now grades the candidates.**
Mirrors the other `experiments/*.py`: the smallest end-to-end loop that proves the axis is real.

Three findings, one line each:

  1. CONTROL FLOW is synthesizable under the no-rule-mint constraint.  A `program` goal expands into
     a strategy that emits an `if x is not None: return <present> ; return <fallback>` skeleton with
     HOLES for its sub-goals — exactly as intake pre-mints an unrolled loop's state chain. Rules only
     *select* the strategy; the tool fills the holes. A guard is just one more pre-minted skeleton.

  2. The pool is minted DEMAND-DRIVEN, so control flow does NOT blow it up.  Instead of
     pre-materializing every candidate program up front (the cross-product `spec_synthesis` warned
     about), the emit tool mints one goal's candidate strategies at a time, and only descends into a
     strategy's sub-structure when that strategy is actually TRIED. An out-competed strategy's whole
     sub-tree is never minted — the saving IS the un-expanded cross-product (measured below).

  3. VERIFICATION gates selection, using the PRODUCTIZED analyzer as the oracle.  CHOOSE prefers the
     compact `return x.value` (no guard) — but the real `analyze` REJECTS it (AttributeError under
     x=None), so synthesis falls back to the guarded form, which `analyze`/`analyze_return_none`
     clear. The generator proposes; the analyzer disposes — the analysis and synthesis halves close
     the loop on control flow, over the SAME firmware. Trust by execution of the checker, not claim.

The two project invariants hold, which is the reassuring part:

  * RULES NEVER MINT.  Fresh statements/branches are existential-minting territory (the wall
    `state_threading.py` hit). So the emit tool pre-mints — but now LAZILY, one layer per expansion
    step; the rules only select. Demand-driven minting is the synthesis mirror of the demand-driven,
    fuel-bounded analysis stance ("agent, not theorem prover"): you never open the whole tree.

  * TRUST BY EXECUTION.  Each assembled candidate is re-intaken and run through the SAME `analyze` /
    `analyze_return_none` the productized loop uses — no bespoke oracle. A candidate is accepted only
    because the checker clears it; the compact-but-buggy candidate is excluded because the checker
    does not.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Callable

import ugm as h
from ugm import load_machine_rules, ask_goal, set_candidate, choose, explain_choice

from pystrider.intake import intake_function
from pystrider.analysis import analyze_all, Outcome


# --- the succinct spec (DATA) ----------------------------------------------------------------

@dataclass(frozen=True)
class Spec:
    """A terse spec: realize a TOTAL function over a possibly-None input — never raise, never return
    None. `intent` names the root goal in the strategy library; the input var is the (maybe-)None
    parameter the emitted control flow must guard."""
    name: str                    # graph id, e.g. "fetch_spec"
    fn_name: str                 # emitted function name
    input_var: str = "x"         # the possibly-None parameter


# --- the strategy library: pre-minted LAZILY, grouped by the GOAL each strategy realizes -------
# A strategy realizes one goal by emitting a code skeleton with HOLES for its sub-goals (the
# compositional, control-flow-carrying analogue of a recipe). Rules select; the tool fills holes.
# `build` maps {sub-goal -> filled node} to this goal's node — a stmt-list for `program`, an expr
# for a value goal. NOTHING here is minted until its goal is actually expanded (finding 2).

def _name(v: str) -> ast.Name:
    return ast.Name(id=v, ctx=ast.Load())


def _is_not_none(v: str) -> ast.expr:
    return ast.Compare(left=_name(v), ops=[ast.IsNot()], comparators=[ast.Constant(value=None)])


@dataclass(frozen=True)
class Strategy:
    name: str                            # graph id / library key
    goal: str                            # the goal-kind it realizes ("program", "present_value", ...)
    subgoals: tuple[str, ...]            # the goal-kinds it needs filled (its holes)
    compactness: float                   # CHOOSE grade — higher = more compact = tried first
    build: Callable[[dict[str, ast.AST], Spec], ast.AST]  # {subgoal -> node}, spec -> this goal's node


# grouped by goal-kind; the value is the candidate pool minted when that goal is expanded.
LIBRARY: dict[str, list[Strategy]] = {
    "program": [
        # COMPACT but BUGGY: `return x.value` with no guard — the analyzer will reject it under None.
        Strategy("s_direct", "program", ("present_value",), 1.0,
                 lambda sub, sp: [ast.Return(value=sub["present_value"])]),
        # CORRECT: guard the deref, fall back to a non-None default — one pre-minted control skeleton.
        Strategy("s_guarded", "program", ("present_value", "fallback_value"), 0.8,
                 lambda sub, sp: [
                     ast.If(test=_is_not_none(sp.input_var),
                            body=[ast.Return(value=sub["present_value"])], orelse=[]),
                     ast.Return(value=sub["fallback_value"])]),
        # A verbose alternative that is out-competed and NEVER reached — its deep `audit` sub-tree is
        # therefore never minted, which is exactly the demand-driven saving finding 2 measures.
        Strategy("s_verbose", "program", ("present_value", "fallback_value", "audit_stmt"), 0.5,
                 lambda sub, sp: [sub["audit_stmt"],
                                  ast.If(test=_is_not_none(sp.input_var),
                                         body=[ast.Return(value=sub["present_value"])], orelse=[]),
                                  ast.Return(value=sub["fallback_value"])]),
    ],
    "present_value": [
        Strategy("pv_attr", "present_value", (), 1.0,
                 lambda sub, sp: ast.Attribute(value=_name(sp.input_var), attr="value", ctx=ast.Load())),
    ],
    "fallback_value": [
        Strategy("fv_empty", "fallback_value", (), 1.0, lambda sub, sp: ast.Dict(keys=[], values=[])),
    ],
    # --- the unique, deep sub-tree of the out-competed `s_verbose` (pruned, never minted) ---
    "audit_stmt": [
        Strategy("au_block", "audit_stmt", ("log_msg", "timestamp"), 1.0,
                 lambda sub, sp: ast.Expr(value=ast.Constant(value=None))),  # (never assembled)
    ],
    "log_msg": [Strategy("lm_str", "log_msg", (), 1.0, lambda sub, sp: ast.Constant(value="audit"))],
    "timestamp": [Strategy("ts_now", "timestamp", (), 1.0, lambda sub, sp: ast.Constant(value=0))],
}
_BY_NAME = {s.name: s for s in (st for pool in LIBRARY.values() for st in pool)}


def _eager_pool_size(root: str) -> int:
    """The size the pool would be if pre-minted EAGERLY: every strategy reachable from `root` through
    sub-goals. The demand-driven run stays below this by never expanding an out-competed branch."""
    seen: set[str] = set(); frontier = [root]
    while frontier:
        goal = frontier.pop()
        for st in LIBRARY.get(goal, []):
            if st.name not in seen:
                seen.add(st.name); frontier.extend(st.subgoals)
    return len(seen)


# --- the selection rule (CNL) — the mirror of operator retrieval, invoked PER GOAL ------------
# A strategy realizes a goal iff it is a strategy for that goal-kind. Deliberately light: the NEW
# discriminator in this probe is VERIFICATION (the analyzer), not the rules — so the rules just
# retrieve the candidate strategies and CHOOSE grades them; `analyze` then accepts or rejects.
RULES = "\n".join([
    "?strat realizes ?goal when ?strat is_a strategy and ?strat for_goal ?k and ?goal wants ?k",
])


# --- the demand-driven synthesizer: mint one layer, select, descend, assemble, VERIFY ---------

@dataclass
class Attempt:
    strategy: str
    source: str
    outcomes: list[Outcome]              # the analyzer's verdict ([] == verified clean)
    accepted: bool


@dataclass
class Synthesis:
    spec: Spec
    winner: str | None
    source: str
    attempts: list[Attempt]              # every candidate tried, in CHOOSE order (with why rejected)
    minted: int                          # strategy-nodes actually minted (demand-driven)
    eager_pool: int                      # what an EAGER pre-mint would have materialized
    choose_trace: list[str]              # CHOOSE provenance for the program-goal selection
    verified: bool


class _Synthesizer:
    """Expands a goal into code, minting each goal's candidate pool ON DEMAND (lazily) and caching
    it, so an out-competed strategy's sub-tree is never minted (the demand-driven claim)."""

    def __init__(self, spec: Spec) -> None:
        self.spec = spec
        self.rules = load_machine_rules(RULES)
        self._minted_goals: set[str] = set()      # goals whose pool has been minted (cache)
        self.minted = 0                            # count of strategy-nodes minted

    def _mint_and_retrieve(self, goal: str) -> tuple[list[Strategy], list[str]]:
        """MINT this goal's candidate strategies (lazily, once) into a fresh graph, then RETRIEVE +
        order them by CHOOSE. This is the one place minting happens — in the tool, per layer."""
        pool = LIBRARY.get(goal, [])
        if goal not in self._minted_goals:
            self._minted_goals.add(goal)
            self.minted += len(pool)               # a real tool pays here, once, per expanded goal
        g = h.Graph(); ids: dict[str, str] = {}
        def n(x: str) -> str:
            if x not in ids: ids[x] = g.add_node(x)
            return ids[x]
        n(goal); g.add_relation(n(goal), "wants", n(goal))     # the goal wants its own kind
        for st in pool:
            g.add_relation(n(st.name), "is_a", n("strategy"))
            g.add_relation(n(st.name), "for_goal", n(goal))
        realizers = {a.split(" ", 1)[0] for a in ask_goal(g, f"who realizes {goal}", self.rules)}
        cands = [st for st in pool if st.name in realizers]
        return cands, self._choose_order(cands)

    def _choose_order(self, cands: list[Strategy]) -> list[str]:
        """Full CHOOSE order (winner first), by iterated public CHOOSE — the mirror of repair_all
        re-choosing after each candidate is tried."""
        order: list[str] = []
        remaining = list(cands)
        while remaining:
            g = h.Graph(); goal = g.add_node("sel")
            node_of = {}
            for c in remaining:
                opt = g.add_node(c.name); node_of[c.name] = c
                set_candidate(g, goal, opt, c.compactness)
            winners = choose(g, goal, alpha=0.01)
            if not winners:
                break
            win = g.name(winners[0]); order.append(win)
            remaining = [c for c in remaining if c.name != win]
        return order

    def build_best(self, goal: str) -> ast.AST:
        """Realize a value/statement sub-goal with its single CHOOSE-best strategy (sub-goals here are
        deterministic; the backtracking that matters is at the `program` root)."""
        cands, order = self._mint_and_retrieve(goal)
        st = _BY_NAME[order[0]]
        return st.build({sg: self.build_best(sg) for sg in st.subgoals}, self.spec)

    def program_choose_trace(self) -> list[str]:
        cands, _ = self._mint_and_retrieve("program")
        g = h.Graph(); goal = g.add_node("sel")
        for c in cands:
            set_candidate(g, goal, g.add_node(c.name), c.compactness)
        choose(g, goal, alpha=0.01)
        return explain_choice(g, goal)


def _assemble(spec: Spec, body: list[ast.stmt]) -> str:
    fn = ast.FunctionDef(
        name=spec.fn_name,
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=spec.input_var)],
                           vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=body, decorator_list=[])
    mod = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(mod)
    return ast.unparse(mod)


def verify(source: str, spec: Spec) -> list[Outcome]:
    """SYMBOLIC verification through the PRODUCTIZED analyzer: re-intake the emitted source and run
    every effect (`analyze` + `analyze_return_none`) under the worst-case hypothesis — the input IS
    None. `[]` means the function neither raises nor returns None under None. No bespoke oracle."""
    return analyze_all(intake_function(source), {spec.input_var: "none"})


def synthesize(spec: Spec) -> Synthesis:
    """Expand the `program` goal DEMAND-DRIVEN; try candidates in CHOOSE order; assemble + VERIFY
    each with the real analyzer; accept the first that clears. The synthesis/analysis loop closing
    on control flow, over one firmware."""
    s = _Synthesizer(spec)
    _cands, order = s._mint_and_retrieve("program")
    attempts: list[Attempt] = []
    winner = source = None
    for name in order:
        st = _BY_NAME[name]
        body = st.build({sg: s.build_best(sg) for sg in st.subgoals}, spec)
        src = _assemble(spec, body)
        outcomes = verify(src, spec)
        ok = not outcomes
        attempts.append(Attempt(strategy=name, source=src, outcomes=outcomes, accepted=ok))
        if ok:
            winner, source = name, src
            break                                  # first verified candidate wins; stop expanding
    return Synthesis(
        spec=spec, winner=winner, source=source or "", attempts=attempts,
        minted=s.minted, eager_pool=_eager_pool_size("program"),
        choose_trace=s.program_choose_trace(), verified=winner is not None)


# --- live walkthrough ------------------------------------------------------------------------

def main() -> None:
    spec = Spec(name="fetch_spec", fn_name="fetch", input_var="x")
    r = synthesize(spec)

    print("Control-flow synthesis: a TOTAL `fetch(x)` — never raise, never return None.\n")
    print("propose-and-verify (CHOOSE order; the analyzer is the oracle):")
    for a in r.attempts:
        verdict = "ACCEPTED (analyzer clears it)" if a.accepted else \
            f"REJECTED: {a.outcomes[0].headline()}"
        print(f"  - {a.strategy:10s}: {a.source.splitlines()[-1].strip():24s} -> {verdict}")

    print(f"\nwinner: {r.winner}   (spec holds under symbolic re-execution: {r.verified})")
    for line in r.source.splitlines():
        print(f"    {line}")

    print(f"\ndemand-driven minting: minted {r.minted} strategy-nodes; an EAGER pre-mint would "
          f"materialize {r.eager_pool}.")
    print(f"  the {r.eager_pool - r.minted} saved are the entire sub-tree of the out-competed "
          f"`s_verbose` (audit/log/timestamp),")
    print(f"  never expanded because `s_guarded` verified first — that gap is the cross-product "
          f"that grows\n  exponentially with independent choice points, and lazy minting never "
          f"pays it.")

    print("\nThe point: CHOOSE preferred the COMPACT `return x.value`, but the productized `analyze` "
          "rejected it\n(AttributeError under x=None); synthesis fell back to the guarded form the "
          "analyzer clears. The\nsynthesis and analysis halves close the loop on control flow — "
          "one firmware, trust by the checker.")


if __name__ == "__main__":
    main()
