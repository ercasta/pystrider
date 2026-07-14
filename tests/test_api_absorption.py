"""Behaviour pins for the API-absorption probe, slice 2 (docs/api_absorption_design.md §2.B).

An ABSORBED library fact (`dict.get returns_optional yes`) + a two-rule bridge makes pystrider's
EXISTING None-deref effect fire on `x = d.get(k); x.attr` — with no None hypothesis on any parameter,
and conservatively (no false positive when the method is non-optional or the receiver type is unknown).
"""
from experiments.api_absorption import analyze_with_absorption


OPTIONAL_GET = "def f(d, k):\n    x = d.get(k)\n    return x.rows\n"
NON_OPTIONAL = "def g(s):\n    x = s.upper()\n    return x.rows\n"
ENVIRON_GET = "def h(env, name):\n    v = env.get(name)\n    return v.strip\n"


def test_absorbed_optional_call_flows_into_the_existing_deref_effect():
    # dict.get is absorbed as returns_optional -> x may be None -> x.rows raises via the UNCHANGED rule.
    assert analyze_with_absorption(OPTIONAL_GET, {"d": "dict"}) == ["x.rows"]


def test_a_second_absorbed_optional_api_works_the_same_way():
    # os.environ is (here) typed as an env whose .get is absorbed optional — same machinery, no new rule.
    assert analyze_with_absorption(ENVIRON_GET, {"env": "os.environ"}) == ["v.strip"]


def test_non_optional_method_is_not_a_false_positive():
    assert analyze_with_absorption(NON_OPTIONAL, {"s": "str"}) == []


def test_unknown_receiver_type_is_conservative():
    # no receiver type -> the call does not resolve -> no absorbed fact applies -> no false positive.
    assert analyze_with_absorption(OPTIONAL_GET, {}) == []
