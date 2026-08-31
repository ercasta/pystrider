"""`Qualname` — the dotted path `intake.py` attaches to every `Function`,
alongside its bare `name`, so two functions sharing a name in different
scopes of one file can be told apart. See `intake.py`'s own docstring on
`Qualname`, and `pystrider.resolve`'s ⚠ on what disambiguating buys (and
what it still doesn't).

    PYTHONPATH=../loopingrules python -m pytest tests/ -q
"""
from __future__ import annotations

from loopingrules.world import World

from pystrider.intake import Function, Qualname, intake


def qualnames(source: str) -> dict:
    """name -> qualname, for every function `intake()` finds in `source`."""
    w = World()
    intake(source, w, "<test>")
    return {fn.name: w.get(e, Qualname).value for e, fn in w.each(Function)}


def test_a_top_level_functions_qualname_is_just_its_name():
    assert qualnames("def f():\n    pass\n") == {"f": "f"}


def test_sibling_top_level_functions_dont_leak_scope_into_each_other():
    assert qualnames(
        "def a():\n    pass\n"
        "def b():\n    pass\n"
    ) == {"a": "a", "b": "b"}


def test_a_nested_functions_qualname_is_dotted_through_its_enclosing_def():
    assert qualnames(
        "def outer():\n"
        "    def inner():\n"
        "        pass\n"
    ) == {"outer": "outer", "inner": "outer.inner"}


def test_sibling_nested_functions_dont_leak_into_each_other_either():
    # `inner2` must not read `outer.inner1.inner2` -- scope is popped after
    # each `def`'s own body, not left on the stack for the next sibling.
    assert qualnames(
        "def outer():\n"
        "    def inner1():\n"
        "        pass\n"
        "    def inner2():\n"
        "        pass\n"
    ) == {"outer": "outer", "inner1": "outer.inner1", "inner2": "outer.inner2"}


def test_two_functions_sharing_a_bare_name_get_different_qualnames():
    w = World()
    intake(
        "def a():\n"
        "    def inner():\n"
        "        pass\n"
        "def b():\n"
        "    def inner():\n"
        "        pass\n",
        w, "<test>")
    names = sorted(w.get(e, Qualname).value for e, _tag in w.each(Function))
    assert names == ["a", "a.inner", "b", "b.inner"]
