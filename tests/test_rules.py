"""`pystrider/rules.py`'s pins — the three shapes, and what each one REFUSES.

⭐ These are the point of the module. That `plan.py` still passes after being
rewritten onto the combinators says only that the rewrite was faithful; what has
to be pinned is that the shapes make the two failures UNWRITEABLE.

⚠⚠ 2026-08-29: rewritten off `Facts`/`relation` onto `World`/`Loop` and typed
components — see `rules.py`'s own note on the generalization. `f.run()`
raising on a rule error was `Facts.run()`'s own behaviour; `Loop.run()` alone
does not (it records the error and moves on, right for a shared prompt) — the
two tests that need the raise use `pystrider.strict.run` instead, the
replacement for exactly that one thing `Facts.run()` did.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from loopingrules.loop import Loop
from pystrider import rules
from pystrider.intake import decode_literal, encode_literal
from pystrider.strict import run as strict_run


@dataclass(frozen=True)
class Seed:
    n: str  # `repr`-encoded — see `intake.encode_literal`


@dataclass(frozen=True)
class Doubled:
    value: str


def world(*rule_makers):
    loop = Loop()
    for i, make in enumerate(rule_makers):
        loop.rule(make(), name=f"probe.{i}")
    return loop


# -- derive: reads and attaches, and cannot do anything else ---------------------

def test_derive_deposits_what_say_answers():
    loop = world(lambda: rules.derive(
        Seed, lambda w, s, seed: (s, Doubled(encode_literal(decode_literal(seed.n) * 2)))))
    s = loop.world.spawn(Seed(encode_literal(21))).id
    loop.run()
    assert decode_literal(loop.world.get(s, Doubled).value) == 42


def test_derive_says_nothing_by_answering_None():
    loop = world(lambda: rules.derive(Seed, lambda w, s, seed: None))
    s = loop.world.spawn(Seed(encode_literal(1))).id
    loop.run()
    assert loop.world.get(s, Doubled) is None


def test_a_derive_that_INVENTS_is_refused_by_name():
    """⚠⚠ The judge shape. `plan.judge_consequences` reached for `_bench()` — a
    minting helper — merely to READ the bench it was judging, and nothing in a
    bare `def rule(world)` could tell. Minting is what costs the termination
    argument, so `derive` takes `spawn` away for the length of the rule."""
    loop = world(lambda: rules.derive(Seed, lambda w, s, seed: w.spawn()))
    loop.world.attach(loop.world.spawn().id, Seed(encode_literal(1)))
    with pytest.raises(RuntimeError, match=r"`derive` rule called `spawn\(\)`"):
        strict_run(loop)


def test_a_derive_that_RETRACTS_is_refused_by_name():
    """The other half of the argument: monotone. A rule that can take a
    component back can oscillate, and `derive`'s bound assumes it never does."""
    loop = world(lambda: rules.derive(Seed, lambda w, s, seed: w.detach(s, Seed)))
    loop.world.attach(loop.world.spawn().id, Seed(encode_literal(1)))
    with pytest.raises(RuntimeError, match=r"`derive` rule called `detach\(\)`"):
        strict_run(loop)


# -- assign: one component per key ------------------------------------------------

def test_assign_retracts_the_component_that_shared_the_key():
    loop = Loop()
    q = loop.world.spawn().id
    rules.assign(loop.world, q, Doubled, Doubled("first"), key=lambda d: "the-only-key")
    rules.assign(loop.world, q, Doubled, Doubled("second"), key=lambda d: "the-only-key")
    assert [d.value for d in loop.world.get_all(q, Doubled)] == ["second"]


def test_assign_leaves_a_DIFFERENT_key_alone():
    @dataclass(frozen=True)
    class Denotes:
        scenario: str
        entity: str

    loop = Loop()
    q = loop.world.spawn().id
    rules.assign(loop.world, q, Denotes, Denotes("a", "in_a"), key=lambda d: d.scenario)
    rules.assign(loop.world, q, Denotes, Denotes("b", "in_b"), key=lambda d: d.scenario)
    assert sorted(d.entity for d in loop.world.get_all(q, Denotes)) == ["in_a", "in_b"]


# -- minting: once per key, and the key is the termination argument -------------

def test_minting_fires_ONCE_even_though_its_trigger_still_holds():
    """⚠⚠ THE RUNAWAY, in miniature. This rule's precondition is one its own
    output can never falsify — exactly `plan.lower`, which applied wherever a
    literal sat on the right of a guard and left a literal there. Under a bare
    `def rule(world)` it minted 18, 17, 16, 15 … until the OOM killer took the
    box. The key is what ends it, and the rule itself is no more careful."""
    made = []

    def act(w, subject, seed, key):
        made.append(w.spawn())
        return True

    loop = world(lambda: rules.minting(Seed, lambda w, s, seed: ((s,),), act))
    loop.world.attach(loop.world.spawn().id, Seed(encode_literal(1)))
    loop.run()
    assert len(made) == 1


def test_a_DECLINED_key_stays_open_for_a_later_tick():
    """`plan._try_edit` answers False when arbitration has not named a winner
    yet. That must not spend the key, or the winner could never enact."""
    calls = []

    def act(w, subject, seed, key):
        calls.append(1)
        return False if len(calls) < 3 else True

    @dataclass(frozen=True)
    class Tick:
        value: str

    def bump():                       # keeps the world changing so ticks continue
        return rules.derive(Seed, lambda w, s, seed: (s, Tick(encode_literal(len(calls)))))

    loop = world(lambda: rules.minting(Seed, lambda w, s, seed: ((s,),), act), bump)
    loop.world.attach(loop.world.spawn().id, Seed(encode_literal(1)))
    loop.run()
    assert len(calls) == 3            # declined twice, acted on the third
