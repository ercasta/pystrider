"""`pystrider.constraints` — the prototype: a constraint is `patterns.py`'s
own shape (`structure => description`, forward-chained, deposited as a
component), pointed at a judgment instead of a neutral description. See
the module's own docstring for what is deliberately simplified and why."""
from __future__ import annotations

from loopingrules.loop import Loop
from pystrider import constraints, patterns
from pystrider.constraints import MAX_LOOPS, TooManyLoops, max_loops
from pystrider.intake import Function, intake
from pystrider.patterns import LoopCount


def load(source: str, origin: str = "<test>"):
    loop = Loop()
    patterns.install(loop)
    constraints.install(loop)
    intake(source, loop.world, origin)
    loop.run()
    return loop.world


def function_with(n_loops: int) -> str:
    body = "".join(f"    for x{i} in xs:\n        pass\n" for i in range(n_loops))
    return f"def f(xs):\n{body}" if body else "def f(xs):\n    return 1\n"


def test_a_function_at_the_limit_is_not_flagged():
    w = load(function_with(MAX_LOOPS))
    (function, _fn), = w.each(Function)
    assert w.get(function, LoopCount) == LoopCount(MAX_LOOPS)
    assert w.get(function, TooManyLoops) is None


def test_a_function_past_the_limit_is_flagged():
    w = load(function_with(MAX_LOOPS + 1))
    (function, _fn), = w.each(Function)
    assert w.get(function, TooManyLoops) == TooManyLoops(MAX_LOOPS + 1, MAX_LOOPS)


def test_the_violation_carries_what_it_was_checked_against():
    # Not just a bare tag -- `count`/`limit` are inspectable on the fact
    # itself, the same way any other derived component here is.
    w = load(function_with(MAX_LOOPS + 3))
    (function, _fn), = w.each(Function)
    violation = w.get(function, TooManyLoops)
    assert violation.count == MAX_LOOPS + 3
    assert violation.limit == MAX_LOOPS


def test_a_loop_free_function_is_not_flagged():
    w = load(function_with(0))
    (function, _fn), = w.each(Function)
    assert w.get(function, TooManyLoops) is None


def test_several_functions_are_judged_independently():
    w = load(
        "def under():\n    for x in xs:\n        pass\n"
        "\n"
        "def over():\n"
        + "".join(f"    for x{i} in xs:\n        pass\n"
                  for i in range(MAX_LOOPS + 2))
    )
    flagged = {fn.name for e, fn in w.each(Function) if w.has(e, TooManyLoops)}
    assert flagged == {"over"}


def test_max_loops_depends_on_loop_count_having_already_run():
    # `max_loops` reads `LoopCount`, it never counts anything itself --
    # installed alone, with no `patterns.loop_count` to feed it, it finds
    # nothing to judge at all, not a wrong (zero) count for everyone.
    loop = Loop()
    constraints.install(loop)          # `patterns` deliberately NOT installed
    intake(function_with(MAX_LOOPS + 5), loop.world, "<test>")
    loop.run()
    assert loop.world.each(TooManyLoops) == []
    assert loop.world.each(LoopCount) == []


def test_recounting_an_unflagged_function_is_not_a_change():
    # `without=TooManyLoops` -- settling depends on this never re-attaching
    # an equal value forever.
    w = load(function_with(MAX_LOOPS + 1))
    before = w.revision
    max_loops(w)
    assert w.revision == before
