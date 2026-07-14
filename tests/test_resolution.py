"""Tests for cross-cutting constraint resolution (grammapy vision.md §12).

A cross-cutting constraint (`requires <capability>`) narrows a decision point's productions to those that
provide it, resolving to exactly one of: Forced (unique), Defaulted (spec silent), Surfaced (several, no
preference — a design-time decision), Rejected (none provides it). Never a silent inferred pick.
"""
import pytest

from grammapy import (
    Production, DecisionPoint, resolve, Forced, Defaulted, Surfaced, Rejected,
)

# a persistence decision, in the shape of the vision doc's running example.
PERSISTENCE = DecisionPoint(
    "persistence",
    productions=(
        Production("file", frozenset({"store"})),
        Production("sql", frozenset({"store", "tx"})),
        Production("memory", frozenset({"store"})),
    ),
    default="file",
)


def test_silent_spec_takes_the_default():
    r = resolve(PERSISTENCE, [])
    assert isinstance(r, Defaulted) and r.production == "file"


def test_a_requirement_that_narrows_to_one_is_forced():
    r = resolve(PERSISTENCE, ["tx"])          # only sql provides tx
    assert isinstance(r, Forced) and r.production == "sql" and r.reason == "unique"
    assert "tx" in str(r)


def test_several_survivors_with_no_preference_surface():
    r = resolve(PERSISTENCE, ["store"])       # file, sql, memory all provide store
    assert isinstance(r, Surfaced)
    assert set(r.survivors) == {"file", "sql", "memory"}


def test_a_declared_preference_tie_breaks_the_survivors():
    point = DecisionPoint("persistence", PERSISTENCE.productions, default="file",
                          preference=("memory", "file", "sql"))
    r = resolve(point, ["store"])
    assert isinstance(r, Forced) and r.production == "memory" and r.reason == "preference"


def test_an_unsatisfiable_requirement_is_rejected():
    r = resolve(PERSISTENCE, ["graph"])       # no production provides graph
    assert isinstance(r, Rejected) and r.requirement == frozenset({"graph"})
    assert "graph" in str(r)


def test_a_requirement_no_single_production_satisfies_is_rejected():
    # tx AND cache: sql has tx but not cache; none provides both -> rejected (not a partial pick).
    point = DecisionPoint("p", (
        Production("sql", frozenset({"store", "tx"})),
        Production("redis", frozenset({"store", "cache"})),
    ), default="sql")
    r = resolve(point, ["tx", "cache"])
    assert isinstance(r, Rejected)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
