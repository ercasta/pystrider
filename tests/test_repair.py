"""Slice 2's pins — a diagnosis drives a code repair.

⭐⭐ **SEVEN OF THESE WERE `xfail(strict=True)` ON `ugm` AND PASS HERE**, and the
reason is worth stating so nobody reads it as more than it is. They were blocked on
`unmet`, which backward reading produced; the scratchpad deleted the goal apparatus
and nothing replaced it. `repair.diagnose` derives the same occasion FORWARD — *the
case wants `v`, the code was read and does not produce `v`*.

⚠ That is a narrower thing than backward reading, and `repair.py`'s note says so:
no goal expansion, no subgoal search, no choice of which tap to try. It reaches this
shape of problem and would not reach a goal needing more than one subgoal to be
found unmet. The slice works; the general capability is still absent.
"""
from __future__ import annotations

import pytest

from pystrider import patterns, repair
from pystrider.emit import emit
from pystrider.evaluator import evaluate, register
from pystrider.facts import Facts
from pystrider.intake import intake

BUG = "def classify(age):\n    if age > 18:\n        return 'adult'\n    return 'minor'\n"
CORRECT = "def classify(age):\n    if age >= 18:\n        return 'adult'\n    return 'minor'\n"


def world(source: str = BUG, given=18, wants="adult", **repair_options):
    """Intake, seed the case, and settle. `repair_options` reach `repair.install`."""
    f = Facts(patterns.install,
              lambda loop, ff: repair.install(loop, ff, **repair_options))
    taken = intake(source, f, "<test>")
    function = f.subjects("function")[0]
    case = f.node("case")
    f.fact("case", case)
    f.fact("given", case, f.value(given))
    f.fact("wants", function, case, f.value(wants))
    f.run()
    return f, taken, function, case


def ran(source: str):
    namespace: dict = {}
    exec(compile(source, "<repaired>", "exec"), namespace)   # noqa: S102
    return namespace["classify"]


# -- diagnosis ------------------------------------------------------------------


def test_what_the_code_does_is_DERIVED_FROM_STRUCTURE_not_by_running_it():
    f, _, function, case = world()
    # ⚠ Asked of the ORIGINAL structure would say 'minor'; by now the repair has
    # run, so what the derivation reports is the repaired code. Both readings are
    # in `evaluated` — see the CHANGE-then-OBSERVE pin below.
    assert f.holds("evaluated", function, case, f.value("minor"))


def test_the_diagnosis_finds_the_goal_UNMET_and_the_repair_reaches_the_REAL_world():
    f, _, function, case = world()
    assert f.holds("agrees", function, case), "the goal comes to hold after repair"
    assert f.holds("repaired", function, case)


def test_CHANGE_then_OBSERVE_the_evaluation_is_re_derived_after_the_change():
    """A repair is not done until its effect is observed. Two evaluations, not one."""
    f, _, function, case = world()
    assert len(f.of("evaluated", function)) == 2


# -- the artefact ---------------------------------------------------------------


def test_the_emitted_source_RUNS_and_answers_the_case():
    """⚠⚠ THE INDEPENDENT GATE. Engine 2 shipped a plan that "succeeded" while
    emitting BYTE-IDENTICAL source: a plan that changes nothing is
    indistinguishable from a real fix unless something inspects the artefact."""
    f, taken, _, _ = world()
    repaired = emit(f, taken.module)
    assert repaired.strip() != BUG.strip()
    assert ran(repaired)(18) == "adult"
    assert ran(repaired)(5) == "minor"


def test_exactly_ONE_repair_family_fires():
    """⚠⚠ It was TWO on `ugm`, and the emitted code read `if age >= 17` — two
    independent fixes for one bug, correct by luck and wrong as a repair.

    There, `unmet` was a fact on an append-only chain and stayed written after the
    first repair. Here a SYSTEM re-runs every tick, so denying the occasion is not
    enough on its own — `repaired($f, $c)` is the durable mark that makes it stick.
    If this goes red, over-repair is back through the new door.
    """
    f, _, _, _ = world()
    assert len(f.subjects("relaxed")) + len(f.subjects("lowered")) == 1


# -- the rivals -----------------------------------------------------------------


