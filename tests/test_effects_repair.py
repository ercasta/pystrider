"""Achieving a wanted effect, wired through the same propose/arbitrate
machinery `repair.py` now uses. See `pystrider/effects_repair.py`'s module
note for what this deliberately does not cover.
"""
from __future__ import annotations

import ast

from loopingrules.loop import Loop
from pystrider import effects, effects_repair
from pystrider.effects import Effect
from pystrider.effects_repair import (Candidate, EffectRepaired, MissingEffect,
                                      Winner, WantsEffect)
from pystrider.emit import emit
from pystrider.intake import Function, intake

SOURCE = "def touch(x):\n    y = x + 1\n"
SOURCE_ALREADY_LOGS = "def touch(x):\n    print(x)\n    y = x + 1\n"


def load(source: str = SOURCE, families=None):
    """Two phases, on purpose — see the module note on why the second one
    must wait for the first to settle."""
    loop = Loop()
    effects.install(loop)
    taken = intake(source, loop.world, "<test>")
    loop.run()
    (function, _tag), = loop.world.each(Function)
    loop.world.attach(function, WantsEffect())
    effects_repair.install(loop, families=families)
    loop.run()
    return loop.world, taken, function


def test_a_missing_io_effect_is_achieved_and_BOTH_families_are_on_the_record():
    w, _, function = load()
    proposed = {c.name for c in w.get_all(function, Candidate)}
    assert proposed == {"via_print", "via_open"}
    assert w.get(function, Winner).name == "via_print"
    assert Effect("io", "print") in w.get_all(function, Effect)


def test_the_effect_is_DERIVED_by_effects_py_not_asserted_by_this_module():
    """Install this module WITHOUT `effects.install`: the call still gets
    synthesized, but nothing ever concludes `Effect(...)` — this module
    never says the word."""
    loop = Loop()
    effects_repair.install(loop)
    taken = intake(SOURCE, loop.world, "<test>")
    (function, _tag), = loop.world.each(Function)
    loop.world.attach(function, WantsEffect())
    loop.run()
    assert loop.world.get(function, Winner).name == "via_print"
    assert loop.world.get_all(function, Effect) == []
    assert "print()" in emit(loop.world, taken.module)


def test_the_emitted_source_contains_the_call_and_still_runs():
    w, taken, _ = load()
    source = emit(w, taken.module)
    assert "print()" in source
    namespace: dict = {}
    exec(compile(source, "<repaired>", "exec"), namespace)  # noqa: S102
    namespace["touch"](5)  # must not raise


def test_a_function_that_already_calls_print_is_left_alone():
    """⚠⚠ The race `install`'s module note warns about, pinned: without the
    two-phase settle, `contains` has not yet caught up to the PRE-EXISTING
    call on the first tick, `diagnose` sees no effect, and a redundant
    second `print()` gets appended to a function that needed nothing."""
    w, _, function = load(SOURCE_ALREADY_LOGS)
    assert w.get_all(function, Candidate) == []
    assert w.get_all(function, MissingEffect) == []


def test_via_open_alone_wins_by_default_and_is_structurally_valid_but_unsafe_to_run():
    w, taken, function = load(families={"via_open"})
    assert w.get(function, Winner).name == "via_open"
    source = emit(w, taken.module)
    assert "open()" in source
    ast.parse(source)  # syntactically valid...
    # ...but NOT executed here: a zero-argument open() raises at runtime,
    # which is exactly why via_print outranks it by default.


def test_exactly_one_family_fires():
    w, _, function = load()
    assert len(w.get_all(function, EffectRepaired)) == 1
