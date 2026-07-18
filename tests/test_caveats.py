"""Pins for UNKNOWN-surfacing — "don't build on silence" (docs/critique.md weakness #5).

Intake now emits a visible `not_modelled` marker for any statement kind it cannot thread (aug-assign,
attribute/subscript store, tuple unpack, for/with, ...), instead of silently framing a stale value
forward. NB a bare CALL statement (`log(x)`) used to be in that list and is now MODELLED as an
`expr_stmt` — closing that coverage gap is what lets a structural rule see a generated program built
out of bare calls (`docs/vocabulary_bridge.md`). `caveats()` surfaces them, and `repair_all`'s `clean` verdict is QUALIFIED by
them — so "clean" means "checked and clear", not "nothing derived". A caveat is not an outcome (the
code may be fine); it is an honest "the analysis did not prove this part".
"""
import pytest

from pystrider import intake_function, caveats, analyze, analyze_all, repair_all


UNMODELLED_CASES = {
    "aug_assign":   "def f(x):\n    x += 1\n    return x",
    "attr_store":   "def f(x):\n    x.cache = 1\n    return x",
    "tuple_unpack": "def f(x):\n    a, b = x\n    return a",
    "for_loop":     "def f(x):\n    for i in x:\n        pass\n    return x",
}


@pytest.mark.parametrize("name,src", list(UNMODELLED_CASES.items()))
def test_unmodelled_statement_is_made_visible(name, src):
    """Each unmodelled statement kind produces a `not_modelled` marker and a surfaced caveat with its
    source label and line — no longer a silent skip."""
    ik = intake_function(src)
    assert len(ik.not_modelled) == 1
    cav = caveats(ik)
    assert len(cav) == 1 and cav[0].kind == "not_modelled" and cav[0].line == 2


def test_modelled_function_has_no_caveats():
    """A function of only modelled statements (assign, guard, return) surfaces NO caveats — the
    control that keeps the marker honest (it fires on real gaps, not everywhere)."""
    src = "def f(x):\n    y = x\n    if y is not None:\n        return y.v\n    return {}"
    assert intake_function(src).not_modelled == []
    assert caveats(intake_function(src)) == []


def test_not_modelled_marker_is_inert_for_analysis():
    """The marker is *visible* but semantically inert: a real outcome elsewhere is still detected, and
    the caveat is reported ALONGSIDE it — the marker does not suppress or invent outcomes."""
    src = "def f(x):\n    x += 1\n    return x.value"        # aug-assign (unmodelled) + a real deref
    ik = intake_function(src)
    outcomes = analyze(ik, {"x": "none"})
    assert [o.label for o in outcomes] == ["x.value"]         # the real AttributeError still fires
    assert [c.label for c in caveats(ik)] == ["x += 1"]       # and the silence is surfaced too


def test_repair_all_qualifies_clean_with_caveats():
    """The load-bearing fix: a function that is outcome-free but contains an unmodelled statement is
    reported as clean MODULO that statement — `fully_modelled` is False and the summary says so, so a
    'clean' verdict is never mistaken for a proof over the whole function."""
    src = "def f(x):\n    x += 1\n    return x"                # no outcome under x=object, but += is a gap
    plan = repair_all(intake_function(src), {"x": "object"})
    assert plan.clean and not plan.fully_modelled
    assert len(plan.caveats) == 1 and plan.caveats[0].label == "x += 1"
    joined = "\n".join(plan.summary())
    assert "modulo 1 unmodelled statement" in joined


def test_repair_all_clean_is_fully_modelled_when_no_gap():
    """A genuinely clean, fully-modelled repair reports `fully_modelled` True and no caveat line — the
    honest positive case, distinct from clean-with-silence."""
    src = "def f(cfg):\n    conn = cfg\n    if conn is not None:\n        a = conn.open()\n    return conn"
    plan = repair_all(intake_function(src), {"cfg": "none"})
    assert plan.clean and plan.fully_modelled and plan.caveats == []
    assert not any(line.startswith("  !") for line in plan.summary())
