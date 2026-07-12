"""Behaviour pins for Slice C — a SECOND effect kind (docs/implementation_plan.md).

Proves the operator library + backward-CHAIN retrieval + CHOOSE + verify-by-re-execution generalize
past the None-deref effect: a `returns_none` outcome (a function returns None when a non-None was
intended) is authored as ONE more semantics rule + two library operators, with NO new machinery —
and the None-deref path is unchanged.
"""
from pystrider import (intake_function, analyze, analyze_return_none, choose_repair)
from pystrider import operators as ops


RETURNS_NONE = """
def f(x):
    y = x
    return y
"""

# a function with BOTH a deref and a return, to show the two effects are independent
BOTH = """
def g(x):
    y = x
    z = y.bar()
    return y
"""


def test_returns_none_effect_fires_and_is_sound():
    ik = intake_function(RETURNS_NONE)
    outs = analyze_return_none(ik, {"x": "none"})
    assert [(o.label, o.base_var, o.kind) for o in outs] == [("return y", "y", "returns_none")]
    # the RECORD trace threads the hypothesis to the return via the value flow
    joined = "\n".join(outs[0].trace)
    assert "returns_none yes" in joined and "has_value none" in joined
    # soundness: a non-None input returns non-None -> no outcome
    assert analyze_return_none(ik, {"x": "object"}) == []


def test_two_effects_are_independent():
    ik = intake_function(RETURNS_NONE)
    # the returns-None function has no attribute access -> the None-deref effect never fires
    assert analyze(ik, {"x": "none"}) == []
    assert analyze_return_none(ik, {"x": "none"}) != []


def test_both_effects_coexist_on_one_function():
    ik = intake_function(BOTH)
    assert [o.label for o in analyze(ik, {"x": "none"})] == ["y.bar"]         # effect 1
    assert [o.label for o in analyze_return_none(ik, {"x": "none"})] == ["return y"]  # effect 2


def test_choose_repair_selects_a_verified_edit_for_the_new_effect():
    ik = intake_function(RETURNS_NONE)
    outcome = analyze_return_none(ik, {"x": "none"})[0]
    sel = choose_repair(ik, {"x": "none"}, outcome,
                        provides_fn=ops.provides_return, analyzer=analyze_return_none)
    # both coalesce operators are retrieved by backward-CHAIN on the `returns_none` effect key
    assert {c.name for c in sel.candidates} == {"coalesce_or", "coalesce_ifexp"}
    assert all(c.cleared for c in sel.candidates)          # each verified by re-execution
    # CHOOSE picks the graded-best (the compact `or`, fit 1.0, over the explicit ifexp, 0.7)
    assert sel.winner.name == "coalesce_or"
    assert sel.winner.v2_source.strip().endswith("return y or {}")


def test_none_deref_repair_is_unchanged():
    # the original effect's means-ends selection still picks the local guard (no regression from
    # generalizing candidate_edits/choose_repair to take a provides_fn + analyzer).
    ik = intake_function("def f(x):\n    y = x\n    return y.bar()\n")
    outcome = analyze(ik, {"x": "none"})[0]
    sel = choose_repair(ik, {"x": "none"}, outcome)      # defaults = the None-deref effect
    assert sel.winner.name == "guard_base"
    assert {c.name for c in sel.candidates} == {"guard_base", "guard_param", "guard_param_wide"}
