"""A Session — several functions reasoned about in ONE shared, accreting ugm graph (Slice B).

Each function is intaken under its own NAMESPACE, so same-named variables / states / expressions
across functions are DISTINCT nodes in the shared graph (identity by `(function, source_name)`),
while the type/value vocabulary the rules match on (`assign`, `none`, `none_value`,
`attribute_error`, …) stays SHARED. This is the id-addressed foundation ugm's Stage-3 core made
usable: a shared multi-function graph can hold legitimately distinct same-named nodes.

Per-function analysis is bounded by `focus_scope` to that function's own working set (ugm feedback
#7), so per-hypothesis cost tracks the function under analysis, not the whole accreted graph. And
detection is READ-ONLY (`suppose(commit=False)`, ugm feedback #6), so functions and hypotheses
never contaminate one another through shared ink.

Not yet here (the inter-procedural payoff, next increment): a `call` in `f` to `g` wiring `f`'s
argument cell to `g`'s parameter cell — a cross-`in_function` edge that lets a value flow across a
call boundary. The structural scope (`in_function`) and namespaced identity this module lands are
its prerequisites.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import ugm as h
from ugm import suppose, ask_goal, CONFIRMED

from .intake import Intake, intake_function
from .analysis import (Outcome, analyze, _node, _hypothesis_facts, _ensure_facts)
from .semantics import build_rule_graph, rule_list


def relabel_trace(trace: list[str], label_of: dict[str, str]) -> list[str]:
    """Render a RECORD trace with source LABELS in place of namespaced node ids (`f0_attr5` ->
    `y.bar`, `f0_y` -> `y`). Structure the rules never label (cells, states, value nodes) is left
    as-is — the predicate/value tokens (`has_value none`) stay verbatim."""
    ids = sorted(label_of, key=len, reverse=True)
    if not ids:
        return list(trace)
    pat = re.compile(r"(?<!\w)(" + "|".join(re.escape(i) for i in ids) + r")(?!\w)")
    return [pat.sub(lambda m: label_of[m.group(1)], line) for line in trace]


@dataclass
class Session:
    """Holds several functions in one shared ugm graph and analyzes each under its own focus."""
    graph: "h.Graph" = field(default_factory=h.Graph)
    functions: dict[str, Intake] = field(default_factory=dict)   # source func name -> Intake
    _n: int = 0
    _link_nodes: set = field(default_factory=set)                # cross-call pseudo-assign node ids

    def add_function(self, src: str, *, loop_unroll: int = 2) -> Intake:
        """Intake `src` under a fresh namespace and MATERIALIZE its facts into the shared graph.
        Shared vocabulary merges by name; every structural node stays distinct (the namespace)."""
        ns = f"f{self._n}_"
        self._n += 1
        ik = intake_function(src, loop_unroll=loop_unroll, namespace=ns)
        present = set(h.derived_triples(self.graph))
        for s, p, o in ik.facts:
            if (s, p, o) in present:            # shared vocab already there (monotone, no dup)
                continue
            self.graph.add_relation(_node(self.graph, s), p, _node(self.graph, o))
            present.add((s, p, o))
        self.functions[ik.func] = ik
        return ik

    def focus_for(self, ik: Intake) -> frozenset[str]:
        """The attention bound for a function: its own entity names plus the hypothesis value /
        outcome vocab — so a hypothesis reasons only within this function's working set."""
        return ik.entity_names() | {"attribute_error", "obj", "none"}

    def analyze(self, func_name: str, hypothesis: dict[str, str]) -> list[Outcome]:
        """Analyze one function against the SHARED graph, bounded to its own focus. Read-only in the
        shared graph (nothing inked), so any number of functions / hypotheses run without cross-talk."""
        ik = self.functions[func_name]
        return analyze(ik, hypothesis, kb=self.graph, focus_scope=self.focus_for(ik))

    def render_trace(self, func_name: str, outcome: Outcome) -> list[str]:
        """`outcome.trace` with this function's source labels substituted (readable rendering)."""
        return relabel_trace(outcome.trace, self.functions[func_name].label_of)

    # --- inter-procedural: value flow across a call boundary (Slice B step 4) ----------------

    def link_calls(self) -> list[tuple[str, str, str]]:
        """Wire every free-function call `f: ... g(a) ...` to a known callee `g`: the callee's
        parameter ENTRY cell takes the value of the caller's argument expression, materialized as a
        cross-`in_function` **pseudo-assign** (`g_param_cell := caller_arg_expr`). The existing ASSIGN
        rule then threads that value into `g`'s body — no new semantics, the payoff of structural
        scope over name-mangling. Returns `(caller, callee, param)` links wired. Call after all
        functions are added.

        **Path-sensitive across the call:** if the call site sits inside a guard `if a is not None:`
        that tests the very argument being passed, the link is stamped `refine_nonnull yes` so the
        refined cross-call assign (semantics 2e) carries only the non-None value into the callee — the
        callee cannot see None on the path where the guarded call actually happens. Without this the
        link is path-INSENSITIVE and a caller-side guard is not credited (a conservative false
        positive)."""
        wired: list[tuple[str, str, str]] = []
        for caller in self.functions.values():
            for call_id, callee_name in caller.call_target.items():
                callee = self.functions.get(callee_name)
                if callee is None:                       # calls something outside the session: skip
                    continue
                args = caller.call_args.get(call_id, [])
                guard_nonnull = self._call_guard_nonnull_var(caller, call_id)
                for i, param in enumerate(callee.params):
                    if i >= len(args):
                        break
                    link = f"{caller.namespace}link_{call_id}_{i}"
                    facts = [
                        (link, "is_a", "assign"),                    # a real ASSIGN (rule 2 fires)
                        (link, "assigns", callee.var_id(param)),     # target: callee's param
                        (link, "from_expr", args[i]),                # source: caller's arg expression
                        (link, "to_state", callee.entry_state),      # written into callee's entry cell
                        (link, "in_function", callee.namespace + callee.func),
                    ]
                    # refine the boundary if the passed argument is the guard's not-None-tested var
                    if guard_nonnull is not None and self._arg_var(caller, args[i]) == guard_nonnull:
                        facts.append((link, "refine_nonnull", "yes"))   # semantics 2e, not 2
                    for s, p, o in facts:
                        self.graph.add_relation(_node(self.graph, s), p, _node(self.graph, o))
                    self._link_nodes.add(link)
                    wired.append((caller.func, callee.func, param))
        return wired

    @staticmethod
    def _call_guard_nonnull_var(caller: Intake, call_id: str) -> str | None:
        """The namespaced variable a call is guarded not-None on (`call within_guard g`, `g tests v`),
        or None. Intake tags a call created inside an `if VAR is not None:` body with `within_guard`."""
        for s, p, o in caller.facts:
            if s == call_id and p == "within_guard":
                for s2, p2, o2 in caller.facts:
                    if s2 == o and p2 == "tests":
                        return o2
        return None

    @staticmethod
    def _arg_var(caller: Intake, arg_expr: str) -> str | None:
        """The namespaced variable a bare-Name argument expression reads (`arg reads v`), or None."""
        return next((o for s, p, o in caller.facts if s == arg_expr and p == "reads"), None)

    def analyze_across_call(self, caller_name: str, hypothesis: dict[str, str],
                            callee_name: str) -> list[Outcome]:
        """Seed a hypothesis about the CALLER's input and find outcomes INSIDE the CALLEE — the value
        crosses the call boundary through the link wired by `link_calls`. Focus spans both functions
        (plus the link) so the cross-procedure chain is in scope; detection stays read-only, so the
        trace is rendered on a private copy of the shared graph."""
        caller, callee = self.functions[caller_name], self.functions[callee_name]
        rg, rules = build_rule_graph(), rule_list()
        assumptions, type_extra = _hypothesis_facts(caller, hypothesis)
        _ensure_facts(self.graph, type_extra)
        focus = self.focus_for(caller) | self.focus_for(callee) | frozenset(self._link_nodes)

        confirmed = [site for site in callee.attributes
                     if suppose(self.graph, rg, assumptions=assumptions,
                                predictions=[("raises", site, "attribute_error")],
                                commit=False, focus_scope=focus).status == CONFIRMED]
        if not confirmed:
            return []

        scratch = self.graph.copy()                      # render the trace without inking the shared graph
        for s, p, o in assumptions:
            scratch.add_relation(_node(scratch, s), p, _node(scratch, o))
        labels = {**caller.label_of, **callee.label_of}
        outcomes: list[Outcome] = []
        for site in confirmed:
            trace = ask_goal(scratch, f"why {site} raises attribute_error", rules)
            outcomes.append(Outcome(
                site=site, label=callee.label_of.get(site, site),
                line=callee.line_of.get(site, 0), kind="attribute_error",
                hypothesis=dict(hypothesis),
                base_var=callee.attr_base_var.get(site, ""),
                trace=relabel_trace(trace, labels)))
        return outcomes
