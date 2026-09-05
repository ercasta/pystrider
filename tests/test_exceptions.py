"""Pins for `pystrider.exceptions` — see that module's own note for scope.

`load()` mirrors `test_effects_repair.py`'s own shape: a fresh `Loop`,
`intake()` straight into its world, `install()`, `run()` to settle.
"""
from __future__ import annotations

import ast

import pytest

from loopingrules.loop import Loop
from pystrider import exceptions
from pystrider.emit import emit
from pystrider.exceptions import Guarded, MayRaise, Repaired, WantsHardening
from pystrider.intake import TryStmt, intake


def load(source: str, harden: bool = True):
    """`harden=True` (the default, so most tests below are unaffected)
    attaches `WantsHardening` for `<test>` before running — the gate
    `wrap_in_try` reads, since `pystrider.domain`'s `harden <path.py>`
    wiring. `harden=False` is what pins the gate itself: without a request,
    recognition still happens, but nothing gets rewritten."""
    loop = Loop()
    taken = intake(source, loop.world, "<test>")
    if harden:
        loop.world.spawn(WantsHardening(taken.origin))
    exceptions.install(loop)
    loop.run()
    return loop.world, taken, loop


SOURCE_DIV = "def divide(x, y):\n    return x / y\n"

SOURCE_CONST_DIVISOR = "def half(x):\n    return x / 2\n"

SOURCE_ALREADY_GUARDED = (
    "def divide(x, y):\n"
    "    try:\n"
    "        return x / y\n"
    "    except ZeroDivisionError:\n"
    "        raise\n"
)

SOURCE_WRONG_GUARD = (
    "def divide(x, y):\n"
    "    try:\n"
    "        return x / y\n"
    "    except ValueError:\n"
    "        raise\n"
)

SOURCE_ORDER = (
    "def f(x, y):\n"
    "    a = 1\n"
    "    b = x / y\n"
    "    c = 2\n"
    "    return a + b + c\n"
)


def test_a_non_constant_division_is_wrapped_and_actually_runs_correctly():
    w, taken, _ = load(SOURCE_DIV)
    source = emit(w, taken.module)
    assert "try:" in source
    assert "except ZeroDivisionError:" in source
    assert "raise" in source
    ast.parse(source)  # syntactically valid...
    namespace: dict = {}
    exec(compile(source, "<repaired>", "exec"), namespace)  # noqa: S102
    assert namespace["divide"](10, 2) == 5.0
    with pytest.raises(ZeroDivisionError):
        namespace["divide"](10, 0)


def test_a_constant_divisor_is_never_flagged_or_touched():
    w, taken, _ = load(SOURCE_CONST_DIVISOR)
    assert w.each(MayRaise) == []
    assert "try" not in emit(w, taken.module)


def test_a_division_already_guarded_by_the_exact_type_is_left_alone():
    w, taken, _ = load(SOURCE_ALREADY_GUARDED)
    (entity, _tag), = w.each(MayRaise)
    assert w.has(entity, Guarded)
    assert w.get_all(entity, Repaired) == []
    assert len(w.each(TryStmt)) == 1  # no second `try` spliced in


def test_a_guard_of_the_wrong_type_does_not_stop_the_wrap():
    """⚠ Not asserting `Guarded` is absent here: once `wrap_in_try` nests its
    OWN `except ZeroDivisionError:` inside the original `except ValueError:`,
    `guarded` correctly (if a little circularly) marks the entity guarded by
    its own repair on the very next tick — that is right, not a bug; what
    this test pins is that the wrap itself still happened despite the
    pre-existing, wrong-typed guard."""
    w, taken, _ = load(SOURCE_WRONG_GUARD)
    (entity, _tag), = w.each(MayRaise)
    assert w.has(entity, Repaired)
    assert len(w.each(TryStmt)) == 2  # the original `ValueError` guard, plus the new one
    assert emit(w, taken.module).count("try:") == 2


def test_the_wrap_is_spliced_in_place_not_appended_at_the_end():
    w, taken, _ = load(SOURCE_ORDER)
    lines = [l.strip() for l in emit(w, taken.module).splitlines() if l.strip()]
    assert (lines.index("a = 1") < lines.index("try:")
            < lines.index("c = 2"))


def test_settling_again_does_not_move_revision_or_double_wrap():
    w, _, loop = load(SOURCE_DIV)
    before = w.revision
    tries_before = len(w.each(TryStmt))
    loop.run()
    assert w.revision == before
    assert len(w.each(TryStmt)) == tries_before


def test_guarded_correctly_reads_a_try_minted_after_may_raise_already_ran():
    """`guarded` watches `MayRaise` alone, never `TryStmt` (see
    `exceptions.py`'s own note on why that is still correct) — pin the over-
    approximation itself, per `PRINCIPLES.md`'s "`watches=` correctness
    should be tested" guideline: `may_raise` runs FIRST and alone, with no
    `TryStmt` anywhere yet; a covering `try` is minted out-of-band after
    that (not through `wrap_in_try`); only THEN is `guarded` installed and
    run — it must still find it, a full rescan rather than a diff since
    `may_raise`'s own tick."""
    loop = Loop()
    intake(SOURCE_DIV, loop.world, "<test>")
    exceptions.install(loop, only=("may_raise",))
    loop.run()
    w = loop.world
    (entity, _tag), = w.each(MayRaise)
    assert w.get_all(entity, Guarded) == []

    block, stmt = exceptions._enclosing_stmt(w, entity)
    exceptions._splice_try(w, block, stmt)

    exceptions.install(loop, only=("guarded",))
    loop.run()
    assert w.has(entity, Guarded)


def test_without_a_hardening_request_recognition_still_happens_but_nothing_is_rewritten():
    """The gate `WantsHardening` exists for: recognition (`may_raise`,
    `guarded`) is unconditional and global, same as `effects.py`'s own
    `contains`/`calls_effectful` -- but `wrap_in_try` must never rewrite a
    file nobody asked to harden, simply because it happened to be `read`."""
    w, taken, _ = load(SOURCE_DIV, harden=False)
    (entity, _tag), = w.each(MayRaise)
    assert w.get_all(entity, Repaired) == []
    assert w.each(TryStmt) == []
    assert "try" not in emit(w, taken.module)
