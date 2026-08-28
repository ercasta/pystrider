"""`pystrider/plan.py`'s pins — `docs/planning_bench.md`, exercised.

`repair.py` is untouched here: `world()` installs it with `families=set()`, so
`guard`/`ask`/`answer`/`checked`/`diagnose` run (feeding `unmet`, `evaluated`,
`agrees`) and no repair family or `arbitration.commit` install fights this
module's own. `plan.py`'s families read `unmet` and take it from there.
"""
from __future__ import annotations

from pystrider import plan, repair
from pystrider.evaluator import evaluate
from pystrider.intake import intake
from ugm.facts import Facts, Printed

BUG = "def classify(age):\n    if age > 18:\n        return 'adult'\n    return 'minor'\n"
ZERO = "def classify(age):\n    if age > 0:\n        return 'adult'\n    return 'minor'\n"


def world(source: str = BUG, given=18, wants="adult"):
    f = Facts(lambda loop, ff: repair.install(loop, ff, families=set()),
              lambda loop, ff: plan.install(loop, ff))
    intake(source, f, "<test>")
    function = f.subjects("function")[0]
    case = f.node("case")
    f.fact("case", case)
    f.fact("given", case, f.value(given))
    f.fact("wants", function, case, f.value(wants))
    f.run()
    return f, function, case


def _find(f, text):
    """The REAL entity already printed as `text`, for a test reading back what a
    SYSTEM minted mid-turn. ⚠⚠ Never `plan._bench(f, ...)` et al. after `f.run()`
    — those go through `f.node()`, and `f.node()` called OUTSIDE a system does
    not deduplicate against an already-settled entity (only a mid-turn `Pending`
    is checked via `_find`; see `facts.py`'s own module note on `_mint`). Calling
    a minting helper from test code for something a system already made spawns a
    SECOND, unconnected entity with the same name — this is the read-only,
    never-spawns way back to the one a system actually used."""
    for entity, printed in f.world.each(Printed):
        if printed.text == text:
            return entity
    return None


def _word(f, text):
    """`f.word(text)` for a word a SYSTEM minted — read-only, via `_find`."""
    return _find(f, text)


def _val(f, payload):
    """`f.value(payload)` for a value a SYSTEM minted — read-only, via `_find`.

    ⚠⚠ `f.value(-1)` here spawned a SECOND entity printed `-1`, and the assertion
    that used it compared the real one against the twin and read False. `_mint`
    de-duplicates against an already-settled entity only INSIDE a turn; `word`/
    `value` also carry `_words`/`_values`, but those cache a real entity only when
    a LATER tick asks again, and `_adopt` rescans the world exactly once per
    `Facts`. So these reads passed for as long as some system re-derived the same
    word or value every tick — which is to say they were pinned by the very
    non-termination `plan.Enacted` fixes. Same rule as `_find`: read, never mint.
    """
    return _find(f, repr(payload))


def _guard_shape(f, function):
    """(operator, threshold) off whatever function is handed — the same
    structural read `repair.guard`/`resolve_guard_of` make, just for a test to
    check the RESULT of a path-copy rather than propose one."""
    block = f.one("body", function)
    for (statement,) in [r for r in f.of("stmt", block) if len(r) == 1]:
        if not f.has("if_stmt", statement):
            continue
        condition = f.one("condition", statement)
        if condition is not None and f.has("comparison", condition):
            right = f.one("right", condition)
            return f.text("operator", condition), f.literal("literal", right)
    return None


# -- the bench: private, structural, no shared mutation -------------------------

def test_both_families_propose_as_candidates():
    f, function, _ = world()
    proposed = {f.show(o) for (o,) in f.of("candidate", function)}
    assert proposed == {"relax", "lower"}


