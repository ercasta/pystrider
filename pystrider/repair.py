"""Slice 2 — a diagnosis drives a code repair, on the harneskills floor.

The same off-by-one guard bug engine 2 repaired, re-derived here so the result
checks against a real prior one rather than against nothing.

## ⚠⚠ WHAT `unmet` WAS, AND WHAT IT IS NOW — the one honest substitution

`rules/repair.ugm` gated both repair families on `+unmet($p, evaluated($f,$c,$v))`,
and `unmet` was produced by BACKWARD READING: the engine expanded the goal
`agrees($f,$c)` into subgoals, found `evaluated($f,$c,$v)` unsatisfied, and wrote
the occasion. That apparatus is gone twice over — upstream deleted `Machine.focus`,
`GOAL` and `SUBGOAL` on the way to the scratchpad, and a Python system has no
antecedent to read backwards even in principle.

⭐ **So `unmet` is DERIVED FORWARD here, and the substitution is narrower than the
thing it replaces.** `diagnose` below says: *the case wants `v`, the code was
evaluated and does not produce `v`* — no goal expansion, no subgoal search, no
choice of which tap to try. It reaches the same occasion for this shape of problem
and it is not backward reading, and the difference matters the moment a goal needs
more than one subgoal to be found unmet.

⚠ **It is still a GATE, which is the measurement slice 2 exists for.** Survey §2
listed *a rule's condition is its parameter type* as the one item that was a
redesign rather than a port; the answer is that the condition is an ordinary query
term, so it is arguable and another author can write a different one.
`install(..., gated=False)` is the control — with the diagnosis dropped, the repair
fires on CORRECT code too, and `test_repair.py` measures exactly that.

## ⚠⚠ CONSUMING THE OCCASION NEEDS A DURABLE MARK HERE, AND ON ugm IT DID NOT

`repair.ugm` had each family deny its own `unmet` — `-unmet(...)` — and that was
enough, because the chain was append-only and nothing re-derived the occasion once
it was withdrawn. **A system re-runs every tick.** So a repair that only denied
`unmet` would have it re-asserted by `diagnose` on the very next pass — before the
evaluator had re-read the changed structure — and the second family would fire on
the same bug. That is the measured over-repair (`if age >= 17`: two independent
fixes, correct by luck and wrong as a repair) arriving through a new door.

⭐ So a repair asserts `repaired($f, $c)` and `diagnose` asks `without=Repaired`.
The deny stays, because withdrawing the occasion is what a repair MEANS; the mark
is what makes it stick on a floor where every rule is offered again.

⚠ IMAGINATION DERIVES, REALITY EXECUTES — carried over deliberately. What a case
returns is derived from STRUCTURE by `evaluator.evaluate`; running the emitted
source is a separate, independent gate. A repair you evaluate by running it is
checked against the same model that proposed it.
"""
from __future__ import annotations

from .evaluator import evaluate
from .facts import Facts, relation

Function = relation("function")
IfStmt = relation("if_stmt")
Block = relation("block")
Case = relation("case")
Wants = relation("wants")
Evaluate = relation("evaluate")
Repaired = relation("repaired")
Agrees = relation("agrees")
Unmet = relation("unmet")


# -- navigation -----------------------------------------------------------------

def guard(f: Facts):
    """Where the guard is: the comparison a function's first `if` tests.

    Python's vocabulary throughout — this is a reading of code, not a description
    of it.
    """

    def system(world) -> None:
        for function, _ in world.each(Function):
            block = f.one("body", function)
            if block is None:
                continue
            for (statement,) in [row for row in f.of("stmt", block) if len(row) == 1]:
                if not f.has("if_stmt", statement):
                    continue
                condition = f.one("condition", statement)
                if condition is not None and f.has("comparison", condition):
                    f.fact("guard", function, condition)

    return system


def inverses(f: Facts):
    """The inverses the evaluator needs to walk UP.

    ⚠ A proposition relates its members and nothing about it is directional, but a
    component hangs on ONE subject — so *which `if` is this the condition of* is a
    derived claim rather than a second index. That is the substrate's own shape:
    navigation is a claim, not a pointer.
    """

    def system(world) -> None:
        for if_stmt, _ in world.each(IfStmt):
            condition = f.one("condition", if_stmt)
            if condition is not None:
                f.fact("if_stmt_of", condition, if_stmt)
        for block, _ in world.each(Block):
            for row in f.of("stmt", block):
                if len(row) == 1:
                    f.fact("block_of", row[0], block)

    return system


# -- asking and answering -------------------------------------------------------

def ask(f: Facts):
    """Write the request to evaluate a function for a case.

    ⚠ `guard` is a precondition, not decoration: without it this fired BEFORE the
    navigation had found the comparison, the evaluator answered *no guard*, and
    nothing asked again — a request is a fact and a fact is not an event.
    """

    def system(world) -> None:
        for function, _ in world.each(Function):
            if not f.of("guard", function):
                continue
            for case, _ in world.each(Case):
                f.fact("evaluate", function, case)

    return system


def answer(f: Facts):
    """The evaluator, as a system. ⚠ A tool PROPOSES; the apparatus CONCLUDES.

    ⭐ On `ugm` this was bound through `Loader.answerer` — a request relation with a
    Python callable behind it. A system IS that, without the binding: it reads the
    requests and deposits what it derived.

    ⚠ The refusal is DEPOSITED rather than swallowed, so a diagnosis that stays
    unmade can say why. Nothing concludes a value it could not derive.
    """

    def system(world) -> None:
        for function, held in list(world.each(Evaluate)):
            for row in held.rows:
                if len(row) != 1:
                    continue
                case = row[0]
                result = evaluate(f, function, case)
                if result.refused is not None:
                    f.fact("could_not_evaluate", function, case, f.value(result.refused))
                else:
                    # ⚠ `fact`, not `state`: CHANGE then OBSERVE means two
                    # evaluations stand, and the second one is the evidence the
                    # repair worked. Replacing would erase what it is evidence of.
                    f.fact("evaluated", function, case, f.value(result.value))

    return system


