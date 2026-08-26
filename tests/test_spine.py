"""Slice 1's pins — intake → recognize → emit, on real parsed code.

These are the claims that must not quietly stop being true.
"""
from __future__ import annotations

import pytest

from pystrider import patterns
from pystrider.emit import Unrenderable, emit
from pystrider.facts import Facts, relation
from pystrider.intake import intake

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
    f = Facts(lambda loop, ff: patterns.install(loop, ff, only=only))
    return f, intake(source, f, origin)


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
    f, taken = load()
    assert emit(f, taken.module) == SOURCE


def test_and_the_round_trip_is_STABLE_which_is_a_separate_claim():
    f, taken = load()
    once = emit(f, taken.module)
    f2, taken2 = load(once)
    assert emit(f2, taken2.module) == once


def test_an_empty_else_renders_as_NO_else():
    """Or the round trip grows one every pass — divergence that compounds."""
    src = "if a:\n    pass"
    f, taken = load(src)
    assert emit(f, taken.module) == src and "else" not in emit(f, taken.module)


# -- the bet, on the artifact ---------------------------------------------------


def test_the_description_recognizes_INTAKEN_CODE():
    f, _ = load()
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert f.has("iteration", loop)


def test_what_was_recognized_CAME_FROM_PARSED_TEXT():
    """⭐ The vacuity control for the test above.

    Without `from_code` a recognition is a claim about the world we meant to build.
    The point of the round trip is that the nodes came out of `ast.parse`.
    """
    f, _ = load()
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert f.has("from_code", loop)
    # ⚠ `origin` is a VALUE (repr-encoded), not a vocabulary word — read it with
    # `literal`, not `text`. The two readers exist so this is a loud mistake rather
    # than a `"'<test>'"` that looks almost right.
    assert f.literal("origin", loop) == "<test>"


def test_the_neutral_parts_are_established_not_just_the_kind():
    """A description that named the loop but not its parts would be a label."""
    f, _ = load()
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert f.holds("does", loop, f.one("body", loop))
    assert f.holds("sequence", loop, f.one("iterated", loop))


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
    f, _ = load(only={"conditional", "application"})
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert not f.has("iteration", loop)


def test_CONTROL_the_same_source_with_the_description_installed_IS_recognized():
    f, _ = load()
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert f.has("iteration", loop)


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
    f, taken = load(OVER_A_GAP)
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert "ListComp" in taken.unmodelled
    assert f.has("unreadable", f.one("iterated", loop))
    assert not f.has("iteration", loop)
    assert not f.holds("sequence", loop, f.one("iterated", loop))


def test_CONTROL_the_SAME_loop_with_a_readable_sequence_IS_recognized():
    """Or the pin above would pass for any reason at all — including the system
    never firing on this shape of loop."""
    f, _ = load("def f(xs):\n    for x in xs:\n        pass\n")
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert f.has("iteration", loop)


def test_readable_is_NOT_complete_so_a_gap_costs_only_what_BINDS_it():
    """⭐ A block holding one unreadable statement is still a readable BLOCK, and
    `does($n, $b)` names the block — so the loop is still described. If this goes
    red because `readable` started meaning `complete`, the gap has begun costing
    every description above it again."""
    f, _ = load("def f(xs):\n    for x in xs:\n        y = [c for c in xs]\n")
    f.run()
    (loop,) = f.subjects("for_stmt")
    body = f.one("body", loop)
    assert f.has("partial", body), "the block really does contain a gap"
    assert f.has("iteration", loop)


def test_a_gap_is_recorded_ONCE_per_label():
    """⚠ It was recorded twice — once where the handler is missing, once when
    `part` saw the placeholder was partial. Harmless to read, wrong to count."""
    f, _ = load(OVER_A_GAP)
    (loop,) = f.subjects("for_stmt")
    assert [f.show(m) for (m,) in f.of("unknown_part", loop)] == ["iterated"]


# -- ⚠⚠ the two capabilities engine 5 does not have ----------------------------

NEEDS_DATA_RULES = (
    "a description is a Python function here, and a function has no antecedent to "
    "read backwards. Restoring this means making descriptions DATA again — a "
    "matcher over `Facts`, with each description compiled to a system the way "
    "`cnl.py` already compiles `head when body`. STRICT so it XPASSes loudly the "
    "day that lands."
)
NEEDS_TRAIL = (
    "nothing records WHY a proposition holds. `ugm`'s `Machine.why` walked a "
    "support trail and was deleted upstream; the harneskills world stores "
    "conclusions, not routes to them. `cnl.explain` answers the same question by "
    "RE-DERIVING, which is a different claim — see its docstring."
)