def test_each_bench_edits_PRIVATELY_frame_zero_and_the_rival_untouched():
    f, function, _ = world()
    name = f.one("name", function)
    zero = _find(f, "scenario:frame_zero")

    # tied on consequence (see below) -- frame zero is not repointed yet.
    assert [fn for (n, fn) in f.of("current", zero) if n == name] == [function]
    assert _guard_shape(f, function) == ("gt", 18), "the ORIGINAL entity is never mutated"

    relax_bench = _find(f, f"scenario:bench:relax:{f.show(function)}")
    lower_bench = _find(f, f"scenario:bench:lower:{f.show(function)}")
    relaxed = [fn for (n, fn) in f.of("current", relax_bench) if n == name][-1]
    lowered = [fn for (n, fn) in f.of("current", lower_bench) if n == name][-1]
    assert relaxed not in (function, lowered)
    assert lowered != function
    assert _guard_shape(f, relaxed) == ("ge", 18)
    assert _guard_shape(f, lowered) == ("gt", 17)


def test_indistinguishable_fixes_are_AMBIGUOUS_not_guessed():
    """Both edits agree with every case this evaluator can read -- `>18`,
    `>=18` and `>17` are the same boolean function over integers. Ranking
    derived from consequences alone, honestly, refuses to break the tie a
    hand-picked `ranked(..., 2)` used to break by fiat."""
    f, function, _ = world()
    assert f.holds("ranked", function, _word(f, "relax"), _val(f, 1))
    assert f.holds("ranked", function, _word(f, "lower"), _val(f, 1))
    assert not f.of("ruled_out", function)
    assert f.text("verdict", function) == "ambiguous"
    assert f.text("winner", function) is None


# -- the two veto shapes ---------------------------------------------------------

def test_authored_policy_vetoes_a_negative_threshold_EVEN_THOUGH_it_would_fix():
    """`lower` on `age > 0` proposes `age > -1` -- which DOES fix `classify(0)`,
    same as `relax`'s `age >= 0`. The policy judge reads `action` and rules it
    out before consequence ever gets consulted; `commit` computes eligible
    (candidates minus ruled-out) BEFORE ranking, so the tie `ranked` alone
    would have left Ambiguous is broken structurally, not by luck."""
    f, function, case = world(ZERO, given=0, wants="adult")
    name = f.one("name", function)
    inner = _find(f, f"query:function_named:{f.show(name)}")
    guard_q = _find(f, f"query:guard_of:{f.show(inner)}")
    assert f.holds("action", function, _word(f, "lower"), guard_q, _val(f, -1))
    assert f.holds("ruled_out", function, _word(f, "lower"), _word(f, "negative_threshold"))
    assert f.text("verdict", function) == "forced"
    assert f.text("winner", function) == "relax"

    zero = _find(f, "scenario:frame_zero")
    applied = [fn for (n, fn) in f.of("current", zero) if n == name][-1]
    assert applied != function
    assert _guard_shape(f, applied) == ("ge", 0)
    assert evaluate(f, applied, case).value == "adult"
    # the loser never touched frame zero, or the world at all past its own bench
    assert not f.holds("ruled_out", function, _word(f, "relax"))


def test_consequence_veto_catches_a_candidate_that_does_not_fix():
    """A rival that structurally applies but doesn't derive the wanted value —
    built directly off `plan.py`'s own helpers rather than a real repair family,
    the way `arbitration.py`'s own tests use a worked pizza example: illustrative,
    not a claim that this bug ever produces one."""
    f, function, case = world()
    name = f.one("name", function)
    bench = plan._bench(f, "sabotage", function)
    f.fact("current", bench, name, function)
    broken = plan._clone(f, f.world, function, "sabotage", readable=())
    plan._move_current(f, bench, name, broken)
    f.fact("candidate", function, f.word("sabotage"))
    f.run()
    assert f.holds("ruled_out", function, f.word("sabotage"), _word(f, "does_not_fix"))


# -- resolvers refuse rather than guess ------------------------------------------

def test_an_unresolvable_query_is_REFUSED_BY_NAME_not_silently_dropped():
    f, function, _ = world()
    ghost = f.word("no_such_function")
    query = plan._function_named(f, ghost)  # a fresh text -- safe to mint directly
    f.run()
    zero = _find(f, "scenario:frame_zero")
    assert f.holds("could_not_resolve", query, zero)
    assert not f.of("denotes", query)
