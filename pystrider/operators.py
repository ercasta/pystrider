"""The transformation-operator library (design §3, step 2) — operators as DATA, retrieved by
effect via backward-CHAIN.

Instead of a hard-coded Python list of edits, each operator is a record keyed by the **outcome
it prevents** (`attribute_error`) and a **precondition** it needs. Retrieval runs through the
public firmware: the library is materialized as facts, and a single CHAIN rule
(`?op applies_to ?site when ?op prevents ?err and ?site raises ?err and ?op needs ?cond and
?site provides ?cond`) is asked backward from the goal "which operators apply to this site?".
An operator whose precondition the site doesn't satisfy is never retrieved — e.g. the
root-param guards are excluded when the deref's value doesn't trace to a parameter.

The effect vocabulary (`attribute_error`, `raises`) is exactly what the analysis produces —
the shared vocabulary the design says lets backward-CHAIN connect goal to operator. Only the
*mechanism* (the AST rewrite behind each strategy) stays Python.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import ugm as h
from ugm import load_machine_rules, ask_goal

from .intake import Intake
from .transform import insert_none_guard, insert_none_guard_range


@dataclass(frozen=True)
class Operator:
    name: str
    prevents: str                # the outcome kind this operator removes (effect key)
    needs: str                   # the precondition the site must `provide` to be applicable
    strategy: str                # dispatch key into STRATEGIES (the mechanism)
    description: str
    locality: float              # graded fit dimensions — DATA, not hard-coded in the chooser
    compactness: float


# --- helpers that read the intake facts (an operator's precondition + its strategy's inputs) ---

def root_param(intake: Intake, var: str) -> str | None:
    """The parameter `var`'s value traces back to via a single `var = <param>` assignment. Works in
    SOURCE-name space (in/out), translating to namespaced graph-node ids at the fact boundary."""
    f = intake.facts
    vid = intake.var_id(var)
    stmt = next((s for (s, p, o) in f if p == "assigns" and o == vid), None)
    if not stmt:
        return None
    e = next((o for (s, p, o) in f if s == stmt and p == "from_expr"), None)
    src = next((o for (s, p, o) in f if s == e and p == "reads"), None)
    src_name = intake.var_source(src) if src else None
    return src_name if src_name in intake.params else None


def assign_line(intake: Intake, var: str) -> int | None:
    vid = intake.var_id(var)
    stmt = next((s for (s, p, o) in intake.facts if p == "assigns" and o == vid), None)
    return intake.line_of.get(stmt) if stmt else None


def provides(intake: Intake, base_var: str) -> set[str]:
    """The precondition tokens the deref site satisfies (what operators can match against)."""
    conds = {"deref_base_known"} if base_var else set()
    if root_param(intake, base_var):
        conds.add("root_param_known")
    return conds


# --- the library (DATA) --------------------------------------------------------------------

LIBRARY: list[Operator] = [
    Operator("guard_base", "attribute_error", "deref_base_known", "guard_deref_base",
             "wrap the deref in `if {var} is not None:` (most local)", locality=1.0, compactness=1.0),
    Operator("guard_param", "attribute_error", "root_param_known", "guard_root_param",
             "wrap the deref in `if {var} is not None:` (root cause)", locality=0.7, compactness=1.0),
    Operator("guard_param_wide", "attribute_error", "root_param_known", "guard_root_param_wide",
             "wrap the assignment through the deref in `if {var} is not None:` (wider)",
             locality=0.7, compactness=0.5),
]

# strategy -> (guard variable, source transform). The only Python mechanism; everything above is data.
STRATEGIES: dict[str, Callable[[Intake, "Outcome"], tuple[str, str]]] = {
    "guard_deref_base": lambda ik, oc: (
        oc.base_var, insert_none_guard(ik.source, oc.base_var, oc.line)),
    "guard_root_param": lambda ik, oc: (
        root_param(ik, oc.base_var),
        insert_none_guard(ik.source, root_param(ik, oc.base_var), oc.line)),
    "guard_root_param_wide": lambda ik, oc: (
        root_param(ik, oc.base_var),
        insert_none_guard_range(ik.source, root_param(ik, oc.base_var),
                                assign_line(ik, oc.base_var), oc.line)),
}


# --- retrieval via backward-CHAIN over the effect key + precondition -------------------------

_RETRIEVAL_CNL = Path(__file__).with_name("operators.cnl").read_text(encoding="utf-8")


def retrieve(site: str, error_kind: str, site_provides: set[str]) -> list[Operator]:
    """Backward-CHAIN the operator library: which operators prevent `error_kind` at `site` AND
    have a precondition the site provides? Runs entirely through the public `ask_goal`."""
    rules = load_machine_rules(_RETRIEVAL_CNL)
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x):
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    def rel(s, p, o): g.add_relation(n(s), p, n(o))
    for op in LIBRARY:
        rel(op.name, "is_a", "operator")
        rel(op.name, "prevents", op.prevents)
        rel(op.name, "needs", op.needs)
    rel(site, "raises", error_kind)
    for c in site_provides:
        rel(site, "provides", c)

    answers = ask_goal(g, f"who applies_to {site}", rules)      # backward-CHAIN retrieval
    applicable = {a.split(" ", 1)[0] for a in answers}          # "guard_base applies_to attr5" -> name
    by_name = {op.name: op for op in LIBRARY}
    return [by_name[name] for name in applicable if name in by_name]
