"""Operational semantics as a ugm rule bank (docs/code_reasoning_design.md §2).

This is the heart of the dynamic reframe: instead of a precomputed data-flow graph, value
flow is *computed by these rules* — a demand-driven abstract interpretation. The rules are
DATA (machine-rule CNL), authored the ugm way; this module owns no engine code.

Abstract domain (the spike minimum): a value is `none` (typed `none_value`) or an opaque
object (typed `object_value`) or UNKNOWN. The design's "concrete-or-UNKNOWN first".

Authoring gotcha learned in the spike: every machine-rule clause is a **3-token triple**
`S P O`. A boolean-shaped predicate therefore needs an explicit object — we write
`?g guard_open yes`, `?e reached yes`, not `?g guard_open`. A 2-token clause is silently
mis-parsed (the trailing keyword is eaten as the object). NACs (`not ...`) DO fire under the
demand-driven `suppose`/`chain_sip` path — verified.
"""
from __future__ import annotations

import ugm as h
from ugm import load_machine_rules, write_rule, AttrGraph


# Each line is one Horn rule: HEAD when BODY1 and BODY2 ...  (a `not` clause is a NAC.)
SEMANTICS = "\n".join([
    # (1) a Name expression evaluates to the current value of the variable it reads
    "?e eval_to ?v when ?e is_a name and ?e reads ?var and ?var has_value ?v",
    # (2) an assignment propagates its source expression's value to the target variable
    "?var has_value ?v when ?stmt is_a assign and ?stmt assigns ?var "
    "and ?stmt from_expr ?e and ?e eval_to ?v",
    # (3) a guard `if VAR is not None:` opens only when its tested var is not a none value
    "?g guard_open yes when ?g is_a guard and ?g tests ?var and ?var has_value ?v "
    "and not ?v is_a none_value",
    # (4) reachability: a guarded expression needs its guard open ...
    "?e reached yes when ?e within_guard ?g and ?g guard_open yes",
    # (5) ... an unguarded attribute access is reached by default
    "?e reached yes when ?e is_a attribute and not ?e within_guard ?g",
    # (6) THE OUTCOME: a reached attribute access on a none-valued base raises AttributeError
    "?e raises attribute_error when ?e is_a attribute and ?e reached yes "
    "and ?e attr_of ?base and ?base eval_to ?v and ?v is_a none_value",
])


def build_rule_graph() -> AttrGraph:
    """Reify the semantics bank into a rule graph for `suppose`/`chain_sip`."""
    rules = load_machine_rules(SEMANTICS)
    rg = AttrGraph()
    for r in rules:
        write_rule(rg, r)
    return rg


def rule_list():
    """The executable rule list (for `ask_goal` when rendering a `why` trace)."""
    return load_machine_rules(SEMANTICS)
