"""`pystrider.symbolic` — the first slice of thread 6 ("mental run" analysis,
`docs/TODO.md`). `fold` is a PURE function (no caching, no world mutation);
`known_value` is a forward, structural ANNOTATION built on top of it
(`patterns.py`'s exact shape: structure => description, deposited as a
component) — not a request/answer pull like `evaluator.evaluate`, and
nothing here is keyed to a `Case`.

⭐ **THE CEILING THIS SLICE DELIBERATELY SITS AT**: constant folding — every
operand traced back to a bare `Constant`, no `Name` (bound or not) anywhere in
the chain. This is the value domain with no unbound symbols and no branches:
the cheapest place to prove the annotation shape (`KnownValue` on an
expression entity) before asking it to reason about what a `Name` is BOUND TO
— which is the actual target this is scaffolding toward (resolving `f()`
through `f = some_function`, to find call sites through indirection). A
`Name` gets no `KnownValue` here, ever; that is next, not this.

⚠⚠ **WHY `fold` IS PURE, AND `known_value` REBUILDS EVERY TICK.** Found
2026-08-31, working through the TMS design (`docs/TODO.md`): `repair.py`'s
`apply` (`relax`/`lower`) mutates a `Comparison`/`Constant` IN PLACE via
`w.replace`, keeping the entity id (rewiring every edge that points at a
fresh id has no cheap answer here — no reverse index). The FIRST version of
this module cached `KnownValue` via `w.attach` gated on `without=KnownValue`
— which, once attached, never reconsidered the entity again, so a `repair`
that changed `18` to `17` left a confidently-wrong `KnownValue("18")`
standing forever. Two fixes, together: `fold` never reads `KnownValue` (it
recomputes from `Constant`/`Arithmetic`/`Comparison`/`Left`/`Right` fresh,
recursing in Python, not across engine ticks — nesting no longer needs one
loop tick per level either, a side benefit), and `known_value` reruns it for
every candidate entity on every tick, `w.replace`-ing (never `w.attach`-ing)
the result — idempotent by `World.replace`'s own dedup, so an unchanged fold
costs nothing once settled, but a CHANGED one is corrected the very next
tick instead of never. See `pystrider.evaluation`'s own module note for the
other half of this fix: a durable receipt is never trusted without
re-deriving through `fold` again first either.

⚠ Abstains the same way every description in this repo does: nothing
asserted where the fold cannot be decided, rather than a guess. Three
distinct reasons to abstain, all silent by construction, none conflated:
an unmodelled operator (`_ARITH`/`_COMPARE` are partial by name, same
posture as `evaluator._DECIDES`), an operand with no fold yet (a `Name`,
or a fold that raises — `ZeroDivisionError` chief among them), or an
operand that is a placeholder (which never carries `Constant`/`Arithmetic`/
`Comparison` at all, so `fold` never reaches a base case for it — no
explicit `Readable` check needed here, unlike `patterns.py`'s three
constructions, because the absence is already structural).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

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
    case, no bound parameter, nothing outside the entity's own subtree. A
    CACHE of `fold`, kept in sync every tick — see the module note on why it
    is `w.replace`d rather than `w.attach`ed. `literal` is `repr`-encoded,
    the same codec as `intake.Constant.literal`.
    """

    literal: str


def fold(w, entity: int) -> Optional[Any]:
    """The value `entity` folds to, decided FRESH from its own current
    components every call — `Constant` trivially, `Arithmetic`/`Comparison`
    by recursing into `Left`/`Right`. `None` wherever the fold cannot be
    decided (see the module note's three-reasons-to-abstain).

    ⚠⚠ Never reads `KnownValue`. That component is a CACHE this function
    feeds (`known_value`, below), never a source this function may lean
    on — the whole point is a caller (`pystrider.evaluation.current`
    chief among them) can trust what THIS returns without first asking
    whether some standing annotation is still in sync with the world.
    """
    if w.has(entity, Constant):
        return decode_literal(w.get(entity, Constant).literal)
    if w.has(entity, Arithmetic):
        return _fold_binary(w, entity, _ARITH.get(w.get(entity, Arithmetic).operator))
    if w.has(entity, Comparison):
        return _fold_binary(w, entity, _COMPARE.get(w.get(entity, Comparison).operator))
    return None


def _fold_binary(w, entity: int, op) -> Optional[Any]:
    if op is None:
        return None
    left, right = w.get(entity, Left), w.get(entity, Right)
    if left is None or right is None:
        return None
    a, b = fold(w, left.entity), fold(w, right.entity)
    if a is None or b is None:
        return None
    try:
        return op(a, b)
    except (ZeroDivisionError, TypeError, ValueError, OverflowError):
        return None


def known_value(w) -> None:
    """`fold` over every `Constant`/`Arithmetic`/`Comparison` entity, kept
    in sync as a standing `KnownValue` — present and correct where `fold`
    decides a value, absent where it does not (a fold that STOPS deciding,
    because something it depended on changed, drops its stale `KnownValue`
    here too, via `w.detach`, not just skips adding a new one).
    """
    for kind in (Constant, Arithmetic, Comparison):
        for entity, _tag in w.each(kind):
            value = fold(w, entity)
            if value is None:
                w.detach(entity, KnownValue)
            else:
                w.replace(entity, KnownValue(encode_literal(value)))


#: ⭐ One entry today, kept as a dict anyway — same reason `patterns.py`'s
#: `DESCRIPTIONS` and `effects.py`'s are, even at one entry: the perturbation
#: pin's `only=` needs a name to select, not a bare function.
DESCRIPTIONS = {"known_value": known_value}


def install(loop, only=None) -> None:
    """Register the descriptions. `only` names a subset, for a control."""
    for name, make in DESCRIPTIONS.items():
        if only is None or name in only:
            loop.rule(make, name=f"symbolic.{name}")
