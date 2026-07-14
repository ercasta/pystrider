"""Pins for the method_not_found effect (API absorption Track A, slice 4).

A SECOND library-shaped effect (the mirror of slice C's returns_none): reasoning over the ABSORBED
`has_method` facts — with NO per-library rule — flags a method call whose receiver type does not declare
the method. The receiver type is established by a one-hop flow: a parameter's given type, or the
absorbed RETURN type of a call assigned to a variable (`r = s.repo()` -> r: _DemoRepo). Conservative: an
unknown receiver type or an undecidable return propagates nothing, so there is no false positive.
"""
import pytest

from pystrider import absorb
from experiments.api_absorption import (
    find_method_not_found, infer_types, _DemoRepo, _DemoSession,
)
from pystrider.intake import intake_function


def _bank():
    return absorb(_DemoSession).facts + absorb(_DemoRepo).facts


def test_a_method_absent_on_a_given_receiver_type_is_flagged():
    # direct case: t: _DemoRepo, which has no `missing` -> the method access raises.
    src = "def g(t, k):\n    return t.missing(k)\n"
    assert find_method_not_found(src, {"t": "_DemoRepo"}, _bank()) == ["t.missing"]


def test_a_method_present_on_the_type_is_not_flagged():
    src = "def h(t, k):\n    return t.find(k)\n"          # _DemoRepo HAS find
    assert find_method_not_found(src, {"t": "_DemoRepo"}, _bank()) == []


def test_a_method_absent_on_a_calls_RETURNED_type_is_flagged():
    # the design's headline case: r's type is inferred _DemoRepo from the absorbed return of s.repo(),
    # and _DemoRepo has no `delete` -> the chained method access raises.
    src = "def f(s, k):\n    r = s.repo()\n    return r.delete(k)\n"
    assert find_method_not_found(src, {"s": "_DemoSession"}, _bank()) == ["r.delete"]


def test_the_inferred_receiver_type_flows_from_the_absorbed_return():
    # the one-hop type flow itself: s (given) -> r via s.repo()'s absorbed `returns _DemoRepo`.
    ik = intake_function("def f(s, k):\n    r = s.repo()\n    return r.delete(k)\n")
    types = infer_types(ik, {"s": "_DemoSession"}, _bank())
    assert types["s"] == "_DemoSession" and types["r"] == "_DemoRepo"


def test_an_unknown_receiver_type_is_conservative():
    # no receiver type given and none inferrable -> no `on_type`, so the rule never fires (no guess).
    src = "def f(s, k):\n    r = s.repo()\n    return r.delete(k)\n"
    assert find_method_not_found(src, {}, _bank()) == []


def test_a_present_method_on_the_returned_type_is_not_flagged():
    # r: _DemoRepo (inferred), and _DemoRepo HAS find -> no false positive on the chained access.
    src = "def f(s, k):\n    r = s.repo()\n    return r.find(k)\n"
    assert find_method_not_found(src, {"s": "_DemoSession"}, _bank()) == []


def test_the_receivers_own_method_call_is_not_flagged():
    # s.repo() itself must not be flagged — _DemoSession HAS repo (only the ABSENT method raises).
    src = "def f(s, k):\n    r = s.repo()\n    return r.delete(k)\n"
    hits = find_method_not_found(src, {"s": "_DemoSession"}, _bank())
    assert "s.repo" not in hits and hits == ["r.delete"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
