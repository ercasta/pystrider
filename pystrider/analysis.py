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
from typing import Callable

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


@dataclass
class Caveat:
    """A place intake could NOT model (an unmodelled statement kind). Its effect on state is unknown,
    so any `clean` / `verified` verdict holds only MODULO this. Surfacing these is the difference
    between "checked and clear" and "nothing derived" (docs/critique.md weakness #5 — don't build on
    silence). A caveat is not an outcome — the code may be fine — but the analysis did not prove it."""
    label: str
    line: int
    kind: str = "not_modelled"

    def headline(self) -> str:
        return f"not modelled: {self.label} (line {self.line}) — verdict holds only modulo this"


def caveats(intake: Intake) -> list[Caveat]:
    """The unmodelled statements in `intake` — the gaps a `clean` verdict is otherwise silent about.
    An empty list next to zero outcomes means the whole function was modelled and is genuinely clear;
    a non-empty list means "clear on what was modelled". Threaded into `RepairPlan`; a synthesis or
    analysis caller should report it alongside outcomes so silence is never mistaken for safety."""
    return [Caveat(label=intake.label_of.get(sid, sid), line=intake.line_of.get(sid, 0))
            for sid in intake.not_modelled]


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


# the outcome vocabulary the rules key on — always kept in focus so any effect stays derivable.
_OUTCOME_VOCAB = frozenset({"attribute_error", "returns_none", "yes", "none"})


def _focus_of(intake: Intake, assumptions: list[tuple[str, str, str]],
              extra: list[tuple[str, str, str]]) -> frozenset[str]:
    """The attention bound for this hypothesis: the function's own entity names plus the value /
    outcome vocab the assumptions + predictions reference. One function = the whole graph (no-op);
    the bound bites once a Session holds several functions."""
    names = set(intake.entity_names())
    for s, _p, o in list(assumptions) + list(extra):
        names.add(s)
        names.add(o)
    return frozenset(names) | _OUTCOME_VOCAB


def _ensure_facts(g: "h.Graph", facts: list[tuple[str, str, str]]) -> None:
    """Add each `(s, p, o)` to `g` if absent (monotone). Used to inject a hypothesis's shared value
    vocab (e.g. `obj is_a object_value`) into a shared Session graph without duplicating it."""
    present = set(h.derived_triples(g))
    for s, p, o in facts:
        if (s, p, o) not in present:
            g.add_relation(_node(g, s), p, _node(g, o))


def _detect(intake: Intake, hypothesis: dict[str, str], *,
            targets: list[str], pred: str, obj: str, kind: str,
            base_of: "Callable[[str], str]",
            extra_facts: list[tuple[str, str, str]] | None = None,
            focus_scope: frozenset[str] | None = None,
            kb: "h.Graph | None" = None) -> list[Outcome]:
    """The shared detection core for ANY effect: seed `hypothesis`, then for each `target` node check
    the prediction `(pred, target, obj)` under `suppose(commit=False)` (read-only), and render the
    RECORD trace for the confirmed ones. `kind` + `base_of` shape the resulting `Outcome`s.

    Detection reuses one KB read-only (feedback #6) and is `focus_scope`-bounded (feedback #7). `kb`
    lets a Session share one accreting graph across functions without contaminating it; traces then
    render on a private scratch KB. `kb=None` builds a private world (single-function default)."""
    rg = build_rule_graph()
    rules = rule_list()
    assumptions, type_extra = _hypothesis_facts(intake, hypothesis)
    extra = type_extra + list(extra_facts or [])
    focus = focus_scope if focus_scope is not None else _focus_of(intake, assumptions, extra)

    own = kb is None
    detect_kb = _kb_from(intake, extra) if own else kb
    if not own:
        _ensure_facts(detect_kb, extra)                    # shared value vocab (e.g. obj), monotone
    confirmed = [t for t in targets
                 if suppose(detect_kb, rg, assumptions=assumptions,
                            predictions=[(pred, t, obj)],
                            commit=False, focus_scope=focus).status == CONFIRMED]
    if not confirmed:
        return []

    # Render on a scratch KB when sharing, so the hypothesis ink never touches the shared graph.
    trace_kb = detect_kb if own else _kb_from(intake, extra)
    for s, p, o in assumptions:                            # ink the hypothesis ONCE to render traces
        trace_kb.add_relation(_node(trace_kb, s), p, _node(trace_kb, o))
    outcomes: list[Outcome] = []
    for t in confirmed:
        trace = ask_goal(trace_kb, f"why {t} {pred} {obj}", rules)
        outcomes.append(Outcome(
            site=t, label=intake.label_of.get(t, t),
            line=intake.line_of.get(t, 0), kind=kind,
            hypothesis=dict(hypothesis), base_var=base_of(t), trace=trace))
    return outcomes