@pytest.mark.xfail(strict=True, reason=NEEDS_TRAIL)
def test_recognition_arrives_EXPLAINED():
    f, _ = load()
    f.run()
    (loop,) = f.subjects("for_stmt")
    trail = " ".join(f.why("iteration", loop))
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
    f, _ = load()
    asked = f.work_order("iteration", f.node("loop_to_build"))
    assert asked == {"for_stmt", "target", "iterated", "body", "readable"}
    assert not (asked & {"iteration", "item", "sequence", "does"})


# -- the membrane ---------------------------------------------------------------


def test_an_unmodelled_construct_is_NAMED_and_costs_its_container():
    """⚠ The example is drawn from what is outside TODAY and must be re-pointed
    every widening. That is the invariant holding, not a defect."""
    f, taken = load("def wait(n):\n    while n:\n        n = n - 1\n")
    assert "While" in taken.unmodelled and not taken.complete
    with pytest.raises(Unrenderable):
        emit(f, taken.module)


def test_a_chained_comparison_is_REFUSED_never_approximated_by_its_first_pair():
    f, taken = load("def f(a, b, c):\n    return a < b < c\n")
    assert "Compare.chained" in taken.unmodelled
    with pytest.raises(Unrenderable):
        emit(f, taken.module)


def test_unconsumed_turns_a_field_nobody_read_into_an_HONEST_GAP():
    """⚠⚠ The guard that found silent field dropping. `-> bool` is not consumed by
    `_FunctionDef`, so it must show up as a gap. If it ever emits `def f(x)` while
    reporting COMPLETE, the guard has been switched off by someone declaring a
    field they did not read."""
    f, taken = load("def f(x) -> bool:\n    pass\n")
    assert "FunctionDef.returns" in taken.unmodelled
    with pytest.raises(Unrenderable):
        emit(f, taken.module)


def test_CONTROL_the_guard_is_silent_on_what_the_handler_DOES_read():
    """Or `unconsumed` would refuse everything and the pin above would be vacuous."""
    _, taken = load("def f(x):\n    pass\n")
    assert taken.complete


# -- the substrate adapter ------------------------------------------------------


def test_one_REFUSES_to_pick_between_several_rather_than_taking_the_first():
    """⚠ Taking `targets(n, label)[0]` is the shape of two measured bugs: a
    three-line loop described by its first statement, and `f(a, b)` described by
    its first argument after a gap renumbered the rest."""
    f, _ = load("def f(x):\n    a = b = x\n")
    (assign,) = f.subjects("assign")
    assert len(f.of("assigned", assign)) == 2
    with pytest.raises(ValueError):
        f.one("assigned", assign)


@pytest.mark.parametrize("payload", ["a'b", 'q"q', "", 3, -2.5, True, None, b"\x00"])
def test_a_literal_survives_the_world_exactly(payload):
    """The value lives IN the world as an entity's printed name, via `repr`, so
    nothing is held in a Python map the systems cannot see."""
    f = Facts()
    assert f.payload(f.value(payload)) == payload
    assert type(f.payload(f.value(payload))) is type(payload)


def test_the_TWIN_TRAP_is_structurally_impossible_now():
    """⚠⚠ It cost four recorded wrong readings, and there is nothing left to get wrong.

    `Graph.atom(name)` minted a FRESH node every call, so a relation built beside
    the corpus's table was a TWIN, nothing matched, and the run reported a contented
    quiescence having done nothing. A relation is a Python class interned by name
    here — two lookups are the same object because Python says so.
    """
    assert relation("for_stmt") is relation("for_stmt")
    f = Facts()
    assert f.word("gt") == f.word("gt"), "a WORD interns too"
    assert f.node("gt") != f.node("gt"), "...but an occurrence does not"


def test_a_WORD_and_a_LITERAL_are_different_kinds_of_entity():
    """⚠⚠ Conflating them made a corpus unable to talk about code: the operator was
    stored `repr`-encoded as `'gt'`, so a rule naming the bare `gt` could never
    match and one of two repair families was dead — and the suite could not tell."""
    f = Facts()
    assert f.word("gt") != f.value("gt")
    assert f.show(f.word("gt")) == "gt" and f.show(f.value("gt")) == "'gt'"


def test_intake_and_the_descriptions_share_NO_vocabulary():
    """⚠ If intake's word and a description's word coincided, the translation would
    do nothing for that part while looking like it worked."""
    for neutral in ("iteration", "item", "sequence", "does", "choice", "tests"):
        f, _ = load()
        assert not f.subjects(neutral), f"intake writes the neutral label {neutral!r}"
