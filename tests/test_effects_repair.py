"""Achieving a wanted effect, wired through the same propose/arbitrate
machinery `repair.py` now uses. See `pystrider/effects_repair.py`'s module
note for what this deliberately does not cover.
"""
from __future__ import annotations

import ast

from pystrider import effects, effects_repair
from pystrider.emit import emit
from pystrider.facts import Facts
from pystrider.intake import intake

SOURCE = "def touch(x):\n    y = x + 1\n"
SOURCE_ALREADY_LOGS = "def touch(x):\n    print(x)\n    y = x + 1\n"


def load(source: str = SOURCE, families=None):
    """Two phases, on purpose — see the module note on why the second one
    must wait for the first to settle."""
    f = Facts(effects.install)
    taken = intake(source, f, "<test>")
    f.run()
    function = f.subjects("function")[0]
    f.fact("wants_effect", function)
    f.install(lambda loop, ff: effects_repair.install(loop, ff, families=families))
    f.run()
    return f, taken, function


def test_a_missing_io_effect_is_achieved_and_BOTH_families_are_on_the_record():
    f, _, function = load()
    proposed = {f.show(o) for (o,) in f.of("candidate", function)}
    assert proposed == {"via_print", "via_open"}
    assert f.text("winner", function) == "via_print"
    assert f.holds("effect", function, f.word("io"), f.word("print"))


def test_the_effect_is_DERIVED_by_effects_py_not_asserted_by_this_module():
    """Install this module WITHOUT `effects.install`: the call still gets
    synthesized, but nothing ever concludes `effect(...)` — this module
    never says the word."""
    f = Facts(lambda loop, ff: effects_repair.install(loop, ff))
    taken = intake(SOURCE, f, "<test>")
    function = f.subjects("function")[0]
    f.fact("wants_effect", function)
    f.run()
    assert f.text("winner", function) == "via_print"
    assert f.of("effect", function) == []
    assert "print()" in emit(f, taken.module)


def test_the_emitted_source_contains_the_call_and_still_runs():
    f, taken, _ = load()
    source = emit(f, taken.module)
    assert "print()" in source
    namespace: dict = {}
    exec(compile(source, "<repaired>", "exec"), namespace)  # noqa: S102
    namespace["touch"](5)  # must not raise


def test_a_function_that_already_calls_print_is_left_alone():
    """⚠⚠ The race `install`'s module note warns about, pinned: without the
    two-phase settle, `contains` has not yet caught up to the PRE-EXISTING
    call on the first tick, `diagnose` sees no effect, and a redundant
    second `print()` gets appended to a function that needed nothing."""
    f, _, function = load(SOURCE_ALREADY_LOGS)
    assert f.of("candidate", function) == []
    assert f.of("missing_effect", function) == []


def test_via_open_alone_wins_by_default_and_is_structurally_valid_but_unsafe_to_run():
    f, taken, function = load(families={"via_open"})
    assert f.text("winner", function) == "via_open"
    source = emit(f, taken.module)
    assert "open()" in source
    ast.parse(source)  # syntactically valid...
    # ...but NOT executed here: a zero-argument open() raises at runtime,
    # which is exactly why via_print outranks it by default.


def test_exactly_one_family_fires():
    f, _, function = load()
    assert len(f.of("effect_repaired", function)) == 1