def analyze(intake: Intake, hypothesis: dict[str, str], *,
            extra_facts: list[tuple[str, str, str]] | None = None,
            focus_scope: frozenset[str] | None = None,
            kb: "h.Graph | None" = None) -> list[Outcome]:
    """Under `hypothesis` (param -> 'none'|'object'), find every attribute site that raises
    AttributeError (effect 1). Each confirmed site carries its RECORD provenance trace."""
    return _detect(intake, hypothesis, targets=intake.attributes,
                   pred="raises", obj="attribute_error", kind="attribute_error",
                   base_of=lambda t: intake.attr_base_var.get(t, ""),
                   extra_facts=extra_facts, focus_scope=focus_scope, kb=kb)


def analyze_return_none(intake: Intake, hypothesis: dict[str, str], *,
                        extra_facts: list[tuple[str, str, str]] | None = None,
                        focus_scope: frozenset[str] | None = None,
                        kb: "h.Graph | None" = None) -> list[Outcome]:
    """Under `hypothesis`, find every return statement that yields None (effect 2 — Slice C). Same
    machinery as `analyze`, a different effect key: proves the loop generalizes past None-derefs."""
    return _detect(intake, hypothesis, targets=intake.returns,
                   pred="returns_none", obj="yes", kind="returns_none",
                   base_of=lambda t: intake.return_var.get(t, ""),
                   extra_facts=extra_facts, focus_scope=focus_scope, kb=kb)


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


def candidate_edits(intake: Intake, hypothesis: dict[str, str], outcome: Outcome, *,
                    provides_fn: "Callable[[Intake, str], set[str]]" = ops.provides,
                    analyzer: "Callable[..., list[Outcome]]" = analyze) -> list[Candidate]:
    """RETRIEVE applicable operators from the effect-keyed library by backward-CHAIN (keyed on
    `outcome.kind`), materialize each as real source, and VERIFY each by re-execution. The candidate
    set is chosen by the library (operators-as-data), not a hard-coded Python list; fit weights come
    from the library. `provides_fn` + `analyzer` swap the effect (None-deref by default; a
    returns-None outcome passes `ops.provides_return` + `analyze_return_none`) with no new machinery."""
    site_provides = provides_fn(intake, outcome.base_var)
    applicable = ops.retrieve(outcome.site, outcome.kind, site_provides)

    out: list[Candidate] = []
    for op in applicable:
        var, v2 = ops.STRATEGIES[op.strategy](intake, outcome)
        residual = analyzer(intake_function(v2), hypothesis)
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


def _choose(cands: list[Candidate],
            fit_of: "Callable[[Candidate], float]") -> tuple[Candidate | None, list[str]]:
    """Run the public CHOOSE firmware over `cands` with a graded fit, returning the winner + the
    auditable `explain_choice` trace. The α-cut drops fit-0 (ineligible) candidates."""
    g = h.Graph()
    goal = g.add_node("repair_goal")
    node_of: dict[str, Candidate] = {}
    for c in cands:
        opt = g.add_node(c.name)
        node_of[c.name] = c
        set_candidate(g, goal, opt, fit_of(c))
    winners = choose(g, goal, alpha=0.01)
    trace = explain_choice(g, goal)
    winner = node_of[g.name(winners[0])] if winners else None
    return winner, trace


def choose_repair(intake: Intake, hypothesis: dict[str, str], outcome: Outcome, *,
                  provides_fn: "Callable[[Intake, str], set[str]]" = ops.provides,
                  analyzer: "Callable[..., list[Outcome]]" = analyze) -> Selection:
    """Generate + verify candidate edits, then use the public CHOOSE firmware mode to pick the
    graded-best (smallest / most-local edit wins). Losers are retained + auditable (monotone).
    `provides_fn` + `analyzer` select the effect (see `candidate_edits`)."""
    cands = candidate_edits(intake, hypothesis, outcome,
                            provides_fn=provides_fn, analyzer=analyzer)
    winner, trace = _choose(cands, lambda c: c.fit)   # only verified edits carry positive fit
    return Selection(winner=winner, candidates=cands, trace=trace)


# --- whole-function repair: iterate to a fixpoint, fixing EVERY outcome, regression-checked -----

# the effect table: for each outcome kind, how to RETRIEVE its operators (provides) and how to
# DETECT it (analyzer). `analyze_all` runs every effect; `repair_all` dispatches candidates by kind.
EFFECTS: "dict[str, tuple[Callable, Callable]]" = {
    "attribute_error": (ops.provides, analyze),
    "returns_none": (ops.provides_return, analyze_return_none),
}


def analyze_all(intake: Intake, hypothesis: dict[str, str], *,
                kb: "h.Graph | None" = None) -> list[Outcome]:
    """Every outcome of every effect under `hypothesis` — the whole-function health check."""
    out: list[Outcome] = []
    for _kind, (_provides, analyzer) in EFFECTS.items():
        out += analyzer(intake, hypothesis, kb=kb)
    return out


