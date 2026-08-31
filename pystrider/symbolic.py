"""`pystrider.symbolic` — the first slice of thread 6 ("mental run" analysis,
`docs/TODO.md`). An ANNOTATION, `patterns.py`'s exact shape (structure =>
description, forward-chained, deposited as a component), not a request/answer
pull like `evaluator.evaluate` — nothing here is keyed to a `Case`, and nothing
needs one to run.

⭐ **THE CEILING THIS SLICE DELIBERATELY SITS AT**: constant folding — every
operand traced back to a bare `Constant`, no `Name` (bound or not) anywhere in
the chain. This is the value domain with no unbound symbols and no branches:
the cheapest place to prove the annotation shape (`KnownValue` on an
expression entity) before asking it to reason about what a `Name` is BOUND TO
— which is the actual target this is scaffolding toward (resolving `f()`
through `f = some_function`, to find call sites through indirection). A
`Name` gets no `KnownValue` here, ever; that is next, not this.

⚠ Abstains the same way every description in this repo does: nothing
asserted where the fold cannot be decided, rather than a guess. Three
distinct reasons to abstain, all silent by construction, none conflated:
an unmodelled operator (`_ARITH`/`_COMPARE` are partial by name, same
posture as `evaluator._DECIDES`), an operand with no `KnownValue` yet (a
`Name`, or a fold that raises — `ZeroDivisionError` chief among them), or an
operand that is a placeholder (which never carries `Constant`/`Arithmetic`/
`Comparison` at all, so it can never reach a `KnownValue` in the first
place — no explicit `Readable` check needed here, unlike `patterns.py`'s
three constructions, because the absence is already structural).
"""
from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import transient
from pystrider.intake import (Arithmetic, Comparison, Constant, Left, Right,
                              decode_literal, encode_literal)

#: Foldable arithmetic operators. ⚠ `matmul` is deliberately absent — `@` has
#: no meaning over Python's own literal types, so there is nothing honest to
#: fold it to; an unmodelled operator here is refused by name, same posture
#: as `evaluator._DECIDES`'s own membrane.
_ARITH = {
    "add": lambda a, b: a + b, "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b, "div": lambda a, b: a / b,
    "floordiv": lambda a, b: a // b, "mod": lambda a, b: a % b,
    "pow": lambda a, b: a ** b, "bitor": lambda a, b: a | b,
    "bitand": lambda a, b: a & b, "bitxor": lambda a, b: a ^ b,
    "lshift": lambda a, b: a << b, "rshift": lambda a, b: a >> b,
}

#: Foldable comparison operators. ⚠ `is`/`is_not`/`in`/`not_in` are
#: deliberately absent — identity and containment are not decidable from two
#: literal VALUES alone (CPython's small-int/string interning makes `is`
#: over literals a fact about the interpreter, not the code), so folding them
#: here would be confidently wrong the way an earlier evaluator's fall-through
#: was (see `evaluator.py`'s own ⚠⚠⚠). Refused by name, not guessed.
_COMPARE = {
    "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b, "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b, "ge": lambda a, b: a >= b,
}


@transient
@dataclass(frozen=True)
class KnownValue:
    """This expression entity's value is decidable from STRUCTURE ALONE — no
    case, no bound parameter, nothing outside the entity's own subtree.
    `literal` is `repr`-encoded, the same codec as `intake.Constant.literal`
    (`encode_literal`/`decode_literal`) — a `KnownValue` is meant to sit
    beside a `Constant` in every way a later reader cares about, including
    how its payload travels.
    """

    literal: str


def known_value(w) -> None:
    """`Constant`  ->  its own literal, trivially. `Arithmetic`/`Comparison`
    whose LEFT and RIGHT both already carry `KnownValue`  ->  the folded
    result. A fixpoint, like every other description here — a doubly-nested
    expression (`(2 + 3) * 4`) needs one tick per nesting level, the loop
    settling once nothing new folds.
    """
    for entity, constant in w.each(Constant, without=KnownValue):
        w.attach(entity, KnownValue(constant.literal))

    for entity, arithmetic, left, right in w.each(
            Arithmetic, Left, Right, without=KnownValue):
        fold = _ARITH.get(arithmetic.operator)
        if fold is None:
            continue
        a = w.get(left.entity, KnownValue)
        b = w.get(right.entity, KnownValue)
        if a is None or b is None:
            continue
        try:
            value = fold(decode_literal(a.literal), decode_literal(b.literal))
        except (ZeroDivisionError, TypeError, ValueError, OverflowError):
            continue
        w.attach(entity, KnownValue(encode_literal(value)))

    for entity, comparison, left, right in w.each(
            Comparison, Left, Right, without=KnownValue):
        decide = _COMPARE.get(comparison.operator)
        if decide is None:
            continue
        a = w.get(left.entity, KnownValue)
        b = w.get(right.entity, KnownValue)
        if a is None or b is None:
            continue
        try:
            value = decide(decode_literal(a.literal), decode_literal(b.literal))
        except TypeError:
            continue
        w.attach(entity, KnownValue(encode_literal(value)))


#: ⭐ One entry today, kept as a dict anyway — same reason `patterns.py`'s
#: `DESCRIPTIONS` and `effects.py`'s are, even at one entry: the perturbation
#: pin's `only=` needs a name to select, not a bare function.
DESCRIPTIONS = {"known_value": known_value}


def install(loop, only=None) -> None:
    """Register the descriptions. `only` names a subset, for a control."""
    for name, make in DESCRIPTIONS.items():
        if only is None or name in only:
            loop.rule(make, name=f"symbolic.{name}")
