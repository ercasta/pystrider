"""Slice 1's pins — intake → recognize → emit, on real parsed code.

These are the claims that must not quietly stop being true.

⚠⚠ 2026-08-29: rewritten off `Facts`/`relation` — deleted upstream, not
renamed — onto `loopingrules.world.World` directly and the typed components
`intake.py`/`patterns.py` now declare. A few pins that tested `Facts`' OWN
behaviour (word/value interning, the twin trap) tested an abstraction that no
longer exists; see the bottom of this file for what replaced them and why.
"""
from __future__ import annotations

import pytest

from loopingrules.loop import Loop
from pystrider import patterns
from pystrider.emit import Unrenderable, emit
from pystrider.intake import (Assign, Assigned, Body, ForStmt, Iterated,
                              Origin, UnknownPart, decode_literal,
                              encode_literal, intake)
from pystrider.exceptions import (Candidate, Guarded, MayRaise, Repaired,
                                  StatementRepaired, Verdict, Winner)
from pystrider.patterns import Applies, Choice, Iteration, LoopCount

SOURCE = '''\
def total(items):
    n = 0
    for it in items:
        if it.price > 10:
            n = n + it.price
    return n\
'''


def load(source: str = SOURCE, origin: str = "<test>", only=None):
    """Intake `source` into a world carrying the descriptions (or a subset)."""
    loop = Loop()
    patterns.install(loop, only=only)
    taken = intake(source, loop.world, origin)
    return loop, taken


def for_stmt(world):
    """The one `ForStmt` in the loaded source."""
    (loop,) = [e for e, _ in world.each(ForStmt)]
    return loop


# -- intake and the round trip --------------------------------------------------


def test_a_real_function_intakes_with_nothing_unread():
    _, taken = load()
    assert taken.unmodelled == () and taken.complete


def test_the_round_trip_is_byte_exact_AGAINST_THE_SOURCE():
    """⚠⚠ Against the SOURCE, never against a previous emit.

    STABILITY IS NOT FIDELITY: an emit-vs-emit round trip is a clean fixpoint on
    code that has already lost something, because the second pass has nothing left
    to drop. That is how annotations on `*args` parameters survived two reach
    measurements on an earlier generation while being silently deleted.
    """
    loop, taken = load()
    assert emit(loop.world, taken.module) == SOURCE


def test_and_the_round_trip_is_STABLE_which_is_a_separate_claim():
    loop, taken = load()
    once = emit(loop.world, taken.module)
    loop2, taken2 = load(once)
    assert emit(loop2.world, taken2.module) == once


def test_an_empty_else_renders_as_NO_else():
    """Or the round trip grows one every pass — divergence that compounds."""
    src = "if a:\n    pass"
    loop, taken = load(src)
    assert emit(loop.world, taken.module) == src and "else" not in emit(loop.world, taken.module)


# -- the bet, on the artifact ---------------------------------------------------


def test_the_description_recognizes_INTAKEN_CODE():
    loop, _ = load()
    loop.run()
    loop_stmt = for_stmt(loop.world)
    assert loop.world.has(loop_stmt, Iteration)


def test_what_was_recognized_CAME_FROM_PARSED_TEXT():
    """⭐ The vacuity control for the test above.

    Without `FromCode` a recognition is a claim about the world we meant to build.
    The point of the round trip is that the nodes came out of `ast.parse`.
    """
    from pystrider.intake import FromCode
    loop, _ = load()
    loop.run()
    loop_stmt = for_stmt(loop.world)
    assert loop.world.has(loop_stmt, FromCode)
    assert loop.world.get(loop_stmt, Origin).value == "<test>"


def test_the_neutral_parts_are_established_not_just_the_kind():
    """A description that named the loop but not its parts would be a label."""
    loop, _ = load()
    loop.run()
    loop_stmt = for_stmt(loop.world)
    it = loop.world.get(loop_stmt, Iteration)
    assert it.does == loop.world.get(loop_stmt, Body).entity
    assert it.sequence == loop.world.get(loop_stmt, Iterated).entity


def test_the_PERTURBATION_darkens_recognition():
    """⭐ The only check that tells ONE description from TWO that agree.

    ⚠ It now perturbs by INSTALLING A SUBSET rather than by editing corpus text,
    because a description is a Python function and there is no text to bend. That
    is a weaker probe and the weakening should be visible: bending
    `+iterated($n, $s)` to `+traverses($n, $s)` proved the recognizer and the
    structure shared one author's vocabulary. Removing the system only proves the
    recognition came from that system. **The stronger form returns when
    descriptions are data again** — see `pystrider/__init__.py`.
    """
    loop, _ = load(only={"conditional", "application"})
    loop.run()
    loop_stmt = for_stmt(loop.world)
    assert not loop.world.has(loop_stmt, Iteration)


