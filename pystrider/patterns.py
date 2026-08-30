"""The neutral descriptions. THE BET lives in this file.

Each rule below is ONE description of a Python construct in a vocabulary that is
not Python's:

    forwards   structure  =>  description   -- RECOGNIZE intaken code

⚠⚠ **AND THE BACKWARD READING IS GONE, NOT PENDING.** A Python function has no
antecedent to read the other way. `test_spine.py` records the expectation it
would have to satisfy, and `pystrider/__init__.py` says what restoring it costs.

⭐ What survives intact is the other half, and it is the half every downstream slice
actually uses: intaken code is recognized in a vocabulary nothing in `intake.py`
speaks.

## ⚠ THE AUTHORING CONSTRAINT THAT SURVIVED EVERY SUBSTRATE CHANGE

Intake must not reuse a description's word. Intake says `ForStmt` / `Iterated` /
`Body`; the description says `Iteration` / `sequence` / `does`. If they coincided
the translation would do nothing for that part **while looking like it worked**,
and the perturbation pin would not bite there. Coincidental agreement is exactly
what this separation exists to make explicit — see
`test_spine.py::test_intake_and_the_patterns_share_NO_vocabulary`.

## ⭐⭐ THE ABSTENTION IS A QUERY TERM

`Readable` is attached by intake on every node it read, and NOT on the
placeholder it puts where an unmodelled construct was. So a description that asks
for `Readable` is saying: *I will not describe this loop's sequence if I could not
read it.* Measured before it existed: `for x in [c for c in xs]` was recognized as
an iteration and a sequence was asserted pointing at the unreadable placeholder — a
CONFIDENTLY WRONG description, not a missed one.

⚠ It is POSITIVE on purpose. `World.each` takes `without=`, so a rule here COULD
ask for the absence directly. It does not: a description that abstains because a
positive `Readable` is missing says *I was told this is readable*, while one keyed
on absence says *nobody told me otherwise* — and the second is how a reader that
simply never ran gets read as agreement.

## ⭐ WHAT `loopingrules` REMOVED THE LAST TRACE OF

A rule with `no <its own conclusion>` as an implicit premise, on an engine with no
inert set, was a HANG. `loopingrules`' loop settles on `world.revision` and
`World.attach` compares before it stores, so that whole class of bug cannot
recur — `without=` survives below because it is the honest reading of *the loops
not yet described*, not because anything depends on it to terminate.

⚠⚠ **2026-08-29: `relation("for_stmt")` is gone, and so is `Facts`.** Every
relation this module used to read or write generically is now the specific
component `intake.py` declares (`ForStmt`, `Target`, `Iterated`, `Body`, ...) or
this module declares for its own conclusions (`Iteration`, `Choice`) — read and
written straight through `World`, no adapter between. `_only()` — this module's
own inline reimplementation of "refuse to guess between several" — is gone too:
`World.each`'s single-valued-per-kind join already gives that guarantee (a
`ValueError` from `World.get`, loudly, the moment two coexist where the query
assumed one).
"""
from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient
from pystrider.intake import (Body, Call, Callee, Condition, ForStmt, Function,
                              IfStmt, Iterated, Readable, Stmt, Target, Then)

#: This module's OWN conclusions — nothing above declares these, and nothing
#: below reads them before this file attaches them.
#:
#: ⚠⚠ TRANSIENT, same as everything they are built from (`intake.py`'s own
#: block explains why): a recognition is a claim about ONE `intake()`'s
#: entities, so it means nothing once those are gone either. See
#: `loopingrules.world.transient`.


@transient
@dataclass(frozen=True)
class Iteration:
    item: int
    sequence: int
    does: int


@transient
@dataclass(frozen=True)
class Choice:
    tests: int
    otherwise_does: int


@transient
@dataclass(frozen=True)
class Applies:
    callee: int


@transient
@dataclass(frozen=True)
class LoopCount:
    """How many `for` statements sit DIRECTLY in a `Function`'s own body --
    an AGGREGATE description, not a construct classification the way
    `Iteration`/`Choice`/`Applies` are, but built the same way: forward,
    off `intake.py`'s own structure, deposited so anything else that ever
    wants "how many loops does this function have" reads it here instead
    of recomputing it inline (`pystrider.domain._reconcile_watch` is the
    first caller — see its own docstring for why it has to WAIT a tick
    for this the one time a watched function was just freshly re-read).

    ⚠ NOT recursive into a nested block (an `if`'s body, a nested `def`)
    — a real, named simplification: "how many loops this function has,"
    not "how many loops its whole subtree has."
    """

    count: int


def iteration(w) -> None:
    """`for x in xs: ...`  ->  an ITERATION over a SEQUENCE that DOES a block.

    ⚠ Every part is checked `Readable` before it is named. A loop whose sequence is
    a placeholder is not described — see the module note on abstention.
    """
    for entity, _for, target, iterated, body in w.each(
            ForStmt, Target, Iterated, Body, without=Iteration):
        item, sequence, does = target.entity, iterated.entity, body.entity
        if not all(w.has(part, Readable) for part in (item, sequence, does)):
            continue
        w.attach(entity, Iteration(item, sequence, does))


def conditional(w) -> None:
    """`if c: ...`  ->  a CHOICE that TESTS a condition and OTHERWISE_DOES a block."""
    for entity, _if, condition, then in w.each(IfStmt, Condition, Then, without=Choice):
        tests, otherwise = condition.entity, then.entity
        if not all(w.has(part, Readable) for part in (tests, otherwise)):
            continue
        w.attach(entity, Choice(tests, otherwise))


def application(w) -> None:
    """`f(...)`  ->  something APPLIES a callee."""
    for entity, _call, callee in w.each(Call, Callee, without=Applies):
        if not w.has(callee.entity, Readable):
            continue
        w.attach(entity, Applies(callee.entity))


def loop_count(w) -> None:
    """A `Function`  ->  its `LoopCount` — see that class's own docstring.

    ⚠ No `Readable` check, unlike the three above: an unreadable `for`
    would already be a placeholder that does not carry `ForStmt` at all
    (see `intake.py`'s own placeholder mechanism), so it is simply not
    counted rather than something this rule has to notice and abstain
    from. `without=LoopCount` here is a pure optimization, not a
    correctness guard the way it can be read as one above -- a reread
    destroys a `Function` entity outright rather than mutating it (see
    `pystrider.resolve.reread`), so one entity only ever gets counted
    once in its whole lifetime regardless.
    """
    for entity, _fn, body in w.each(Function, Body, without=LoopCount):
        count = sum(1 for stmt in w.get_all(w.entity(body.entity), Stmt)
                    if w.has(w.entity(stmt.entity), ForStmt))
        w.attach(entity, LoopCount(count))


#: ⭐ The descriptions, in one place, so a caller can install a SUBSET. The
#: perturbation pin needs exactly that: prove the bet by taking one description away
#: and watching recognition go dark.
DESCRIPTIONS = {"iteration": iteration, "conditional": conditional,
                "application": application, "loop_count": loop_count}


def install(loop, only=None) -> None:
    """Register the descriptions. `only` names a subset, for a control."""
    for name, make in DESCRIPTIONS.items():
        if only is None or name in only:
            loop.rule(make, name=f"patterns.{name}")
