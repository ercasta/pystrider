"""Effects — a semantic annotation built `patterns.py`'s way: forward-only,
off structure `intake.py` already produced.
"""
from __future__ import annotations

from pystrider import effects
from ugm.facts import Facts
from pystrider.intake import intake


def load(source: str, origin: str = "<test>", only=None):
    """Intake `source` into a world carrying the effect descriptions (or a subset)."""
    f = Facts(lambda loop, ff: effects.install(loop, ff, only=only))
    taken = intake(source, f, origin)
    f.run()
    return f, taken


def _effects_of(f, function):
    return [(f.show(kind), f.show(target)) for kind, target in f.of("effect", function)]


def test_a_direct_attribute_mutation_is_an_effect():
    f, _ = load(
        "def save(self):\n"
        "    self.dirty = 1\n"
    )
    function = f.subjects("function")[0]
    assert ("mutates", "dirty") in _effects_of(f, function)


def test_a_mutation_nested_inside_a_loop_and_a_branch_still_counts():
    """⚠ Not readable off `Function.body` directly — this is what `contains`
    is for."""
    f, _ = load(
        "def scrub(self, items):\n"
        "    for it in items:\n"
        "        if it:\n"
        "            self.dirty = 1\n"
    )
    function = f.subjects("function")[0]
    assert ("mutates", "dirty") in _effects_of(f, function)


def test_a_known_io_call_is_an_effect():
    f, _ = load(
        "def announce(x):\n"
        "    print(x)\n"
    )
    function = f.subjects("function")[0]
    assert ("io", "print") in _effects_of(f, function)


def test_a_known_io_method_call_is_an_effect():
    f, _ = load(
        "def log(self, x):\n"
        "    self.stream.write(x)\n"
    )
    function = f.subjects("function")[0]
    assert ("io", "write") in _effects_of(f, function)


def test_an_unknown_call_asserts_no_effect():
    """⚠ A registry, not a guess — calling something we don't recognize is
    silent, the same abstention `patterns.py` documents for an unreadable part."""
    f, _ = load(
        "def classify(x):\n"
        "    return helper(x)\n"
    )
    function = f.subjects("function")[0]
    assert _effects_of(f, function) == []


def test_an_effect_propagates_across_a_call_in_the_same_module():
    f, _ = load(
        "def inner():\n"
        "    print('hi')\n"
        "\n"
        "def outer():\n"
        "    inner()\n"
    )
    by_name = {f.text("name", fn): fn for fn in f.subjects("function")}
    assert ("io", "print") in _effects_of(f, by_name["inner"])
    assert ("io", "print") in _effects_of(f, by_name["outer"])


def test_a_function_that_does_neither_has_no_effect():
    f, _ = load(
        "def total(items):\n"
        "    n = 0\n"
        "    for it in items:\n"
        "        n = n + it\n"
        "    return n\n"
    )
    function = f.subjects("function")[0]
    assert _effects_of(f, function) == []


def test_only_selects_a_subset_of_descriptions():
    """The same control knob `patterns.py` offers, for the same reason."""
    f, _ = load(
        "def announce(x):\n"
        "    print(x)\n",
        only={"contains"},
    )
    function = f.subjects("function")[0]
    assert _effects_of(f, function) == []
