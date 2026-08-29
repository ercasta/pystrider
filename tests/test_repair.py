"""Slice 2's pins — a diagnosis drives a code repair.

⭐⭐ **SEVEN OF THESE WERE `xfail(strict=True)` ON AN EARLIER ENGINE AND PASS
HERE**, and the reason is worth stating so nobody reads it as more than it is.
They were blocked on `unmet`, which backward reading produced; a rewrite
deleted the goal apparatus and nothing replaced it. `repair.diagnose` derives
the same occasion FORWARD — *the case wants `v`, the code was read and does
not produce `v`*.

⚠ That is a narrower thing than backward reading, and `repair.py`'s note says so:
no goal expansion, no subgoal search, no choice of which tap to try. It reaches this
shape of problem and would not reach a goal needing more than one subgoal to be
found unmet. The slice works; the general capability is still absent.

⚠⚠ 2026-08-29: rewritten off `Facts`/`ugm.arbitration.commit` onto
`loopingrules.world.World` and the typed components `evaluator.py`/`repair.py`
now declare — see those modules' own notes.
"""
from __future__ import annotations

import pytest

from loopingrules.loop import Loop
from pystrider import patterns, repair
from pystrider.emit import emit
from pystrider.evaluator import (Case, CouldNotEvaluate, Evaluated, Given,
                                 Guard, Wants, evaluate, register)
from pystrider.intake import Comparison, Function, encode_literal, intake
from pystrider.repair import (Agrees, Candidate, Lowered, Relaxed, Repaired,
                              Unmet, Verdict, Winner)

BUG = "def classify(age):\n    if age > 18:\n        return 'adult'\n    return 'minor'\n"
CORRECT = "def classify(age):\n    if age >= 18:\n        return 'adult'\n    return 'minor'\n"


def make_world(source: str = BUG, given=18, wants="adult", **repair_options):
    """Intake, seed the case, and settle. `repair_options` reach `repair.install`."""
    loop = Loop()
    patterns.install(loop)
    repair.install(loop, **repair_options)
    taken = intake(source, loop.world, "<test>")
    ((function, _tag),) = loop.world.each(Function)
    # ⚠ `.id`, not the `Entity` handle `spawn` hands back: every OTHER
    # component field that names this case (`Wants.case`, `Evaluated.case`,
    # ...) is lowered to a plain int the instant it round-trips through
    # `attach()` — comparing an `Entity` against the int later stored beside
    # it is `Entity.__eq__`'s one deliberate refusal (never true against a
    # bare int), so this test holds the same plain id everything else does.
    case = loop.world.spawn(Case()).id
    loop.world.attach(case, Given(encode_literal(given)))
    loop.world.attach(function, Wants(case, encode_literal(wants)))
    loop.run()
    return loop.world, taken, function, case


def ran(source: str):
    namespace: dict = {}
    exec(compile(source, "<repaired>", "exec"), namespace)   # noqa: S102
    return namespace["classify"]


# -- diagnosis ------------------------------------------------------------------


def test_what_the_code_does_is_DERIVED_FROM_STRUCTURE_not_by_running_it():
    w, _, function, case = make_world()
    # ⚠ Asked of the ORIGINAL structure would say 'minor'; by now the repair has
    # run, so what the derivation reports is the repaired code. Both readings are
    # in `Evaluated` — see the CHANGE-then-OBSERVE pin below.
    assert Evaluated(case, encode_literal("minor")) in w.get_all(function, Evaluated)


def test_the_diagnosis_finds_the_goal_UNMET_and_the_repair_reaches_the_REAL_world():
    w, _, function, case = make_world()
    assert Agrees(case) in w.get_all(function, Agrees), "the goal comes to hold after repair"
    assert Repaired(case) in w.get_all(function, Repaired)


def test_CHANGE_then_OBSERVE_the_evaluation_is_re_derived_after_the_change():
    """A repair is not done until its effect is observed. Two evaluations, not one."""
    w, _, function, _case = make_world()
    assert len(w.get_all(function, Evaluated)) == 2


# -- the artefact ---------------------------------------------------------------


def test_the_emitted_source_RUNS_and_answers_the_case():
    """⚠⚠ THE INDEPENDENT GATE. A plan that changes nothing is indistinguishable
    from a real fix unless something inspects the artefact."""
    w, taken, _, _ = make_world()
    repaired = emit(w, taken.module)
    assert repaired.strip() != BUG.strip()
    assert ran(repaired)(18) == "adult"
    assert ran(repaired)(5) == "minor"


def test_exactly_ONE_repair_family_fires():
    """⚠⚠ It was TWO on an earlier engine, and the emitted code read
    `if age >= 17` — two independent fixes for one bug, correct by luck and
    wrong as a repair.

    There, `unmet` was a fact on an append-only chain and stayed written after
    the first repair. Here a RULE re-runs every tick, so denying the occasion
    is not enough on its own — `Repaired(case)` is the durable mark that makes
    it stick. If this goes red, over-repair is back through the new door.
    """
    w, _, _, _ = make_world()
    assert len(w.all(Relaxed)) + len(w.all(Lowered)) == 1