def test_CONTROL_the_same_source_with_the_description_installed_IS_recognized():
    loop, _ = load()
    loop.run()
    loop_stmt = for_stmt(loop.world)
    assert loop.world.has(loop_stmt, Iteration)


# -- abstention: a description will not describe what it could not read ---------

#: `iterated` is a comprehension, which is unmodelled — so it becomes a PLACEHOLDER
#: and the loop's sequence is a part we did not read.
OVER_A_GAP = "def f(xs):\n    for x in [c for c in xs]:\n        pass\n"


def test_a_description_ABSTAINS_over_a_part_it_could_not_read():
    """⚠⚠ Measured as a live defect before the rule existed, not anticipated.

    `for x in [c for c in xs]` was recognized as an iteration and
    `sequence(loop, <unreadable>)` was asserted — a CONFIDENTLY WRONG description,
    not a missed one.
    """
    from pystrider.intake import Unreadable
    loop, taken = load(OVER_A_GAP)
    loop.run()
    loop_stmt = for_stmt(loop.world)
    assert "ListComp" in taken.unmodelled
    sequence = loop.world.get(loop_stmt, Iterated).entity
    assert loop.world.has(sequence, Unreadable)
    assert not loop.world.has(loop_stmt, Iteration)
    assert loop.world.get(loop_stmt, Body) is not None    # body IS readable...
    # ...but there is no Iteration at all, so there is nothing to hold a wrong
    # `sequence` pointer either — the abstention is total, not partial.


def test_CONTROL_the_SAME_loop_with_a_readable_sequence_IS_recognized():
    """Or the pin above would pass for any reason at all — including the system
    never firing on this shape of loop."""
    loop, _ = load("def f(xs):\n    for x in xs:\n        pass\n")
    loop.run()
    loop_stmt = for_stmt(loop.world)
    assert loop.world.has(loop_stmt, Iteration)


def test_readable_is_NOT_complete_so_a_gap_costs_only_what_BINDS_it():
    """⭐ A block holding one unreadable statement is still a readable BLOCK, and
    `does($n, $b)` names the block — so the loop is still described. If this goes
    red because `Readable` started meaning `complete`, the gap has begun costing
    every description above it again."""
    from pystrider.intake import Partial
    loop, _ = load("def f(xs):\n    for x in xs:\n        y = [c for c in xs]\n")
    loop.run()
    loop_stmt = for_stmt(loop.world)
    body = loop.world.get(loop_stmt, Body).entity
    assert loop.world.has(body, Partial), "the block really does contain a gap"
    assert loop.world.has(loop_stmt, Iteration)


def test_a_gap_is_recorded_ONCE_per_label():
    """⚠ It was recorded twice — once where the handler is missing, once when
    `part` saw the placeholder was partial. Harmless to read, wrong to count."""
    loop, _ = load(OVER_A_GAP)
    loop_stmt = for_stmt(loop.world)
    assert [u.label for u in loop.world.get_all(loop_stmt, UnknownPart)] == ["iterated"]


# -- ⚠⚠ the two capabilities the engine does not have ---------------------------

NEEDS_DATA_RULES = (
    "a description is a Python function here, and a function has no antecedent to "
    "read backwards. Restoring this means making descriptions DATA again — a "
    "matcher over the world, with each description compiled to a rule the way "
    "`cnl.py` already compiles `head when body`. STRICT so it XPASSes loudly the "
    "day that lands."
)
NEEDS_TRAIL = (
    "nothing records WHY a proposition holds. `loopingrules.world` stores "
    "conclusions, not routes to them. `cnl.explain` answers the same question by "
    "RE-DERIVING, which is a different claim — see its docstring."
)


@pytest.mark.xfail(strict=True, reason=NEEDS_TRAIL)
def test_recognition_arrives_EXPLAINED():
    loop, _ = load()
    loop.run()
    loop_stmt = for_stmt(loop.world)
    trail = " ".join(loop.world.why("iteration", loop_stmt))
    assert all(part in trail for part in ("for_stmt", "target", "iterated", "body"))


@pytest.mark.xfail(strict=True, reason=NEEDS_DATA_RULES)
def test_the_SAME_description_read_backwards_asks_for_the_STRUCTURE():
    """⚠⚠ THE WRITE HALF OF THE BET.

    Kept intact rather than rewritten, so whoever makes descriptions data again has
    the expectation sitting right here. The set below is what `<iteration>`'s
    antecedent asked for on engine 3 — Python's vocabulary and none of its own,
    because a description that asked for its own words would be a rule recognizing
    what it had written.
    """
    loop, _ = load()
    asked = loop.world.work_order("iteration", loop.world.spawn())
    assert asked == {"for_stmt", "target", "iterated", "body", "readable"}
    assert not (asked & {"iteration", "item", "sequence", "does"})