def checked(f: Facts):
    """The case is satisfied: what was wanted is what the code does.

    ⚠⚠ THE ORDER THAT WAS LOAD-BEARING ON ugm IS NOT, HERE, AND THAT IS WORTH
    NAMING. `_settle` took the first entry satisfying a subgoal and nothing
    backtracked, so whichever member came first bound `$v` — with `evaluated`
    first, `$v` bound to what the code DOES and the plan reported *your expectation
    is wrong*. Nothing binds here: `wants` is read and `evaluated` is CHECKED
    against it, so the given cannot be revised by a lookup order.
    """

    def system(world) -> None:
        for function, held in world.each(Wants):
            for row in held.rows:
                if len(row) != 2:
                    continue
                case, wanted = row
                if f.holds("evaluated", function, case, wanted):
                    f.fact("agrees", function, case)

    return system


def diagnose(f: Facts):
    """⭐ The occasion a repair acts on: the code was read, and it does not agree.

    See the module note — this is a forward substitute for what backward reading
    produced, and it is narrower than what it replaces.
    """

    def system(world) -> None:
        for function, held in world.each(Wants, without=Repaired):
            for row in held.rows:
                if len(row) != 2:
                    continue
                case, wanted = row
                evaluations = [r for r in f.of("evaluated", function)
                               if len(r) == 2 and r[0] == case]
                if not evaluations:
                    continue                      # nothing read it yet; not a verdict
                if any(r[1] == wanted for r in evaluations):
                    continue                      # it agrees; there is nothing unmet
                f.fact("unmet", function, case, wanted)

    return system


# -- ⭐⭐ the two repair families ------------------------------------------------
#
# Both genuinely fix the bug, which is the point: "found A" must not be read as
# "B is wrong". ⚠ Engine 2 pinned its winner by name and the pin went quietly
# VACUOUS when the tie-break flipped — so a probe derives the rival from the
# outcome instead of naming it.
#
# CHANGE then OBSERVE: each denies the old claim, asserts the new one, and marks
# the occasion consumed. A repair is not done until its effect is observed, and the
# observation is the evaluator running again over the changed structure.

def _occasions(f: Facts, world, gated: bool):
    """The (function, case) pairs a repair may act on.

    ⚠ `gated` is the CONTROL. With the diagnosis dropped, every case is an occasion
    and the repair damages correct code — which is the measurement, not a bug.
    """
    source = Unmet if gated else Wants
    for function, held in world.each(source, without=Repaired):
        for row in held.rows:
            if len(row) == 2:
                # ⚠ The WANTED value travels with the occasion, because withdrawing
                # `unmet` needs the whole row — an earlier version denied
                # `unmet(f, case)` against a row stored as `(case, wanted)`, matched
                # nothing, and left the occasion standing. It happened to stay
                # correct only because `repaired` also guards it, which is exactly
                # the kind of second mechanism that hides a dead first one.
                yield function, row[0], row[1]


def relax(f: Facts, gated: bool = True):
    """`>` was meant to be `>=`. Deny the operator, assert its neighbour."""

    def system(world) -> None:
        for function, case, wanted in list(_occasions(f, world, gated)):
            for (comparison,) in [r for r in f.of("guard", function) if len(r) == 1]:
                if not f.holds("operator", comparison, f.word("gt")):
                    continue
                f.deny("unmet", function, case, wanted)
                f.deny("operator", comparison, f.word("gt"))
                f.fact("operator", comparison, f.word("ge"))
                f.fact("relaxed", comparison)
                f.fact("repaired", function, case)
                return

    return system


def lower(f: Facts, gated: bool = True):
    """The threshold was one too high. Deny the literal, assert its neighbour."""

    def system(world) -> None:
        for function, case, wanted in list(_occasions(f, world, gated)):
            for (comparison,) in [r for r in f.of("guard", function) if len(r) == 1]:
                right = f.one("right", comparison)
                if right is None or not f.holds("literal", right, f.value(18)):
                    continue
                f.deny("unmet", function, case, wanted)
                f.deny("literal", right, f.value(18))
                f.fact("literal", right, f.value(17))
                f.fact("lowered", right)
                f.fact("repaired", function, case)
                return

    return system


#: ⚠ The order is the tie-break, and it is REGISTRATION ORDER — visible, and the
#: only thing deciding which family wins. Engine 2's was buried in a planner.
FAMILIES = {"relax": relax, "lower": lower}


def install(loop, f: Facts, gated: bool = True, families=None) -> None:
    """The diagnosis and the repair, as systems.

    ⚠ Navigation and evaluation are registered BEFORE the repair, so a first tick
    reads the structure and a later one acts on it. The loop reaches the same
    fixpoint either way; the trace is only legible in this order.
    """
    loop.system(guard(f), name="repair.guard")
    loop.system(inverses(f), name="repair.inverses")
    loop.system(ask(f), name="repair.ask")
    loop.system(answer(f), name="repair.answer")
    loop.system(checked(f), name="repair.checked")
    if gated:
        loop.system(diagnose(f), name="repair.diagnose")
    for name, make in FAMILIES.items():
        if families is None or name in families:
            loop.system(make(f, gated), name=f"repair.{name}")
