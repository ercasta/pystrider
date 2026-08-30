"""`patterns.LoopCount` -- a standing, composable description (see its own
docstring for why it exists as a rule rather than an inline count), so
"how many loops does this function have" is answerable off the world by
ANYTHING, not just `pystrider.domain._reconcile_watch`, the caller that
prompted building it this way."""
from __future__ import annotations

from loopingrules.loop import Loop
from pystrider import patterns
from pystrider.intake import Function, intake
from pystrider.patterns import LoopCount


def load(source: str, origin: str = "<test>"):
    loop = Loop()
    patterns.install(loop)
    taken = intake(source, loop.world, origin)
    loop.run()
    return loop.world, taken


def test_a_function_with_no_loops_counts_zero():
    w, _ = load("def f():\n    return 1\n")
    (function, _fn), = w.each(Function)
    assert w.get(function, LoopCount) == LoopCount(0)


def test_top_level_loops_are_counted():
    w, _ = load(
        "def f(xs, ys):\n"
        "    for x in xs:\n"
        "        pass\n"
        "    for y in ys:\n"
        "        pass\n"
    )
    (function, _fn), = w.each(Function)
    assert w.get(function, LoopCount) == LoopCount(2)


def test_a_loop_nested_inside_an_if_is_NOT_counted():
    # A real, named simplification (see `LoopCount`'s own docstring): this
    # rule counts a function's DIRECT body, not its whole subtree.
    w, _ = load(
        "def f(xs, flag):\n"
        "    if flag:\n"
        "        for x in xs:\n"
        "            pass\n"
    )
    (function, _fn), = w.each(Function)
    assert w.get(function, LoopCount) == LoopCount(0)


def test_each_function_gets_its_own_count():
    w, _ = load(
        "def one(xs):\n"
        "    for x in xs:\n"
        "        pass\n"
        "\n"
        "def none():\n"
        "    return 1\n"
    )
    by_name = {fn.name: w.get(e, LoopCount).count for e, fn in w.each(Function)}
    assert by_name == {"one": 1, "none": 0}


def test_recounting_an_unchanged_function_is_not_a_change():
    # `without=LoopCount` -- `loop_count` never revisits an entity it has
    # already counted, which matters for settling: `revision` must not
    # move forever just because the rule runs every tick.
    w, taken = load("def f():\n    for x in xs:\n        pass\n")
    before = w.revision
    patterns.loop_count(w)
    assert w.revision == before