# -- the membrane ---------------------------------------------------------------


def test_an_unmodelled_construct_is_NAMED_and_costs_its_container():
    """⚠ The example is drawn from what is outside TODAY and must be re-pointed
    every widening. That is the invariant holding, not a defect."""
    loop, taken = load("def wait(n):\n    while n:\n        n = n - 1\n")
    assert "While" in taken.unmodelled and not taken.complete
    with pytest.raises(Unrenderable):
        emit(loop.world, taken.module)


def test_a_chained_comparison_is_REFUSED_never_approximated_by_its_first_pair():
    loop, taken = load("def f(a, b, c):\n    return a < b < c\n")
    assert "Compare.chained" in taken.unmodelled
    with pytest.raises(Unrenderable):
        emit(loop.world, taken.module)


def test_unconsumed_turns_a_field_nobody_read_into_an_HONEST_GAP():
    """⚠⚠ The guard that found silent field dropping. `-> bool` is not consumed by
    `_FunctionDef`, so it must show up as a gap. If it ever emits `def f(x)` while
    reporting COMPLETE, the guard has been switched off by someone declaring a
    field they did not read."""
    loop, taken = load("def f(x) -> bool:\n    pass\n")
    assert "FunctionDef.returns" in taken.unmodelled
    with pytest.raises(Unrenderable):
        emit(loop.world, taken.module)


def test_CONTROL_the_guard_is_silent_on_what_the_handler_DOES_read():
    """Or `unconsumed` would refuse everything and the pin above would be vacuous."""
    _, taken = load("def f(x):\n    pass\n")
    assert taken.complete


# -- the substrate, which is UPSTREAM now ---------------------------------------
#
# ⚠⚠ 2026-08-29: `Facts`/`arbitration.py` are gone from `loopingrules` too —
# deleted outright, not ported (nothing in `harneskills` itself ever imported
# them). The pins below that tested `Facts`' OWN behaviour (word/value
# interning, the twin trap) tested an abstraction this package no longer has;
# what replaces each is noted at its own definition. What is NOT gone is the
# underlying discipline each pin was protecting — "refuse to guess between
# several," "a literal survives exactly," "two references to one vocabulary
# item are the same object" — `loopingrules.world.World` gives every one of
# these directly now, which is what each rewritten pin below actually checks.


def test_one_REFUSES_to_pick_between_several_rather_than_taking_the_first():
    """⚠ Taking the first of several is the shape of two measured bugs: a
    three-line loop described by its first statement, and `f(a, b)` described by
    its first argument after a gap renumbered the rest. `World.get` refuses this
    itself now — there is no adapter left to carry the discipline."""
    loop, _ = load("def f(x):\n    a = b = x\n")
    ((assign, _),) = [(e, a) for e, a in loop.world.each(Assign)]
    assert len(loop.world.get_all(assign, Assigned)) == 2
    with pytest.raises(ValueError):
        loop.world.get(assign, Assigned)


@pytest.mark.parametrize("payload", ["a'b", 'q"q', "", 3, -2.5, True, None, b"\x00"])
def test_a_literal_survives_the_codec_exactly(payload):
    """⭐ `encode_literal`/`decode_literal` replace `Facts.value`/`.payload` — a
    plain `repr` codec now, not an interned entity, because a component field
    compares by value and there is nothing left an identity would buy here."""
    assert decode_literal(encode_literal(payload)) == payload
    assert type(decode_literal(encode_literal(payload))) is type(payload)


def test_intake_and_the_descriptions_share_NO_vocabulary():
    """⚠ If intake's word and a description's word coincided, the translation
    would do nothing for that part while looking like it worked. There is no
    shared string table any more for two authors to collide in BY ACCIDENT — a
    collision now has to be a Python `NameError`-worthy identical class name —
    so what is left to check is that `patterns.py`'s (and now `exceptions.
    py`'s) conclusions really are classes `intake.py` never defines or
    attaches — see `PRINCIPLES.md`'s "guard vocabulary collision with a
    check" guideline."""
    import pystrider.intake as intake_module
    for neutral in (Iteration, Choice, Applies, LoopCount,
                    MayRaise, Guarded, Repaired,
                    Candidate, Winner, Verdict, StatementRepaired):
        assert getattr(intake_module, neutral.__name__, None) is not neutral, (
            f"intake.py also defines {neutral.__name__!r} — the two modules "
            f"collided on a name"
        )