@dataclass
class RepairStep:
    """One edit in a repair plan: the outcome it targeted, the operator CHOSEN, and the state after."""
    target_label: str
    target_kind: str
    target_line: int
    operator: str
    description: str
    fit: float
    remaining: int               # outcomes left after this edit (strictly fewer than before)
    source_after: str


@dataclass
class RepairPlan:
    """The result of repairing a whole function: the final source, the ordered audit log of edits,
    and whether the function is now CLEAN (no outcome remains under the hypothesis). If not clean,
    `stuck` is an outcome no regression-free edit could remove."""
    source: str
    steps: list[RepairStep]
    clean: bool
    stuck: Outcome | None = None
    caveats: list[Caveat] = field(default_factory=list)   # unmodelled statements the verdict is modulo

    @property
    def fully_modelled(self) -> bool:
        """True iff intake modelled every statement — so `clean` means "checked and clear", not
        "clear on what was modelled". A `clean` plan with `fully_modelled` False is an honest partial."""
        return not self.caveats

    def summary(self) -> list[str]:
        head = ("repaired to clean" if self.clean
                else f"stuck on {self.stuck.label!r} ({self.stuck.kind})" if self.stuck
                else "incomplete (step budget)")
        if self.clean and self.caveats:                   # qualify a clean verdict with the silence
            head += f" (modulo {len(self.caveats)} unmodelled statement(s))"
        lines = [f"{len(self.steps)} edit(s) -> {head}"]
        for i, s in enumerate(self.steps, 1):
            lines.append(f"  {i}. fix {s.target_label!r} ({s.target_kind}, line {s.target_line}) "
                         f"via {s.operator} [fit {s.fit:.2f}] -> {s.remaining} left")
        for c in self.caveats:
            lines.append(f"  ! {c.headline()}")
        return lines


def repair_all(intake: Intake, hypothesis: dict[str, str], *, max_steps: int = 12) -> RepairPlan:
    """Repair a WHOLE function to a fixpoint: while any outcome remains under `hypothesis`, retrieve
    + verify candidate edits for it, keep only those that **make progress** (strictly fewer outcomes)
    AND introduce **no new outcome** (regression-checking — a new label appearing is rejected), CHOOSE
    the graded-best, apply it, and re-analyze the edited source. Returns the clean source + an audit
    log. Means-ends toward a goal STATE (a clean function), not a single-site patch.

    Each candidate is judged by re-executing the edited source through `analyze_all` (every effect),
    so a guard that clears an AttributeError but a lingering returns-None is still counted honestly,
    and an edit that trades one bug for another is refused. If no regression-free edit removes the
    current outcome, the plan stops with `stuck` set (an honest 'I can't fix this locally')."""
    source = intake.source
    steps: list[RepairStep] = []

    for _ in range(max_steps):
        cur = intake_function(source)
        outcomes = analyze_all(cur, hypothesis)
        if not outcomes:
            return RepairPlan(source=source, steps=steps, clean=True, caveats=caveats(cur))
        target = outcomes[0]
        prev_labels = {o.label for o in outcomes}
        provides_fn, analyzer = EFFECTS[target.kind]

        # retrieve + materialize edits for the target's effect, then keep the regression-free ones.
        cands = candidate_edits(cur, hypothesis, target,
                                provides_fn=provides_fn, analyzer=analyzer)
        accepted: list[Candidate] = []
        residual_of: dict[str, list[Outcome]] = {}
        for c in cands:
            resid = analyze_all(intake_function(c.v2_source), hypothesis)
            makes_progress = len(resid) < len(outcomes)
            introduces = {o.label for o in resid} - prev_labels     # a NEW outcome = regression
            if makes_progress and not introduces:
                accepted.append(c)
                residual_of[c.name] = resid
        if not accepted:
            return RepairPlan(source=source, steps=steps, clean=False, stuck=target)

        winner, _trace = _choose(accepted, lambda c: min(c.locality, c.compactness))
        winner = winner or accepted[0]
        source = winner.v2_source
        steps.append(RepairStep(
            target_label=target.label, target_kind=target.kind, target_line=target.line,
            operator=winner.name, description=winner.description, fit=min(winner.locality, winner.compactness),
            remaining=len(residual_of[winner.name]), source_after=source))

    final_intake = intake_function(source)
    final = analyze_all(final_intake, hypothesis)
    return RepairPlan(source=source, steps=steps, clean=not final,
                      stuck=final[0] if final else None, caveats=caveats(final_intake))


def analyze_source(src: str, hypothesis: dict[str, str]) -> tuple[Intake, list[Outcome]]:
    """Convenience: intake `src` then analyze under `hypothesis`."""
    intake = intake_function(src)
    return intake, analyze(intake, hypothesis)
