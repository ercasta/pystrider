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
from pystrider.exceptions import (Candidate, Guarded, MayRaise, Repaired,
                                  Verdict, WantsHardening, Winner)
from pystrider.intake import Handler, TryStmt, intake


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


def test_a_bare_risky_expression_statement_is_found_and_wrapped():
    """Regression pin for `_enclosing_stmt`'s own normalization note: a
    risky expression that IS ITSELF the statement (no enclosing `return`/
    `=` around it) must be found on the very first membership check, not
    walked past."""
    w, taken, _ = load("def divide(x, y):\n    x / y\n    return 1\n")
    (entity, _tag), = w.each(MayRaise)
    assert w.has(entity, Repaired)
    source = emit(w, taken.module)
    assert "try:" in source
    assert "return 1" in source


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
    should be tested" guideline: `may_raise_zero_division` runs FIRST and
    alone, with no `TryStmt` anywhere yet; a covering `try` is minted
    out-of-band after that (not through the repair pipeline); only THEN is
    `guarded` installed and run — it must still find it, a full rescan
    rather than a diff since `may_raise_zero_division`'s own tick."""
    loop = Loop()
    intake(SOURCE_DIV, loop.world, "<test>")
    exceptions.install(loop, only=("may_raise_zero_division",))
    loop.run()
    w = loop.world
    (entity, _tag), = w.each(MayRaise)
    assert w.get_all(entity, Guarded) == []

    block, stmt = exceptions._enclosing_stmt(w, entity)
    exceptions._splice_try(w, block, stmt, ["ZeroDivisionError"])

    exceptions.install(loop, only=("guarded",))
    loop.run()
    assert w.has(entity, Guarded)


def test_without_a_hardening_request_recognition_still_happens_but_nothing_is_rewritten():
    """The gate `WantsHardening` exists for: recognition (`may_raise_*`,
    `guarded`) is unconditional and global, same as `effects.py`'s own
    `contains`/`calls_effectful` -- but the repair pipeline must never
    rewrite a file nobody asked to harden, simply because it happened to
    be `read`."""
    w, taken, _ = load(SOURCE_DIV, harden=False)
    (entity, _tag), = w.each(MayRaise)
    assert w.get_all(entity, Repaired) == []
    assert w.each(TryStmt) == []
    assert "try" not in emit(w, taken.module)


# --- the second risk: `int`/`float` with a non-constant argument -----------

SOURCE_INT_CALL = "def parse(raw):\n    return int(raw)\n"

SOURCE_INT_CONST = "def answer():\n    return int('42')\n"


def test_a_non_constant_int_call_is_wrapped_and_actually_runs_correctly():
    w, taken, _ = load(SOURCE_INT_CALL)
    source = emit(w, taken.module)
    assert "except ValueError:" in source
    namespace: dict = {}
    exec(compile(source, "<repaired>", "exec"), namespace)  # noqa: S102
    assert namespace["parse"]("42") == 42
    with pytest.raises(ValueError):
        namespace["parse"]("not a number")


def test_a_constant_argument_to_int_is_never_flagged():
    w, taken, _ = load(SOURCE_INT_CONST)
    assert w.each(MayRaise) == []
    assert "try" not in emit(w, taken.module)


def test_int_with_the_wrong_number_of_arguments_is_never_flagged():
    # `int(x, base)` -- a real, differently-shaped call this recognizer
    # has no opinion about, refused rather than guessed at.
    w, taken, _ = load("def parse(raw, base):\n    return int(raw, base)\n")
    assert w.each(MayRaise) == []


# --- two risks sharing one statement: scalability + arbitration ------------

SOURCE_TWO_RISKS = "def rate(raw, total):\n    return int(raw) / total\n"


def test_two_co_occurring_risks_settle_to_one_combined_try_not_two_nested_ones():
    w, taken, _ = load(SOURCE_TWO_RISKS)
    (try_entity, _tag), = w.each(TryStmt)   # exactly ONE `try`, not two nested
    handlers = w.get_all(try_entity, Handler)
    assert len(handlers) == 2               # ...carrying BOTH exception types
    source = emit(w, taken.module)
    assert source.count("try:") == 1
    assert "except ValueError:" in source
    assert "except ZeroDivisionError:" in source


def test_per_issue_is_proposed_but_arbitration_inhibits_it():
    """The concrete, checkable version of "inhibit the single-issue fix
    when there's more than one": `per_issue` really was on the table, and
    really lost -- not merely never built."""
    w, _taken, _ = load(SOURCE_TWO_RISKS)
    (stmt, winner), = w.each(Winner)
    names = {c.name for c in w.get_all(stmt, Candidate)}
    assert names == {"per_issue", "combined"}   # both really were on the table
    assert winner.name == "combined"            # ...and `combined` really won
    assert w.get(stmt, Verdict) == Verdict("forced")


def test_per_issue_still_fully_works_when_forced_to_win():
    """Proves the losing family is not dead code — same reasoning
    `test_via_open_alone_wins_by_default...` already pins for
    `effects_repair.py`'s own losing rival."""
    loop = Loop()
    taken = intake(SOURCE_TWO_RISKS, loop.world, "<test>")
    loop.world.spawn(WantsHardening(taken.origin))
    exceptions.install(loop, only=(
        "may_raise_zero_division", "may_raise_value_error", "guarded",
        "propose_per_issue", "arbitrate_repair", "apply_repair"))
    loop.run()
    w = loop.world
    assert len(w.each(TryStmt)) == 2   # two NESTED trys, not one combined one
    source = emit(w, taken.module)
    assert source.count("try:") == 2
    ast.parse(source)

