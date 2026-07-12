"""The analysis loop — hypothesis-driven symbolic reasoning over intake facts.

This is the design's core loop (docs/code_reasoning_design.md §1, §"Vertical spike"):
SUPPOSE a value for a parameter, CHAIN the operational semantics forward, and read the
OUTCOME (does an attribute access raise on a None binding?). Reasoning goes entirely through
the public ugm firmware — `suppose` opens the hypothesis world, `ask_goal("why ...")` renders
the RECORD provenance as the human-readable execution trace. We never touch the graph after
intake.

Modification (step 5) is the same loop one level deeper: `guarded_variant` applies a
transformation operator (insert `if VAR is not None:`) as added, monotone facts — a new code
version — and re-runs the analysis inside it to confirm the outcome clears.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import ugm as h
from ugm import suppose, ask_goal, CONFIRMED

from .intake import Intake, intake_function
from .semantics import build_rule_graph, rule_list


# the value nodes a hypothesis can bind a parameter to, with their lattice type fact.
VALUE_KINDS = {
    "none": ("none", None),                       # `none is_a none_value` ships in the intake
    "object": ("obj", ("obj", "is_a", "object_value")),
}


@dataclass
class Outcome:
    site: str                    # the attribute-access expr id
    label: str                   # source-like label, e.g. "y.bar"
    line: int
    kind: str                    # "attribute_error"
    hypothesis: dict[str, str]
    trace: list[str] = field(default_factory=list)

    def headline(self) -> str:
        hyp = ", ".join(f"{k}={ 'None' if v=='none' else 'obj' }"
                        for k, v in self.hypothesis.items())
        return f"assuming {hyp}: {self.label} (line {self.line}) -> AttributeError"


def _kb_from(intake: Intake, extra: list[tuple[str, str, str]]) -> "h.Graph":
    """Materialize intake facts + any extra facts (value-kind types, guard structure) into a
    fresh graph. This is the ONLY direct materialization — the sanctioned intake boundary."""
    g = h.Graph()
    ids: dict[str, str] = {}

    def nid(name: str) -> str:
        if name not in ids:
            ex = g.nodes_named(name)
            ids[name] = ex[0] if ex else g.add_node(name)
        return ids[name]

    for s, p, o in list(intake.facts) + extra:
        g.add_relation(nid(s), p, nid(o))
    return g


def _hypothesis_facts(hypothesis: dict[str, str]):
    """(assumptions, extra type facts) for a param->value-kind hypothesis."""
    assumptions, extra = [], []
    for param, kind in hypothesis.items():
        node, type_fact = VALUE_KINDS[kind]
        assumptions.append((param, "has_value", node))
        if type_fact:
            extra.append(type_fact)
    return assumptions, extra


def analyze(intake: Intake, hypothesis: dict[str, str], *,
            extra_facts: list[tuple[str, str, str]] | None = None) -> list[Outcome]:
    """Under `hypothesis` (param -> 'none'|'object'), find every attribute site that raises
    AttributeError. Each confirmed site carries its RECORD provenance trace."""
    rg = build_rule_graph()
    rules = rule_list()
    assumptions, type_extra = _hypothesis_facts(hypothesis)
    extra = type_extra + list(extra_facts or [])

    outcomes: list[Outcome] = []
    for site in intake.attributes:
        kb = _kb_from(intake, extra)                       # fresh world per site (suppose mutates)
        result = suppose(kb, rg, assumptions=assumptions,
                         predictions=[("raises", site, "attribute_error")])
        if result.status == CONFIRMED:
            # the assumption is now ink; re-derive demand-driven to render the provenance trace.
            trace = ask_goal(kb, f"why {site} raises attribute_error", rules)
            outcomes.append(Outcome(
                site=site, label=intake.label_of.get(site, site),
                line=intake.line_of.get(site, 0), kind="attribute_error",
                hypothesis=dict(hypothesis), trace=trace))
    return outcomes


# --- modification (step 5): the "insert a guard" transformation operator -----------------

def guarded_variant(intake: Intake, guard_var: str, site: str) -> list[tuple[str, str, str]]:
    """The effect of inserting `if GUARD_VAR is not None:` around `site`, as added facts (a new
    monotone code version V2). Reachability of `site` now depends on the guard opening, which the
    semantics ties to `guard_var` not being None."""
    return [
        ("g_guard", "is_a", "guard"),
        ("g_guard", "tests", guard_var),
        (site, "within_guard", "g_guard"),
    ]


def analyze_source(src: str, hypothesis: dict[str, str]) -> tuple[Intake, list[Outcome]]:
    """Convenience: intake `src` then analyze under `hypothesis`."""
    intake = intake_function(src)
    return intake, analyze(intake, hypothesis)