# -- the rivals -----------------------------------------------------------------


@pytest.mark.parametrize("only", ["relax", "lower"])
def test_EITHER_repair_family_alone_genuinely_fixes_it(only):
    """⚠ A pin that named its winner by hand went silently vacuous the moment
    the tie-break flipped — it passed while exercising the family the planner
    had just chosen. Both are checked here, so which one wins is free to
    change."""
    w, taken, _, _ = make_world(families={only})
    classify = ran(emit(w, taken.module))
    assert classify(18) == "adult" and classify(5) == "minor"


def test_the_two_families_reach_DIFFERENT_source_and_both_are_correct():
    """"found A" must not be read as "B is wrong"."""
    relaxed = emit(*_module(make_world(families={"relax"})))
    lowered = emit(*_module(make_world(families={"lower"})))
    assert relaxed != lowered
    assert "age >= 18" in relaxed and "age > 17" in lowered


def _module(built):
    w, taken, _, _ = built
    return w, taken.module


def test_which_family_won_is_a_NAMED_FACT_not_registration_order():
    """docs/decision_patterns.md's claim, pinned: both rivals are on the
    record as `Candidate`s, and which one fired is a `Winner`/`Verdict`
    fact readable directly, not an artefact of `FAMILIES` dict order."""
    w, _, function, _ = make_world()
    proposed = {c.name for c in w.get_all(function, Candidate)}
    assert proposed == {"relax", "lower"}
    assert w.get(function, Winner).name == "relax"
    assert w.get(function, Verdict).value == "forced"


# -- ⭐ what makes a repair unproposable ----------------------------------------


def test_WITHOUT_the_diagnosis_a_repair_damages_CORRECT_code():
    """⭐⭐ The measurement this slice exists for.

    The condition is an ordinary query term — so it is arguable, and another
    author can write a different one. `gated=False` removes it and the repair
    fires on correct code.
    """
    w, taken, _, _ = make_world(CORRECT, gated=False)
    assert emit(w, taken.module).strip() != CORRECT.strip()


def test_WITH_it_correct_code_is_left_alone():
    w, taken, _, _ = make_world(CORRECT)
    assert emit(w, taken.module).strip() == CORRECT.strip()
    assert not w.all(Relaxed) and not w.all(Lowered)


# -- the membrane ---------------------------------------------------------------


def test_an_unmodelled_operator_is_refused_BY_NAME_and_nothing_is_concluded():
    """⚠⚠⚠ An earlier evaluator said in PROSE that it modelled `gt`/`ge` only
    and fell through to `gt` for everything else, deriving `age < 18` as
    `age > 18` and answering `'minor'` about code that plainly returns
    `'adult'`. **A membrane described in prose is not a membrane.**"""
    src = "def classify(age):\n    if age is 18:\n        return 'adult'\n    return 'minor'\n"
    w, _, function, case = make_world(src)
    verdict = evaluate(w, function, case)
    assert verdict.refused == "unmodelled_operator:is" and verdict.value is None
    assert not w.get_all(function, Evaluated)
    assert w.get_all(function, CouldNotEvaluate), "the refusal is DEPOSITED, not swallowed"


def test_CONTROL_an_operator_that_IS_modelled_is_not_refused():
    """Or the pin above would pass for a function it simply could not read."""
    src = "def classify(age):\n    if age < 18:\n        return 'minor'\n    return 'adult'\n"
    w, _, function, case = make_world(src, given=5, wants="minor")
    assert evaluate(w, function, case).refused is None


# -- the substrate the repair rests on ------------------------------------------


def test_repair_is_REPLACE_and_the_reader_sees_the_CURRENT_claim():
    """⚠⚠ On an append-only chain *change this* was `-old, +new` and a reader
    over its own deposit log would see BOTH and emit the code that was just
    repaired. `World.replace` makes the old value genuinely gone — but the
    replace still has to actually happen, and this is what catches a repair
    that only ever added."""
    w, _, function, _ = make_world()
    guard = w.get_all(function, Guard)[0]
    comp = w.get(guard.entity, Comparison)
    assert comp.operator == "ge", f"a withdrawn claim is still visible: {comp.operator}"
    assert len(w.get_all(guard.entity, Comparison)) == 1, "replace, not a second row beside it"


def test_the_answerer_TABLE_is_gone_and_says_so_rather_than_binding_nothing():
    """⚠ A caller that still registers a tool expects one to run. Answering
    *nothing was bound* by silently binding nothing is how a dead evaluator
    stays green."""
    with pytest.raises(NotImplementedError, match="rule now"):
        register()
