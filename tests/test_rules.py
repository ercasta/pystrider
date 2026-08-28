"""`pystrider/rules.py`'s pins — the three shapes, and what each one REFUSES.

⭐ These are the point of the module. That `plan.py` still passes after being
rewritten onto the combinators says only that the rewrite was faithful; what has
to be pinned is that the shapes make the two failures UNWRITEABLE.
"""
from __future__ import annotations

import pytest

from pystrider import rules
from ugm.facts import Facts, relation

Seed = relation("seed")


def world(*systems):
    def install(loop, f):
        for i, system in enumerate(systems):
            f.system(system(f), name=f"probe.{i}")
    return Facts(install)


# -- derive: reads and deposits, and cannot do anything else ---------------------

def test_derive_deposits_what_say_answers():
    f = world(lambda f: rules.derive(
        f, Seed, lambda f, s, n: ("doubled", s, f.value(f.payload(n) * 2)), arity=1))
    s = f.node("s")
    f.fact("seed", s, f.value(21))
    f.run()
    assert f.literal("doubled", s) == 42


def test_derive_says_nothing_by_answering_None():
    f = world(lambda f: rules.derive(f, Seed, lambda f, s, n: None, arity=1))
    s = f.node("s")
    f.fact("seed", s, f.value(1))
    f.run()
    assert f.of("doubled", s) == []


def test_a_derive_that_INVENTS_is_refused_by_name():
    """⚠⚠ The judge shape. `judge_consequences` reached for `_bench()` — a
    minting helper — merely to READ the bench it was judging, and nothing in the
    old `def system(world)` could tell. Minting is what costs the termination
    argument, so `derive` takes `node` away for the length of the rule."""
    f = world(lambda f: rules.derive(f, Seed, lambda f, s, n: f.node("invented"), arity=1))
    f.fact("seed", f.node("s"), f.value(1))
    with pytest.raises(RuntimeError, match=r"`derive` rule called `node\(\)`"):
        f.run()


def test_a_derive_that_RETRACTS_is_refused_by_name():
    """The other half of the argument: monotone. A rule that can take a fact back
    can oscillate, and `derive`'s bound assumes it never does."""
    f = world(lambda f: rules.derive(f, Seed, lambda f, s, n: f.deny("seed", s, n), arity=1))
    f.fact("seed", f.node("s"), f.value(1))
    with pytest.raises(RuntimeError, match=r"`derive` rule called `deny\(\)`"):
        f.run()


# -- assign: one row per key ----------------------------------------------------

def test_assign_retracts_the_row_that_shared_the_key():
    f = Facts()
    q, s = f.node("q"), f.node("scenario")
    rules.assign(f, "denotes", q, s, f.node("first"), keys=1)
    rules.assign(f, "denotes", q, s, f.node("second"), keys=1)
    assert [f.show(e) for (_, e) in f.of("denotes", q)] == ["second"]


def test_assign_leaves_a_DIFFERENT_key_alone():
    f = Facts()
    q, a, b = f.node("q"), f.node("scenario_a"), f.node("scenario_b")
    rules.assign(f, "denotes", q, a, f.node("in_a"), keys=1)
    rules.assign(f, "denotes", q, b, f.node("in_b"), keys=1)
    assert sorted(f.show(e) for (_, e) in f.of("denotes", q)) == ["in_a", "in_b"]


# -- minting: once per key, and the key is the termination argument -------------

def test_minting_fires_ONCE_even_though_its_trigger_still_holds():
    """⚠⚠ THE RUNAWAY, in miniature. This rule's precondition is one its own
    output can never falsify — exactly `plan.lower`, which applied wherever a
    literal sat on the right of a guard and left a literal there. Under a bare
    `def system(world)` it minted 18, 17, 16, 15 … until the OOM killer took the
    box. The key is what ends it, and the rule itself is no more careful."""
    made = []

    def act(f, world, subject, n, key):
        made.append(f.node(f"clone:{len(made)}"))
        return True

    f = world(lambda f: rules.minting(
        f, Seed, lambda f, s, n: ((s,),), act, arity=1))
    f.fact("seed", f.node("s"), f.value(1))
    f.run()
    assert len(made) == 1


def test_a_DECLINED_key_stays_open_for_a_later_tick():
    """`_try_edit` answers False when arbitration has not named a winner yet.
    That must not spend the key, or the winner could never enact."""
    calls = []

    def act(f, world, subject, n, key):
        calls.append(1)
        return False if len(calls) < 3 else True

    def bump(f):                      # keeps the world changing so ticks continue
        return rules.derive(f, Seed, lambda f, s, n: ("tick", s, f.value(len(calls))), arity=1)

    f = world(lambda f: rules.minting(f, Seed, lambda f, s, n: ((s,),), act, arity=1), bump)
    f.fact("seed", f.node("s"), f.value(1))
    f.run()
    assert len(calls) == 3            # declined twice, acted on the third
