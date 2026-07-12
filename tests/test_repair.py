"""Behaviour pins for whole-function auto-fix (`repair_all`) — means-ends toward a CLEAN function.

`repair_all` iterates: while any outcome (of any effect) remains under the hypothesis, retrieve +
verify candidate edits, keep only those that make PROGRESS (strictly fewer outcomes) and introduce
NO new outcome (regression-checking), CHOOSE the graded-best, apply it, and re-analyze — until the
function is clean or honestly `stuck`. It returns the edited source plus an audit log.
"""
from pystrider import intake_function, analyze_all, repair_all


TWO_EFFECTS = """
def process(cfg, data):
    conn = cfg
    a = conn.open()
    rows = data
    return rows
"""

TWO_DEREFS = """
def f(a, b):
    x = a
    y = b
    p = x.go()
    return y.run()
"""

SAFE = """
def f(x):
    if x is not None:
        return x.go()
    return 0
"""


def test_repairs_a_mixed_effect_function_to_clean():
    ik = intake_function(TWO_EFFECTS)
    hyp = {"cfg": "none", "data": "none"}
    assert len(analyze_all(ik, hyp)) == 2                    # an AttributeError AND a returns-None
    plan = repair_all(ik, hyp)
    assert plan.clean and plan.stuck is None
    assert [s.target_kind for s in plan.steps] == ["attribute_error", "returns_none"]
    assert [s.operator for s in plan.steps] == ["guard_base", "coalesce_or"]
    # the returned source REALLY is clean under re-execution (not just claimed)
    assert analyze_all(intake_function(plan.source), hyp) == []


def test_each_edit_makes_monotone_progress():
    plan = repair_all(intake_function(TWO_EFFECTS), {"cfg": "none", "data": "none"})
    remaining = [s.remaining for s in plan.steps]
    assert remaining == sorted(remaining, reverse=True)      # strictly decreasing outcome count
    assert remaining[-1] == 0                                # ends at zero -> clean


def test_multiple_derefs_each_get_their_own_guard():
    plan = repair_all(intake_function(TWO_DEREFS), {"a": "none", "b": "none"})
    assert plan.clean
    assert len(plan.steps) == 2 and all(s.operator == "guard_base" for s in plan.steps)


def test_step_budget_leaves_an_honest_stuck_outcome():
    # cap the budget below the number of fixes needed -> not clean, but honest about what remains.
    plan = repair_all(intake_function(TWO_EFFECTS), {"cfg": "none", "data": "none"}, max_steps=1)
    assert not plan.clean and plan.stuck is not None
    assert len(plan.steps) == 1
    assert len(analyze_all(intake_function(plan.source), {"cfg": "none", "data": "none"})) == 1


def test_a_clean_function_needs_no_edits():
    plan = repair_all(intake_function(SAFE), {"x": "none"})
    assert plan.clean and plan.steps == []


def test_summary_is_a_readable_audit_log():
    plan = repair_all(intake_function(TWO_EFFECTS), {"cfg": "none", "data": "none"})
    text = "\n".join(plan.summary())
    assert "2 edit(s) -> repaired to clean" in text
    assert "conn.open" in text and "return rows" in text
