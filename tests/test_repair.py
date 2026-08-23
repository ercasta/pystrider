"""Slice 2's pins — one goal drives a code repair.

The narrative version with its printed evidence is `experiments/pystrider_repair.py`.

⚠ Read `conftest.py` first: this suite runs in its own pytest invocation.
"""
from __future__ import annotations

import pytest

from pystrider import corpus
from pystrider.emit import emit
from pystrider.evaluator import evaluate, register
from pystrider.facts import Facts
from pystrider.intake import intake

BUG = "def classify(age):\n    if age > 18:\n        return 'adult'\n    return 'minor'\n"
CORRECT = "def classify(age):\n    if age >= 18:\n        return 'adult'\n    return 'minor'\n"


def world(source: str = BUG, rules: str = "", scope: str = "r", given=18, wants="adult"):
    f = Facts(rules or corpus("patterns", "repair"), scope=scope)
    taken = intake(source, f, "<test>")
    function = f.subjects("function")[0]
    case = f.node("case")
    f.fact("case", case)
    f.fact("given", case, f.value(given))
    f.fact("wants", function, case, f.value(wants))
    register(f)
    f.run()
    return f, taken, function, case


#: ⚠⚠ EVERY TEST BELOW THAT CALLS THIS IS `xfail(strict=True)`, and the mark is on the
#: test rather than here so each one still says what it was checking. The three lines
#: this used to be are not repairable in place:
#:
#:     f.m.gate.write(f.m.focus, f.g.rel(f.m.GOAL, goal), PLUS, mention=True)
#:                      ^^^^^             ^^^^^^         ^^^^   ^^^^^^^
#:                      gone              gone           gone   gone
#:
#: A goal was the engine's own relation and drove backward reading; under the
#: scratchpad it is an ordinary corpus relation with no machinery behind it. STRICT so
#: that the day a backward reader is authored, these XPASS loudly instead of sitting
#: green-but-skipped — a pin that cannot tell you the world changed is not a pin.
NEEDS_GOALS = ("the engine no longer manages goals — see docs/transplant.md; a backward "
               "reader has to be authored in rules/ before this can pass again")


def pursue(f: Facts, function: int, case: int):
    """Assert the goal and let the rules chase it. NOT AVAILABLE on this engine."""
    raise NotImplementedError(NEEDS_GOALS)


def ran(source: str):
    namespace: dict = {}
    exec(compile(source, "<repaired>", "exec"), namespace)   # noqa: S102
    return namespace["classify"]


# -- diagnosis ------------------------------------------------------------------


def test_what_the_code_does_is_DERIVED_FROM_STRUCTURE_not_by_running_it():
    f, _, function, case = world()
    assert evaluate(f, function, case).value == "minor"


@pytest.mark.xfail(strict=True, reason=NEEDS_GOALS)
def test_the_goal_comes_to_hold_and_the_repair_reaches_the_REAL_graph():
    f, _, function, case = world()
    assert f.m.holds(pursue(f, function, case)) == PLUS


@pytest.mark.xfail(strict=True, reason=NEEDS_GOALS)
def test_CHANGE_then_OBSERVE_the_evaluation_is_re_derived_after_the_change():
    """A repair is not done until its effect is observed. Two evaluations, not one."""
    f, _, function, case = world()
    pursue(f, function, case)
    assert len(f.of("evaluated", function)) == 2


# -- the artefact ---------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=NEEDS_GOALS)
def test_the_emitted_source_RUNS_and_answers_the_case():
    """⚠⚠ THE INDEPENDENT GATE. Engine 2 shipped a plan that "succeeded" while
    emitting BYTE-IDENTICAL source: a plan that changes nothing is
    indistinguishable from a real fix unless something inspects the artefact."""
    f, taken, function, case = world()
    pursue(f, function, case)
    repaired = emit(f, taken.module)
    assert repaired.strip() != BUG.strip()
    assert ran(repaired)(18) == "adult"
    assert ran(repaired)(5) == "minor"


@pytest.mark.xfail(strict=True, reason=NEEDS_GOALS)
def test_exactly_ONE_repair_family_fires():
    """⚠⚠ It was TWO, and the emitted code read `if age >= 17` — two independent
    fixes for one bug, correct by luck and wrong as a repair.

    `unmet` is a FACT and a fact is not an event: on an append-only chain it stays
    written, so after the first repair fixed the code the second was still
    proposable off the same stale occasion. Each repair now DENIES the occasion it
    acted on. If this goes red, over-repair is back.
    """
    f, _, function, case = world()
    pursue(f, function, case)
    assert len(f.subjects("relaxed")) + len(f.subjects("lowered")) == 1