@pytest.mark.parametrize("only", ["relax", "lower"])
def test_EITHER_repair_family_alone_genuinely_fixes_it(only):
    """⚠ Engine 2 pinned its winner BY NAME and the pin went silently vacuous when
    the tie-break flipped — it passed while exercising the family the planner had
    just chosen. Both are checked here, so which one wins is free to change."""
    f, taken, _, _ = world(families={only})
    classify = ran(emit(f, taken.module))
    assert classify(18) == "adult" and classify(5) == "minor"


def test_the_two_families_reach_DIFFERENT_source_and_both_are_correct():
    """"found A" must not be read as "B is wrong"."""
    relaxed = emit(*_module(world(families={"relax"})))
    lowered = emit(*_module(world(families={"lower"})))
    assert relaxed != lowered
    assert "age >= 18" in relaxed and "age > 17" in lowered


def _module(built):
    f, taken, _, _ = built
    return f, taken.module


# -- ⭐ what makes a repair unproposable ----------------------------------------


def test_WITHOUT_the_diagnosis_a_repair_damages_CORRECT_code():
    """⭐⭐ The measurement this slice exists for.

    Survey §2 lists *a rule's condition is its parameter type* as the one item that
    is a REDESIGN rather than a port. The answer is that the condition is an
    ordinary query term — so it is arguable, and another author can write a
    different one. `gated=False` removes it and the repair fires on correct code.
    """
    f, taken, _, _ = world(CORRECT, gated=False)
    assert emit(f, taken.module).strip() != CORRECT.strip()


def test_WITH_it_correct_code_is_left_alone():
    f, taken, _, _ = world(CORRECT)
    assert emit(f, taken.module).strip() == CORRECT.strip()
    assert not f.subjects("relaxed") and not f.subjects("lowered")


# -- the membrane ---------------------------------------------------------------


def test_an_unmodelled_operator_is_refused_BY_NAME_and_nothing_is_concluded():
    """⚠⚠⚠ Engine 2's evaluator said in PROSE that it modelled `gt`/`ge` only and
    fell through to `gt` for everything else, deriving `age < 18` as `age > 18` and
    answering `'minor'` about code that plainly returns `'adult'`. **A membrane
    described in prose is not a membrane.**"""
    src = "def classify(age):\n    if age is 18:\n        return 'adult'\n    return 'minor'\n"
    f, _, function, case = world(src)
    verdict = evaluate(f, function, case)
    assert verdict.refused == "unmodelled_operator:is" and verdict.value is None
    assert not f.of("evaluated", function)
    assert f.of("could_not_evaluate", function), "the refusal is DEPOSITED, not swallowed"


def test_CONTROL_an_operator_that_IS_modelled_is_not_refused():
    """Or the pin above would pass for a function it simply could not read."""
    src = "def classify(age):\n    if age < 18:\n        return 'minor'\n    return 'adult'\n"
    f, _, function, case = world(src, given=5, wants="minor")
    assert evaluate(f, function, case).refused is None


# -- the substrate the repair rests on ------------------------------------------


def test_repair_is_DENY_then_ASSERT_and_the_reader_sees_the_CURRENT_claim():
    """⚠⚠ On `ugm` the chain was append-only, so *change this* was `-old, +new` and
    a reader over its own deposit log would see BOTH and emit the code that was just
    repaired. Here removal is removal — but the DENY still has to happen, and this
    is what catches a repair that only ever added."""
    f, _, function, _ = world()
    guard = f.of("guard", function)[0][0]
    operators = [f.show(o) for (o,) in f.of("operator", guard)]
    assert operators == ["ge"], f"a withdrawn claim is still visible: {operators}"


def test_a_WORD_and_a_LITERAL_are_different_kinds_of_entity():
    """⚠⚠ Conflating them made a corpus unable to talk about code: the operator was
    stored `repr`-encoded as `'gt'`, so a rule naming the bare `gt` could never
    match and one of the two repair families was **dead**. The suite could not
    tell, because the other keys on an integer, where `repr(18)` and the token `18`
    agree by luck."""
    f, _, function, _ = world(CORRECT)
    guard = f.of("guard", function)[0][0]
    assert f.one("operator", guard) == f.word("ge")
    assert f.one("operator", guard) != f.value("ge")


def test_the_answerer_TABLE_is_gone_and_says_so_rather_than_binding_nothing():
    """⚠ A caller that still registers a tool expects one to run. Answering
    *nothing was bound* by silently binding nothing is how a dead evaluator stays
    green."""
    with pytest.raises(NotImplementedError, match="system now"):
        register(Facts())
