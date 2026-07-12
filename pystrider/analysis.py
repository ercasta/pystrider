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
from ugm import set_candidate, choose, explain_choice, winners_of

from .intake import Intake, intake_function
from .semantics import build_rule_graph, rule_list
from .transform import insert_none_guard
from . import operators as ops


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
    base_var: str = ""           # the variable dereferenced at the site (what a guard would test)
    trace: list[str] = field(default_factory=list)

    def headline(self) -> str:
        hyp = ", ".join(f"{k}={ 'None' if v=='none' else 'obj' }"
                        for k, v in self.hypothesis.items())
        return f"assuming {hyp}: {self.label} (line {self.line}) -> AttributeError"


def _node(g: "h.Graph", name: str) -> str:
    """The id of the node named `name`, reusing an existing one or minting it (intake boundary)."""
    ex = g.nodes_named(name)
    return ex[0] if ex else g.add_node(name)


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


def _hypothesis_facts(intake: Intake, hypothesis: dict[str, str]):
    """(assumptions, extra type facts) for a param->value-kind hypothesis. The value is seeded into
    the parameter's ENTRY-STATE cell (its value at function entry); the semantics thread it forward."""
    assumptions, extra = [], []
    for param, kind in hypothesis.items():
        node, type_fact = VALUE_KINDS[kind]
        assumptions.append((intake.entry_cell(param), "has_value", node))
        if type_fact:
            extra.append(type_fact)
    return assumptions, extra


def _focus_of(intake: Intake, assumptions: list[tuple[str, str, str]],
              extra: list[tuple[str, str, str]]) -> frozenset[str]:
    """The attention bound for this hypothesis: the function's own entity names plus the value /
    outcome vocab the assumptions + predictions reference (`attribute_error`, the value nodes). One
    function = the whole graph (no-op); the bound bites once a Session holds several functions."""
    names = set(intake.entity_names())
    for s, _p, o in list(assumptions) + list(extra):
        names.add(s)
        names.add(o)
    names.add("attribute_error")
    return frozenset(names)


def _ensure_facts(g: "h.Graph", facts: list[tuple[str, str, str]]) -> None:
    """Add each `(s, p, o)` to `g` if absent (monotone). Used to inject a hypothesis's shared value
    vocab (e.g. `obj is_a object_value`) into a shared Session graph without duplicating it."""
    present = set(h.derived_triples(g))
    for s, p, o in facts:
        if (s, p, o) not in present:
            g.add_relation(_node(g, s), p, _node(g, o))


def analyze(intake: Intake, hypothesis: dict[str, str], *,
            extra_facts: list[tuple[str, str, str]] | None = None,
            focus_scope: frozenset[str] | None = None,
            kb: "h.Graph | None" = None) -> list[Outcome]:
    """Under `hypothesis` (param -> 'none'|'object'), find every attribute site that raises
    AttributeError. Each confirmed site carries its RECORD provenance trace.

    Detection is a **pure query over the KB** — `suppose(commit=False)` inks nothing, so the world
    is reused across every site (ugm feedback #6 retired the old rebuild-per-site dance). Attention
    is bounded by `focus_scope` (feedback #7), defaulting to this function's working set.

    `kb` lets a `Session` run this against a **shared, accreting graph** holding several functions:
    detection stays read-only (nothing inked into the shared graph — so other functions and other
    hypotheses are never contaminated), and `focus_scope` keeps the cost tracking this function, not
    the whole graph. Trace rendering (which needs the hypothesis present to re-derive the RECORD
    tree) then happens on a private scratch KB, never the shared one. `kb=None` builds a private
    world from `intake` (the single-function default)."""
    rg = build_rule_graph()
    rules = rule_list()
    assumptions, type_extra = _hypothesis_facts(intake, hypothesis)
    extra = type_extra + list(extra_facts or [])
    focus = focus_scope if focus_scope is not None else _focus_of(intake, assumptions, extra)

    own = kb is None
    detect_kb = _kb_from(intake, extra) if own else kb
    if not own:
        _ensure_facts(detect_kb, extra)                    # shared value vocab (e.g. obj), monotone
    confirmed = [site for site in intake.attributes
                 if suppose(detect_kb, rg, assumptions=assumptions,
                            predictions=[("raises", site, "attribute_error")],
                            commit=False, focus_scope=focus).status == CONFIRMED]
    if not confirmed:
        return []

    # Render on a scratch KB when sharing, so the hypothesis ink never touches the shared graph.
    trace_kb = detect_kb if own else _kb_from(intake, extra)
    for s, p, o in assumptions:                            # ink the hypothesis ONCE to render traces
        trace_kb.add_relation(_node(trace_kb, s), p, _node(trace_kb, o))
    outcomes: list[Outcome] = []
    for site in confirmed:
        trace = ask_goal(trace_kb, f"why {site} raises attribute_error", rules)
        outcomes.append(Outcome(
            site=site, label=intake.label_of.get(site, site),
            line=intake.line_of.get(site, 0), kind="attribute_error",
            hypothesis=dict(hypothesis),
            base_var=intake.attr_base_var.get(site, ""), trace=trace))
    return outcomes


