"""Pins the state-succession feasibility probe (experiments/state_threading.py).

The reassignment program:  y = x (None); y = z (obj); return y.bar()
State-threading over a pre-materialized cell lattice must:
  - give y = None after st1 but y = obj (NOT None) after st2 (reassignment), and
  - frame x forward unchanged, and
  - NOT raise at the deref in p2, but raise if the deref were in p1.
"""
from experiments.state_threading import Transition, build, value_at, raises

STATES = ["p0", "p1", "p2"]
VARS = ["x", "y", "z"]
TRANSITIONS = [
    Transition(frm="p0", to="p1", assigns="y", reads="x"),   # y = x
    Transition(frm="p1", to="p2", assigns="y", reads="z"),   # y = z
]
SEEDS = [("p0", "x", "none"), ("p0", "z", "obj")]


def _kb(deref):
    return build(STATES, VARS, TRANSITIONS, deref, SEEDS)


def test_reassignment_threads_correctly():
    g, rg, rules = _kb(deref=("ea", "y", "p2"))
    assert value_at(g, rules, "p1", "y", "none")        # y is None right after st1
    assert value_at(g, rules, "p2", "y", "obj")         # y is obj after st2 ...
    assert not value_at(g, rules, "p2", "y", "none")    # ... and NOT still None (the SSA bug)


def test_frame_axiom_carries_unchanged_vars():
    g, rg, rules = _kb(deref=("ea", "y", "p2"))
    assert value_at(g, rules, "p2", "x", "none")        # x framed forward across both transitions


def test_no_false_raise_after_reassignment():
    g, rg, rules = _kb(deref=("ea", "y", "p2"))
    assert not raises(g, rules, "ea")                   # y is obj at p2 -> safe


def test_raise_when_deref_precedes_reassignment():
    # control: the same deref one state earlier (p1, y still None) MUST raise
    g, rg, rules = _kb(deref=("eb", "y", "p1"))
    assert raises(g, rules, "eb")
