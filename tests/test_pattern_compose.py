"""Pins for pattern composition by intent (experiments/pattern_compose.py).

The humble target: patterns represented as intent-tagged RULES, composed by intent, checked by RUNNING,
repaired LOCALLY where a sub-part betrays its intent — no grammapy, no proofs. These pins hold: (1) a
sound guess ships on the first run; (2) a wrong filter is localized to that sub-intent and repaired;
(3) a wrong reducer likewise; (4) both-wrong is fixed one sub-part at a time; (5) an unrepairable intent
is an honest refusal; (6) `localize` names the deepest sub-part that betrays its intent; and (7) the
UNDERSTAND mirror recognizes a pattern from raw code, buggy variant included.
"""
from experiments.pattern_compose import (
    GOAL, ENV, Pattern, develop, compose, localize, value, recognize, REPERTOIRE,
)


def test_sound_guess_ships_on_first_run():
    dev = develop(GOAL, ENV)
    assert dev.ok
    assert len(dev.steps) == 1 and "SHIP" in dev.steps[0]
    assert value(dev.final, ENV) == 4.0


def test_wrong_filter_is_localized_and_repaired():
    dev = develop(GOAL, ENV, guess={"positives_of": "keep_nonneg"})
    assert dev.ok
    assert any("localized fault to intent 'positives_of'" in s for s in dev.steps)
    assert any("keep_nonneg` -> `keep_strict`" in s for s in dev.steps)
    assert value(dev.final, ENV) == 4.0


def test_wrong_reducer_is_localized_and_repaired():
    dev = develop(GOAL, ENV, guess={"average_of": "total"})
    assert dev.ok
    assert any("localized fault to intent 'average_of'" in s for s in dev.steps)
    assert any("total` -> `mean`" in s for s in dev.steps)


def test_both_wrong_repaired_one_subpart_at_a_time():
    dev = develop(GOAL, ENV, guess={"positives_of": "keep_nonneg", "average_of": "total"})
    assert dev.ok
    repairs = [s for s in dev.steps if "REPAIR" in s]
    assert len(repairs) == 2                              # the filter, then the reducer
    assert "positives_of" in repairs[0] and "average_of" in repairs[1]


def test_unrepairable_intent_is_an_honest_refusal():
    # a crippled repertoire whose only positives_of pattern is the buggy one -> no swap available.
    crippled = {
        "positives_of": [Pattern("keep_nonneg", "positives_of", ("s",), "[e for e in {s} if e >= 0]")],
        "average_of": REPERTOIRE["average_of"],
    }
    dev = develop(GOAL, ENV, rep=crippled)
    assert not dev.ok
    assert "no other pattern realizes intent 'positives_of'" in dev.refusal


def test_localize_names_the_deepest_betraying_subpart():
    root = compose(GOAL, {"positives_of": "keep_nonneg"})   # filter wrong, reducer right
    culprit = localize(root, ENV)
    assert culprit.intent == "positives_of"                 # the filter, not the (faithful) average above it


def test_understand_recognizes_patterns_from_raw_code():
    assert recognize("[e for e in xs if e > 0]") == ("positives_of", "keep_strict")
    assert recognize("[e for e in xs if e >= 0]") == ("positives_of", "keep_nonneg")   # the buggy variant
    assert recognize("sum(xs) / len(xs)") == ("average_of", "mean")
    assert recognize("sum(xs)") == ("average_of", "total")
    assert recognize("xs + 1") is None                      # nothing in the repertoire matches
