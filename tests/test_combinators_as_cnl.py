"""Pins for the combinators-as-CNL probe (experiments/combinators_as_cnl.py).

The finding that settles the bridges-vs-channels question: grammapy's composition checks port to CNL
rule-modules over the same ugm graph, verdict-identical to the Python checks, run read-only. Two
representative shapes: SCOPE (closure — recursion + stratified negation) and ACCUMULATE (distinctness —
`?a != ?b`, ugm feedback #11). Requires the ugm build with distinctness + `ask_goal(commit=False)`.
"""
import pytest

import ugm as h
from ugm import load_machine_rules, ask_goal

from experiments.combinators_as_cnl import (
    cnl_unhandled, grammapy_unhandled, cnl_conflicts, grammapy_conflicts,
    _accumulate_facts, _graph, ACCUMULATE_RULES,
)
from experiments.app_synthesis import app_scope_tree, Spec, _button_atom


def _buttons(*names):
    return [_button_atom(b) for b in names]


@pytest.mark.parametrize("spec,screen", [
    (Spec(name="s", irreversible=True), "confirm_screen"),   # handled -> no leak
    (Spec(name="s", irreversible=True), "one_screen"),       # unhandled -> a leak
    (Spec(name="s"), "one_screen"),                          # no effect
])
def test_scope_as_cnl_matches_grammapy(spec, screen):
    tree = app_scope_tree(spec, screen)
    assert cnl_unhandled(tree) == grammapy_unhandled(tree)


def test_scope_cnl_finds_the_specific_leak():
    tree = app_scope_tree(Spec(name="s", irreversible=True), "one_screen")
    assert cnl_unhandled(tree) == {("perform_withdrawal", "needs_confirmation")}


@pytest.mark.parametrize("items", [
    _buttons("ok", "cancel"),            # disjoint -> no conflict
    _buttons("ok", "yes"),               # two proceed -> collide on confirm.submit
    _buttons("ok", "yes", "proceed"),    # three affirmatives -> still one shared channel
    _buttons("ok"),                      # a single writer must NOT self-conflict (the distinctness point)
])
def test_accumulate_as_cnl_matches_grammapy(items):
    assert cnl_conflicts(items) == grammapy_conflicts(items)


def test_accumulate_cnl_needs_no_hand_authored_distinctness():
    # the whole #11 point: the collision is DERIVED, with zero distinct_from facts supplied.
    assert cnl_conflicts(_buttons("ok", "yes")) == {"confirm.submit"}
    assert cnl_conflicts(_buttons("ok")) == set()      # single writer, no false positive


def test_the_cnl_checks_run_read_only():
    # a check must not ink the graph it checks (else running checks contaminates the graph).
    facts = _accumulate_facts(_buttons("ok", "yes"))
    g = _graph(facts)
    ask_goal(g, "who write_conflict yes", load_machine_rules(ACCUMULATE_RULES), commit=False)
    channels = {c for (_, _, c) in facts}
    standing = [a for a in ask_goal(g, "who write_conflict yes", load_machine_rules(""), commit=False)
                if a.split(" ", 1)[0] in channels]
    assert standing == []                              # nothing committed by the read-only check


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
