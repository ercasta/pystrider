"""`pystrider/plan.py`'s pins — `docs/planning_bench.md`, exercised.

`repair.py` is untouched here: `make_world` installs it with `families=set()`,
so `guard`/`ask`/`answer`/`checked`/`diagnose` run (feeding `Unmet`,
`Evaluated`, `Agrees`) and no repair family or `repair.arbitrate` install
fights this module's own. `plan.py`'s families read `Unmet` and take it from
there.

⚠⚠ 2026-08-29: rewritten off `Facts`/`arbitration.commit` onto `World`/`Loop`
and the typed components `plan.py` now declares — see its own module note.
"""
from __future__ import annotations

from loopingrules.loop import Loop
from pystrider import plan, repair
from pystrider.evaluator import Case, Given, Wants, evaluate
from pystrider.intake import (Body, Comparison, Condition, Constant, Function,
                              IfStmt, Readable, Right, Stmt, decode_literal,
                              encode_literal, intake)

BUG = "def classify(age):\n    if age > 18:\n        return 'adult'\n    return 'minor'\n"
ZERO = "def classify(age):\n    if age > 0:\n        return 'adult'\n    return 'minor'\n"


def make_world(source: str = BUG, given=18, wants="adult"):
    """`(loop, function, case, name)` — `loop` stays in hand so a test that
    needs a second settle after mutating by hand (below) can just call
    `loop.run()` again, the rules already registered on it."""
    loop = Loop()
    repair.install(loop, families=set())
    plan.install(loop)
    intake(source, loop.world, "<test>")
    ((function, fn),) = loop.world.each(Function)
    case = loop.world.spawn(Case()).id
    loop.world.attach(case, Given(encode_literal(given)))
    loop.world.attach(function, Wants(case, encode_literal(wants)))
    loop.run()
    return loop, function.id, case, fn.name


def _guard_shape(w, function):
    """(operator, threshold) off whatever function is handed — the same
    structural read `repair.guard`/`resolve_guard_of` make, just for a test to
    check the RESULT of a path-copy rather than propose one."""
    body = w.get(function, Body)
    for stmt in w.get_all(body.entity, Stmt):
        statement = stmt.entity
        if not w.has(statement, IfStmt):
            continue
        condition = w.get(statement, Condition)
        if condition is not None and w.has(condition.entity, Comparison):
            comparison = w.get(condition.entity, Comparison)
            right = w.get(condition.entity, Right)
            literal = w.get(right.entity, Constant)
            return comparison.operator, decode_literal(literal.literal)
    return None


# -- the bench: private, structural, no shared mutation -------------------------

def test_both_families_propose_as_candidates():
    loop, function, _case, _name = make_world()
    proposed = {c.family for c in loop.world.get_all(function, plan.Candidate)}
    assert proposed == {"relax", "lower"}


def test_each_bench_edits_PRIVATELY_frame_zero_and_the_rival_untouched():
    loop, function, _case, name = make_world()
    w = loop.world
    zero = plan._frame_zero(w)

    # tied on consequence (see below) -- frame zero is not repointed yet.
    assert [c.function for c in w.get_all(zero, plan.Current) if c.name == name] == [function]
    assert _guard_shape(w, function) == ("gt", 18), "the ORIGINAL entity is never mutated"

    relax_bench = next(b.scenario for b in w.get_all(function, plan.Bench) if b.family == "relax")
    lower_bench = next(b.scenario for b in w.get_all(function, plan.Bench) if b.family == "lower")
    relaxed = [c.function for c in w.get_all(relax_bench, plan.Current) if c.name == name][-1]
    lowered = [c.function for c in w.get_all(lower_bench, plan.Current) if c.name == name][-1]
    assert relaxed not in (function, lowered)
    assert lowered != function
    assert _guard_shape(w, relaxed) == ("ge", 18)
    assert _guard_shape(w, lowered) == ("gt", 17)


def test_indistinguishable_fixes_are_AMBIGUOUS_not_guessed():
    """Both edits agree with every case this evaluator can read -- `>18`,
    `>=18` and `>17` are the same boolean function over integers. Ranking
    derived from consequences alone, honestly, refuses to break the tie a
    hand-picked priority used to break by fiat."""
    loop, function, _case, _name = make_world()
    w = loop.world
    assert plan.Ranked("relax", 1) in w.get_all(function, plan.Ranked)
    assert plan.Ranked("lower", 1) in w.get_all(function, plan.Ranked)
    assert w.get_all(function, plan.RuledOut) == []
    assert w.get(function, plan.Verdict).value == "ambiguous"
    assert w.get(function, plan.Winner) is None


# -- the two veto shapes ---------------------------------------------------------

def test_authored_policy_vetoes_a_negative_threshold_EVEN_THOUGH_it_would_fix():
    """`lower` on `age > 0` proposes `age > -1` -- which DOES fix `classify(0)`,
    same as `relax`'s `age >= 0`. The policy judge reads `Action` and rules it
    out before consequence ever gets consulted; `commit` computes eligible
    (candidates minus ruled-out) BEFORE ranking, so the tie `Ranked` alone
    would have left Ambiguous is broken structurally, not by luck."""
    loop, function, case, name = make_world(ZERO, given=0, wants="adult")
    w = loop.world
    inner = plan._function_named(w, name)
    guard_q = plan._guard_of(w, inner)
    assert plan.Action("lower", guard_q, encode_literal(-1)) in w.get_all(function, plan.Action)
    assert plan.RuledOut("lower", "negative_threshold") in w.get_all(function, plan.RuledOut)
    assert w.get(function, plan.Verdict).value == "forced"
    assert w.get(function, plan.Winner).family == "relax"

    zero = plan._frame_zero(w)
    applied = [c.function for c in w.get_all(zero, plan.Current) if c.name == name][-1]
    assert applied != function
    assert _guard_shape(w, applied) == ("ge", 0)
    assert evaluate(w, applied, case).value == "adult"
    # the loser never touched frame zero, or the world at all past its own bench
    assert not any(r.family == "relax" for r in w.get_all(function, plan.RuledOut))


def test_consequence_veto_catches_a_candidate_that_does_not_fix():
    """A rival that structurally applies but doesn't derive the wanted value —
    built directly off `plan.py`'s own helpers rather than a real repair
    family, the way `docs/decision_patterns.md`'s own worked example is
    illustrative rather than a claim that this bug ever produces one."""
    loop, function, _case, name = make_world()
    w = loop.world
    bench = plan._bench(w, "sabotage", function)
    w.attach(bench, plan.Current(name, function))
    broken = plan._clone(w, function, "sabotage", {Readable: []})
    plan._move_current(w, bench, name, broken)
    w.attach(function, plan.Candidate("sabotage"))
    loop.run()
    assert plan.RuledOut("sabotage", "does_not_fix") in w.get_all(function, plan.RuledOut)


# -- resolvers refuse rather than guess ------------------------------------------

def test_an_unresolvable_query_is_REFUSED_BY_NAME_not_silently_dropped():
    loop, function, _case, _name = make_world()
    w = loop.world
    query = plan._function_named(w, "no_such_function")  # a fresh name -- safe to mint directly
    loop.run()
    zero = plan._frame_zero(w)
    assert plan.CouldNotResolve(zero) in w.get_all(query, plan.CouldNotResolve)
    assert w.get_all(query, plan.Denotes) == []
