"""The neutral descriptions. THE BET lives in this file.

Each system below is ONE description of a Python construct in a vocabulary that is
not Python's:

    forwards   structure  =>  description   -- RECOGNIZE intaken code

⚠⚠ **AND THE BACKWARD READING IS GONE, NOT PENDING.** On `ugm`'s restart engine a
rule was DATA, so the same authored implication could be read the other way — an
antecedent became a work order for WRITING the construct. That is what
`rules/patterns.ugm` was, and it is the half of the bet this port does not keep: a
Python function has no antecedent to read. `test_spine.py` records the expectation
it would have to satisfy, and `pystrider/__init__.py` says what restoring it costs.

⭐ What survives intact is the other half, and it is the half every downstream slice
actually uses: intaken code is recognized in a vocabulary nothing in `intake.py`
speaks.

## ⚠ THE AUTHORING CONSTRAINT THAT SURVIVED EVERY SUBSTRATE CHANGE

Intake must not reuse a description's word. Intake says `for_stmt` / `iterated` /
`body`; the description says `iteration` / `sequence` / `does`. If they coincided
the translation would do nothing for that part **while looking like it worked**,
and the perturbation pin would not bite there. Coincidental agreement is exactly
what this separation exists to make explicit — see
`test_spine.py::test_intake_and_the_patterns_share_NO_vocabulary`.

## ⭐⭐ THE ABSTENTION IS A QUERY TERM

`readable($x)` is asserted by intake on every node it read, and NOT on the
placeholder it puts where an unmodelled construct was. So a description that asks
for `Readable` is saying: *I will not describe this loop's sequence if I could not
read it.* Measured before it existed: `for x in [c for c in xs]` was recognized as
an iteration and `sequence(loop, <unreadable>)` was asserted — a CONFIDENTLY WRONG
description, not a missed one.

⚠ It is POSITIVE on purpose, and that is no longer forced. On `ugm` a rule could
not say *nothing claims this*, so intake had to assert the good case. `World.each`
takes `without=`, so a system here COULD ask for the absence directly. It does not:
a description that abstains because a positive `readable` is missing says *I was
told this is readable*, while one keyed on absence says *nobody told me otherwise* —
and the second is how a reader that simply never ran gets read as agreement.

## ⭐ WHAT THE PORT DELETED

Every rule in `patterns.ugm` carried `no <its own conclusion>` as a premise, and a
rule without one was a HANG — `ugm` had no inert set, so a rule that did not stop
itself re-fired for ever while every later rule never ran. The `harneskills` loop
settles on `world.revision` and `attach` compares before it stores, so that whole
class of bug is gone. `without=` survives below because it is the honest reading of
*the loops not yet described*, not because anything depends on it.
"""
from __future__ import annotations

from .facts import Facts, relation

#: The vocabulary these systems read and write, bound once so the queries read like
#: the `harneskills` examples they are.
ForStmt = relation("for_stmt")
IfStmt = relation("if_stmt")
Call = relation("call")
Target = relation("target")
Iterated = relation("iterated")
Body = relation("body")
Condition = relation("condition")
Then = relation("then")
Callee = relation("callee")
Readable = relation("readable")
Iteration = relation("iteration")
Choice = relation("choice")


def _only(rows):
    """The single object of a one-place row set, or None. `Facts.one`'s refusal,
    inline, because a system holds the component already."""
    return rows[0][0] if len(rows) == 1 and len(rows[0]) == 1 else None


def iteration(f: Facts):
    """`for x in xs: ...`  ->  an ITERATION over a SEQUENCE that DOES a block.

    ⚠ Every part is checked `readable` before it is named. A loop whose sequence is
    a placeholder is not described — see the module note on abstention.
    """

    def system(world) -> None:
        for entity, _kind in world.each(ForStmt, without=Iteration):
            item = _only(f.of("target", entity))
            sequence = _only(f.of("iterated", entity))
            does = _only(f.of("body", entity))
            if item is None or sequence is None or does is None:
                continue
            if not all(f.has("readable", part) for part in (item, sequence, does)):
                continue
            f.fact("iteration", entity)
            f.fact("item", entity, item)
            f.fact("sequence", entity, sequence)
            f.fact("does", entity, does)

    return system


def conditional(f: Facts):
    """`if c: ...`  ->  a CHOICE that TESTS a condition and OTHERWISE_DOES a block."""

    def system(world) -> None:
        for entity, _kind in world.each(IfStmt, without=Choice):
            tests = _only(f.of("condition", entity))
            otherwise = _only(f.of("then", entity))
            if tests is None or otherwise is None:
                continue
            if not all(f.has("readable", part) for part in (tests, otherwise)):
                continue
            f.fact("choice", entity)
            f.fact("tests", entity, tests)
            f.fact("otherwise_does", entity, otherwise)

    return system


def application(f: Facts):
    """`f(...)`  ->  something APPLIES a callee."""

    def system(world) -> None:
        for entity, _kind in world.each(Call):
            callee = _only(f.of("callee", entity))
            if callee is None or not f.has("readable", callee):
                continue
            f.fact("applies", entity, callee)

    return system


#: ⭐ The descriptions, in one place, so a caller can install a SUBSET. The
#: perturbation pin needs exactly that: prove the bet by taking one description away
#: and watching recognition go dark.
DESCRIPTIONS = {"iteration": iteration, "conditional": conditional,
                "application": application}


def install(loop, f: Facts, only=None) -> None:
    """Register the descriptions. `only` names a subset, for a control."""
    for name, make in DESCRIPTIONS.items():
        if only is None or name in only:
            loop.system(make(f), name=f"patterns.{name}")