# --- modification (step 5): the "insert a guard" transformation operator -----------------

def guarded_variant(intake: Intake, guard_var: str, site: str) -> list[tuple[str, str, str]]:
    """The effect of inserting `if GUARD_VAR is not None:` around `site`, as added facts (a new
    monotone code version V2). Reachability of `site` now depends on the guard opening, which the
    semantics ties to `guard_var`'s cell (in the site's state) not being None."""
    state = intake.state_of.get(site, intake.entry_state)
    return [
        ("g_guard", "is_a", "guard"),
        ("g_guard", "tests", intake.var_id(guard_var)),   # the guard tests the var's graph node
        ("g_guard", "in_state", state),
        (site, "within_guard", "g_guard"),
    ]


@dataclass
class Repair:
    """A materialized code edit and its verification-by-re-execution."""
    var: str                     # the variable the inserted guard tests
    v2_source: str               # the actual edited Python (a human can read/apply this)
    cleared: bool                # did the original outcome disappear under re-analysis?
    residual: list[Outcome]      # any outcomes STILL present under the same hypothesis (want [])


def repair(intake: Intake, hypothesis: dict[str, str], outcome: Outcome) -> Repair:
    """Materialize an `if <base_var> is not None:` guard around the deref, then VERIFY by
    re-execution: re-intake the *edited source* (so the guard facts are derived, not
    hand-authored) and re-run the analysis under the same hypothesis. The edit is trusted only
    if the outcome clears on the real transformed code."""
    var = outcome.base_var or hypothesis and next(iter(hypothesis))    # fall back to a param
    v2_source = insert_none_guard(intake.source, var, outcome.line)
    v2 = intake_function(v2_source)
    residual = analyze(v2, hypothesis)
    cleared = all(o.site != outcome.site and o.label != outcome.label for o in residual)
    return Repair(var=var, v2_source=v2_source, cleared=cleared and not residual,
                  residual=residual)


# --- means-ends SELECTION: several candidate edits, verified, then CHOOSE the graded-best ------

@dataclass
class Candidate:
    """One proposed edit: its materialized source, whether it verifies, and its graded fit."""
    name: str
    var: str                     # the variable the guard tests
    description: str
    v2_source: str
    cleared: bool                # did it verify (outcome gone under re-execution)?
    locality: float              # 1.0 = acts at the deref's own base var; lower = upstream/wider
    compactness: float           # 1.0 = smallest edit; lower = wraps more code

    @property
    def fit(self) -> float:
        # non-compensatory (min) — matches ugm's t-norm graded reading; an edit is only as good
        # as its weakest dimension. Unverified edits are ineligible (fit 0).
        return min(self.locality, self.compactness) if self.cleared else 0.0


def candidate_edits(intake: Intake, hypothesis: dict[str, str],
                    outcome: Outcome) -> list[Candidate]:
    """RETRIEVE applicable operators from the effect-keyed library by backward-CHAIN, materialize
    each as real source, and VERIFY each by re-execution. The candidate set is chosen by the
    library (operators-as-data), not a hard-coded Python list; fit weights come from the library."""
    site_provides = ops.provides(intake, outcome.base_var)
    applicable = ops.retrieve(outcome.site, outcome.kind, site_provides)

    out: list[Candidate] = []
    for op in applicable:
        var, v2 = ops.STRATEGIES[op.strategy](intake, outcome)
        residual = analyze(intake_function(v2), hypothesis)
        cleared = not any(o.label == outcome.label for o in residual)
        out.append(Candidate(name=op.name, var=var, description=op.description.format(var=var),
                             v2_source=v2, cleared=cleared,
                             locality=op.locality, compactness=op.compactness))
    return out


@dataclass
class Selection:
    winner: Candidate | None
    candidates: list[Candidate]
    trace: list[str]             # explain_choice — the auditable CHOOSE why-trace


def choose_repair(intake: Intake, hypothesis: dict[str, str],
                  outcome: Outcome) -> Selection:
    """Generate + verify candidate edits, then use the public CHOOSE firmware mode to pick the
    graded-best (smallest / most-local edit wins). Losers are retained + auditable (monotone)."""
    cands = candidate_edits(intake, hypothesis, outcome)
    g = h.Graph()
    goal = g.add_node("repair_goal")
    node_of: dict[str, Candidate] = {}
    for c in cands:
        opt = g.add_node(c.name)
        node_of[c.name] = c
        set_candidate(g, goal, opt, c.fit)          # only verified edits carry positive fit
    winners = choose(g, goal, alpha=0.01)           # α-cut drops unverified (fit 0) candidates
    trace = explain_choice(g, goal)
    winner = node_of[g.name(winners[0])] if winners else None
    return Selection(winner=winner, candidates=cands, trace=trace)


def analyze_source(src: str, hypothesis: dict[str, str]) -> tuple[Intake, list[Outcome]]:
    """Convenience: intake `src` then analyze under `hypothesis`."""
    intake = intake_function(src)
    return intake, analyze(intake, hypothesis)
