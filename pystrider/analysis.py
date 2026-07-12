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
from .transform import insert_none_guard, insert_none_guard_range


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
                hypothesis=dict(hypothesis),
                base_var=intake.attr_base_var.get(site, ""), trace=trace))
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


def _assign_line_of(intake: Intake, var: str) -> int | None:
    """Line of the assignment that sets `var` (for a range-wrapping edit)."""
    stmt = next((s for (s, p, o) in intake.facts if p == "assigns" and o == var), None)
    return intake.line_of.get(stmt) if stmt else None


def _root_param(intake: Intake, var: str) -> str | None:
    """The parameter `var`'s value traces back to (via a single `var = <param>` assignment)."""
    facts = intake.facts
    stmt = next((s for (s, p, o) in facts if p == "assigns" and o == var), None)
    if not stmt:
        return None
    e = next((o for (s, p, o) in facts if s == stmt and p == "from_expr"), None)
    src = next((o for (s, p, o) in facts if s == e and p == "reads"), None)
    return src if src in intake.params else None


def candidate_edits(intake: Intake, hypothesis: dict[str, str],
                    outcome: Outcome) -> list[Candidate]:
    """Propose several repair operators for `outcome`, materialize each as real source, and VERIFY
    each by re-execution. Returns every candidate (verified or not) with its graded fit."""
    base = outcome.base_var
    root = _root_param(intake, base)
    assign_line = _assign_line_of(intake, base)
    src = intake.source

    specs = [
        ("guard-base", base, f"wrap the deref in `if {base} is not None:` (most local)",
         lambda: insert_none_guard(src, base, outcome.line), 1.0, 1.0),
    ]
    if root and root != base:
        specs.append(
            ("guard-param", root, f"wrap the deref in `if {root} is not None:` (root cause)",
             lambda: insert_none_guard(src, root, outcome.line), 0.7, 1.0))
        if assign_line is not None:
            specs.append(
                ("guard-param-wide", root,
                 f"wrap `{base} = {root}` through the deref in `if {root} is not None:` (wider)",
                 lambda: insert_none_guard_range(src, root, assign_line, outcome.line), 0.7, 0.5))

    out: list[Candidate] = []
    for name, var, desc, make, locality, compact in specs:
        v2 = make()
        residual = analyze(intake_function(v2), hypothesis)
        cleared = not any(o.label == outcome.label for o in residual)
        out.append(Candidate(name=name, var=var, description=desc, v2_source=v2,
                             cleared=cleared, locality=locality, compactness=compact))
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
