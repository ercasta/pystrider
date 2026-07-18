"""Pins for the reach measurement (experiments/reach_curve.py).

The claim under test is the project's coverage claim: a small fixed rule set NAVIGATES to a much larger
set of programs than it has rules, and says so honestly when it cannot. These pins walk a reduced grid
(the probe walks the full one) and assert the two properties that make the number mean anything —
predicted reach matches actual reach, and nothing ships silently wrong.
"""
from experiments.reach_curve import TRANSFORMS, grid, measure, summarize


_CACHE = []


def _walk():
    """The reduced grid, walked ONCE. The build loop is deterministic, so re-walking it per pin would
    only multiply ~8s of planner runs by the number of tests."""
    if not _CACHE:
        _CACHE.extend(measure(*case) for case in grid(full=False))
    return _CACHE


def test_predicted_reach_matches_ACTUAL_reach_in_both_directions():
    # every case is labelled reachable-or-not IN ADVANCE from the rule set. Two ways to be wrong: a
    # spec we called reachable that refuses (the rules are weaker than we think), and one we called
    # unreachable that ships (our model of the closure is wrong, or the loop cheated).
    outcomes = _walk()
    s = summarize(outcomes)
    assert s["in_closure_shipped"] == s["in_closure"], \
        [o.label for o in outcomes if o.reachable and o.kind != "shipped"]
    assert s["out_closure_refused"] == s["out_closure"], \
        [o.label for o in outcomes if not o.reachable and o.kind == "shipped"]
    assert s["in_closure"] and s["out_closure"]          # the grid must exercise both sides


def test_nothing_ships_SILENTLY_WRONG():
    # THE falsifying outcome. Each shipped program is re-executed by the probe and checked against its
    # spec independently of the loop's own verdict — an unreachable spec refused by name is an honest
    # boundary, but a shipped-and-wrong program would mean the method does not work.
    outcomes = _walk()
    assert summarize(outcomes)["silent_wrong"] == 0, \
        [(o.label, o.wanted, o.got) for o in outcomes if o.kind == "SILENT WRONG"]


def test_reach_comes_from_COMPOSING_repairs_not_from_any_single_rule():
    # the composition claim, as a number: successes that needed more than one repair APPLIED. If every
    # success were reachable in one hop, the loop would be a lookup table with extra steps.
    outcomes = _walk()
    composed = [o for o in outcomes if o.kind == "shipped" and o.repairs >= 2]
    assert composed, "no spec required composing repairs — the grid is not exercising the claim"
    assert max(o.repairs for o in outcomes) >= 2


def test_a_function_being_AVAILABLE_does_not_put_it_in_reach():
    # `shout` exists as a repair and still cannot uppercase a RAW value, because it only ever wraps an
    # already-greeted payload. Reach is the closure of what the rules compose to, not the set of
    # functions lying around — the distinction that makes "reach" a real measurement.
    assert TRANSFORMS["shout_only"][1] is None
    assert TRANSFORMS["loud"][1] == 2                    # ...though shout IS reachable when composed
    outcomes = {o.label: o for o in _walk()}
    assert outcomes["flat/1/shout_only"].kind == "unverified"
    assert outcomes["flat/1/loud"].kind == "shipped"


def test_the_loop_SHAPE_costs_no_reach():
    # the same transforms, inside a `for` body: reachable transforms stay reachable and are repaired by
    # the same rules, which is what "the pattern did not need loop-aware repairs" means empirically.
    outcomes = {o.label: o for o in _walk()}
    for t in ("plain", "greet", "loud"):
        assert outcomes["loop/" + t].kind == "shipped", t
        assert outcomes["flat/1/" + t].kind == "shipped", t
    assert outcomes["loop/shout_only"].kind == "unverified"
