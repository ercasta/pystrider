"""Feasibility probe — state-succession WITHOUT existential minting.

This probe settles the design's #1 open question (docs/code_reasoning_design.md,
"State-succession vs. SSA"). It is a **probe, not integrated intake**: it hand-builds a
tiny CFG rather than deriving one from `ast`. See docs/spike_findings.md §"State-succession".

Finding in two halves:

  1. WALL — "mint a successor state" cannot be expressed as an ordinary Horn rule. An
     existential head variable (`?s next_state ?s2` with `?s2` RHS-only) is NOT Skolem-minted
     by the public rule drivers: `chain_sip` collapses `?s2` onto the demand's object (SIP),
     and the forward drivers derive nothing. Genuine fresh-per-firing minting is a MINT-opcode
     capability the rule surface does not expose.

  2. WORKAROUND — move the minting to the intake tool. Intake knows the CFG statically, so it
     pre-materializes the state x var "cell" lattice; the rules then only BIND pre-existing
     cells. Pure Datalog, no existential heads. The frame axiom is a NAC: carry a var's value
     across a transition that does NOT assign it (`not ?t assigns_var ?v`). This correctly
     handles reassignment (the case SSA-per-var gets wrong) and framing.

The state-pool size intake pre-mints IS the fuel/unrolling budget — connecting this directly
to the design's "fuel / world budget" question (a loop becomes a bounded pre-materialized
state chain).
"""
from __future__ import annotations

from dataclasses import dataclass

import ugm as h
from ugm import load_machine_rules, write_rule, AttrGraph, ask_goal


# state-threading semantics — binds pre-materialized cells; mints nothing.
STATE_SEMANTICS = "\n".join([
    # ASSIGN: the target cell in the to-state takes the source cell's value in the from-state
    "?c2 has_value ?val when ?t is_a transition and ?t from_state ?s1 and ?t to_state ?s2 "
    "and ?t assigns_var ?tgt and ?t reads_var ?src "
    "and ?c1 in_state ?s1 and ?c1 for_var ?src and ?c1 has_value ?val "
    "and ?c2 in_state ?s2 and ?c2 for_var ?tgt",
    # FRAME: carry a var forward across any transition that does NOT assign it
    "?c2 has_value ?val when ?t is_a transition and ?t from_state ?s1 and ?t to_state ?s2 "
    "and ?c1 in_state ?s1 and ?c1 for_var ?v and ?c1 has_value ?val "
    "and ?c2 in_state ?s2 and ?c2 for_var ?v and not ?t assigns_var ?v",
    # OUTCOME: attribute on a none-valued base, read in the deref's state
    "?e raises attribute_error when ?e is_a attribute and ?e attr_of_var ?bv "
    "and ?e in_state ?s and ?c in_state ?s and ?c for_var ?bv "
    "and ?c has_value ?val and ?val is_a none_value",
])


@dataclass
class Transition:
    frm: str
    to: str
    assigns: str
    reads: str


def build(states, variables, transitions, deref, seeds):
    """Materialize the pre-minted cell lattice + CFG, seed param values, return (graph, rules).

    `deref` = (expr_id, base_var, state); `seeds` = list of (state, var, value_node).
    Mints nothing at reasoning time — every state and cell exists up front (the intake move).
    """
    rules = load_machine_rules(STATE_SEMANTICS)
    rg = AttrGraph()
    for r in rules:
        write_rule(rg, r)

    g = h.Graph(); ids: dict[str, str] = {}
    def n(x):
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    def rel(s, p, o): g.add_relation(n(s), p, n(o))

    rel("none", "is_a", "none_value"); rel("obj", "is_a", "object_value")
    for s in states:
        for v in variables:
            rel(f"c_{s}_{v}", "in_state", s)
            rel(f"c_{s}_{v}", "for_var", v)
    for i, t in enumerate(transitions, 1):
        tid = f"t{i}"
        rel(tid, "is_a", "transition")
        rel(tid, "from_state", t.frm); rel(tid, "to_state", t.to)
        rel(tid, "assigns_var", t.assigns); rel(tid, "reads_var", t.reads)
    eid, bvar, st = deref
    rel(eid, "is_a", "attribute"); rel(eid, "attr_of_var", bvar); rel(eid, "in_state", st)
    for s, v, val in seeds:
        rel(f"c_{s}_{v}", "has_value", val)
    return g, rg, rules


def value_at(g, rules, state, var, value) -> bool:
    return ask_goal(g, f"does c_{state}_{var} has_value {value}", rules) == ["yes"]


def raises(g, rules, expr_id) -> bool:
    return ask_goal(g, f"is {expr_id} raises attribute_error", rules) == ["yes"]
