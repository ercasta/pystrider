"""Effects — a semantic annotation built `patterns.py`'s way: forward-only,
off structure `intake.py` already produced.
"""
from __future__ import annotations

from loopingrules.loop import Loop
from pystrider import effects
from pystrider.effects import Effect
from pystrider.intake import Function, Name, intake


def load(source: str, origin: str = "<test>", only=None):
    """Intake `source` into a world carrying the effect descriptions (or a subset)."""
    loop = Loop()
    effects.install(loop, only=only)
    taken = intake(source, loop.world, origin)
    loop.run()
    return loop.world, taken


def _effects_of(w, function):
    return [(e.kind, e.detail) for e in w.get_all(function, Effect)]


def test_a_direct_attribute_mutation_is_an_effect():
    w, _ = load(
        "def save(self):\n"
        "    self.dirty = 1\n"
    )
    (function, _tag), = w.each(Function)
    assert ("mutates", "dirty") in _effects_of(w, function)


def test_a_mutation_nested_inside_a_loop_and_a_branch_still_counts():
    """⚠ Not readable off `Function`'s own `Body` directly — this is what
    `Contains` is for."""
    w, _ = load(
        "def scrub(self, items):\n"
        "    for it in items:\n"
        "        if it:\n"
        "            self.dirty = 1\n"
    )
    (function, _tag), = w.each(Function)
    assert ("mutates", "dirty") in _effects_of(w, function)


def test_a_known_io_call_is_an_effect():
    w, _ = load(
        "def announce(x):\n"
        "    print(x)\n"
    )
    (function, _tag), = w.each(Function)
    assert ("io", "print") in _effects_of(w, function)


def test_a_known_io_method_call_is_an_effect():
    w, _ = load(
        "def log(self, x):\n"
        "    self.stream.write(x)\n"
    )
    (function, _tag), = w.each(Function)
    assert ("io", "write") in _effects_of(w, function)


def test_an_unknown_call_asserts_no_effect():
    """⚠ A registry, not a guess — calling something we don't recognize is
    silent, the same abstention `patterns.py` documents for an unreadable part."""
    w, _ = load(
        "def classify(x):\n"
        "    return helper(x)\n"
    )
    (function, _tag), = w.each(Function)
    assert _effects_of(w, function) == []


def test_an_effect_propagates_across_a_call_in_the_same_module():
    w, _ = load(
        "def inner():\n"
        "    print('hi')\n"
        "\n"
        "def outer():\n"
        "    inner()\n"
    )
    by_name = {fn.name: e for e, fn in w.each(Function)}
    assert ("io", "print") in _effects_of(w, by_name["inner"])
    assert ("io", "print") in _effects_of(w, by_name["outer"])


def test_a_function_that_does_neither_has_no_effect():
    w, _ = load(
        "def total(items):\n"
        "    n = 0\n"
        "    for it in items:\n"
        "        n = n + it\n"
        "    return n\n"
    )
    (function, _tag), = w.each(Function)
    assert _effects_of(w, function) == []


def test_only_selects_a_subset_of_descriptions():
    """The same control knob `patterns.py` offers, for the same reason."""
    w, _ = load(
        "def announce(x):\n"
        "    print(x)\n",
        only={"contains"},
    )
    (function, _tag), = w.each(Function)
    assert _effects_of(w, function) == []
