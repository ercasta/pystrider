"""Tests for the exclusive-choice combinator (grammapy vision.md §3.4, §4.3).

Choice is sound iff its guards PARTITION the domain `enum ∪ {absent}` — pairwise disjoint AND jointly
exhaustive — so exactly one production fires per spec (the determinacy analysis, static and decidable).
The fixture is the vision doc's own persistence-strategy example (§7.1): `sql` (the default, guarded by
key-absence too), `document`, `in_memory`.
"""
import pytest

from grammapy import (
    ABSENT, Choice, CompositionError, Guard, GuardedProduction, guard_coverage,
)

ENUM = ("sql", "document", "in_memory")


def _persistence_choice():
    """The vision.md §7.1 persistence Choice: guards partition {sql, document, in_memory, absent}."""
    return [
        GuardedProduction("sql", Guard.of("sql", absent=True)),   # default branch: absent | key=sql
        GuardedProduction("document", Guard.of("document")),
        GuardedProduction("in_memory", Guard.of("in_memory")),
    ]


def test_partitioning_guards_are_admitted():
    Choice.check(ENUM, _persistence_choice())          # no raise == the guards partition the domain


def test_select_picks_the_one_satisfied_production():
    prods = _persistence_choice()
    assert Choice.select(prods, "document").label == "document"
    assert Choice.select(prods, "in_memory").label == "in_memory"
    assert Choice.select(prods, "sql").label == "sql"
    assert Choice.select(prods, ABSENT).label == "sql"     # spec silent -> the default branch fires


def test_overlapping_guards_are_rejected_as_not_disjoint():
    prods = [
        GuardedProduction("sql", Guard.of("sql", absent=True)),
        GuardedProduction("document", Guard.of("document")),
        GuardedProduction("also_sql", Guard.of("sql")),        # a second claimant of `sql`
        GuardedProduction("in_memory", Guard.of("in_memory")),
    ]
    with pytest.raises(CompositionError) as ctx:
        Choice.check(ENUM, prods)
    msg = str(ctx.value)
    assert "do not partition" in msg
    assert "sql" in msg and "also_sql" in msg              # the shared state + both productions named


def test_non_exhaustive_guards_are_rejected_as_a_gap():
    prods = [
        GuardedProduction("sql", Guard.of("sql", absent=True)),
        GuardedProduction("document", Guard.of("document")),
        # in_memory is in the enum but no production admits it -> a gap
    ]
    with pytest.raises(CompositionError) as ctx:
        Choice.check(ENUM, prods)
    assert "in_memory" in str(ctx.value) and "no production" in str(ctx.value)


def test_missing_absent_branch_is_a_gap():
    # every enum value covered, but the key-absent state (a silent spec) is not -> not exhaustive.
    prods = [
        GuardedProduction("sql", Guard.of("sql")),        # no `absent=True` this time
        GuardedProduction("document", Guard.of("document")),
        GuardedProduction("in_memory", Guard.of("in_memory")),
    ]
    conflicts = guard_coverage(ENUM, prods)
    assert any(str(c) == "state `absent` is admitted by no production" for c in conflicts)


def test_guard_literal_outside_the_enum_is_rejected():
    prods = [
        GuardedProduction("sql", Guard.of("sql", absent=True)),
        GuardedProduction("document", Guard.of("document")),
        GuardedProduction("mystery", Guard.of("graphdb")),     # graphdb is not in the enum
        GuardedProduction("in_memory", Guard.of("in_memory")),
    ]
    with pytest.raises(CompositionError) as ctx:
        Choice.check(ENUM, prods)
    assert "graphdb" in str(ctx.value) and "not in the declared enum" in str(ctx.value)


def test_coverage_is_order_independent():
    prods = _persistence_choice()
    assert guard_coverage(ENUM, prods) == []
    assert guard_coverage(ENUM, list(reversed(prods))) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