# -- the rivals -----------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=NEEDS_GOALS)
@pytest.mark.parametrize("dropped", ["relax", "lower"])
def test_EITHER_repair_family_alone_genuinely_fixes_it(dropped):
    """⚠ Engine 2 pinned its winner BY NAME and the pin went silently vacuous when
    upstream's tie-break flipped — it passed while exercising the family the
    planner had just chosen. Both families are checked here, so which one wins is
    free to change; it already did once, mid-slice.
    """
    text = corpus("patterns", "repair")
    start = text.index(f"rule <{dropped}>")
    i, depth = text.index("(", start), 0
    while True:
        depth += 1 if text[i] == "(" else -1 if text[i] == ")" else 0
        if depth == 0:
            break
        i += 1
    f, taken, function, case = world(rules=text[:start] + text[i + 1:], scope=dropped)
    pursue(f, function, case)
    classify = ran(emit(f, taken.module))
    assert classify(18) == "adult" and classify(5) == "minor"


# -- ⭐ what makes a repair unproposable ----------------------------------------


def test_WITHOUT_the_unmet_member_a_repair_damages_CORRECT_code():
    """⭐⭐ The measurement this slice exists for.

    Survey §2 lists *a rule's condition is its parameter type* as the one item that
    is a REDESIGN rather than a port. The answer measured here is `+unmet($p, ...)`:
    a repair is proposable only once backward reading has found the goal unmet, and
    the condition is an ordinary antecedent member rather than a type — so it is
    arguable, and another author can write a different one.
    """
    ungated = corpus("patterns", "repair").replace(
        "+unmet($p, evaluated($f, $c, $v))", "+wants($f, $c, $v)"
    ).replace("-unmet($p, evaluated($f, $c, $v)),\n    ", "")
    f, taken, _function, _case = world(CORRECT, rules=ungated, scope="ungated")
    f.run()
    assert emit(f, taken.module).strip() != CORRECT.strip()


def test_WITH_it_correct_code_is_left_alone():
    f, taken, _function, _case = world(CORRECT, scope="gated")
    f.run()
    assert emit(f, taken.module).strip() == CORRECT.strip()
    assert not f.subjects("relaxed") and not f.subjects("lowered")


# -- the membrane ---------------------------------------------------------------


def test_an_unmodelled_operator_is_refused_BY_NAME_and_nothing_is_concluded():
    """⚠⚠⚠ Engine 2's evaluator said in PROSE that it modelled `gt`/`ge` only and
    fell through to `gt` for everything else, deriving `age < 18` as `age > 18` and
    answering `'minor'` about code that plainly returns `'adult'`. **A membrane
    described in prose is not a membrane.**"""
    src = "def classify(age):\n    if age is 18:\n        return 'adult'\n    return 'minor'\n"
    f, _, function, case = world(src, scope="membrane")
    verdict = evaluate(f, function, case)
    assert verdict.refused == "unmodelled_operator:is"
    assert verdict.value is None
    assert not f.of("evaluated", function)


def test_CONTROL_an_operator_that_IS_modelled_is_not_refused():
    """Or the pin above would pass for a function it simply could not read."""
    src = "def classify(age):\n    if age < 18:\n        return 'minor'\n    return 'adult'\n"
    f, _, function, case = world(src, scope="modelled", given=5, wants="minor")
    assert evaluate(f, function, case).refused is None


# -- the substrate the repair rests on ------------------------------------------


@pytest.mark.xfail(strict=True, reason=NEEDS_GOALS)
def test_repair_is_DENY_then_ASSERT_and_the_reader_sees_the_CURRENT_claim():
    """⚠⚠ The chain is append-only: nothing is mutated and nothing is removed, so
    *change this* is `-old, +new`. A reader over its own deposit log would see both
    and hand `emit` the code that was just repaired."""
    f, _, function, case = world()
    guard = f.of("guard", function)[0][0]
    assert f.text("operator", guard) == "gt"
    pursue(f, function, case)
    operators = [f.word_of(o) for (o,) in f.of("operator", guard)]
    assert len(operators) == 1, f"a denied claim is still visible: {operators}"


def test_a_WORD_and_a_LITERAL_are_different_kinds_of_node():
    """⚠⚠ Conflating them made a corpus unable to talk about code: the operator was
    stored `repr`-encoded as `'gt'`, so `+operator($g, gt)` in an authored rule
    could never match and one of the two repair families was **dead**. The suite
    could not tell, because the other family keys on an integer, where `repr(18)`
    and the token `18` agree by luck."""
    f, _, function, _case = world()
    guard = f.of("guard", function)[0][0]
    assert f.one("operator", guard) == f.word("gt")
    assert f.one("operator", guard) != f.value("gt")
