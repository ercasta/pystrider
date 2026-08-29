"""Effects — annotating a function with what it DOES to the world outside its
own return value, forward-derived off structure `intake.py` already produced.

⭐ This is `patterns.py`'s recipe, not a new mechanism: `iteration` reads
`ForStmt`/`Target`/`Iterated`/`Body` and abstains via `Readable`; `effect`
below reads `Assign`/`Attribute`/`Call` the same way, and abstains the same
way. It is the half of the original bet that survived every substrate change
intact — forward, structure to description — so it costs nothing new here.

⚠⚠ WHAT `effect` DOES NOT CLAIM. A function whose syntax contains no mutation
or call intake recognizes is silent, not certified pure — `Readable`/`Partial`
already say when a part could not be read at all, and `patterns.application`'s
own `Applies` gates on `Readable` for exactly this reason. `effect` inherits
the same honesty by construction: it never asserts from a placeholder.

⭐⭐ TRANSITIVITY IS THE FREE PART. Propagating an effect across a call graph
(`outer` calls `inner`, `inner` writes, so `outer` writes) is not new
machinery either — it is one more forward rule reading `Effect` and
`Contains`/`Call` at a fixpoint, the same fixpoint `patterns.py`'s
descriptions already settle on. This is the argument for building semantic
annotation on the ECS at all: propagation is a query, not a walk this module
has to write.

⚠ WHAT THIS MODULE DOES NOT DO: write code FROM a wanted effect. That is the
other half of the bet — gone, not parked, because a Python rule has no
antecedent to read backwards. See `effects_repair.py` for the shape a
write-from-intent loop takes here instead: not backward reasoning, an
authored, effect-indexed family of forward repairs, each gated on `wants`
and not yet `has`.
"""
from __future__ import annotations

from dataclasses import dataclass

from .intake import (Assign, Assigned, Attribute, Body, Call, Callee,
                     Function, Name, Otherwise, Readable, Stmt, Then)

#: Known effectful callees, by their structural reading. ⚠ A REGISTRY, not an
#: inference — that `open` performs I/O is knowledge about the standard
#: library, not something the syntax alone reveals.
IO_NAMES = {"print", "open", "input"}
IO_ATTRS = {"write", "read", "append", "close", "send", "recv"}

#: Part labels a function's own reach walks through, one hop per tick, to
#: find everything nested in a `for`/`if` without re-walking blocks itself.
_NESTING = (Stmt, Then, Otherwise, Body)


@dataclass(frozen=True)
class Contains:
    """`function` CONTAINS this entity, reached through its own `Body` and
    the ordinary block-nesting labels. Multi-valued — one row per member."""

    entity: int


@dataclass(frozen=True)
class Effect:
    """`function` has this effect — `Effect("mutates", "dirty")`,
    `Effect("io", "print")`. Multi-valued — a function may have several."""

    kind: str
    detail: str


# -- navigation: which function a nested statement belongs to --------------------

def contains(w) -> None:
    """`function` CONTAINS every node reachable through its own `Body` and
    the ordinary block-nesting labels, computed as a fixpoint: one hop
    attached per tick, the loop settling once nothing new is reachable —
    the same shape `patterns.py`'s descriptions settle in, applied to
    reachability instead of recognition.
    """
    for function, _tag in w.each(Function):
        body = w.get(function, Body)
        if body is not None:
            w.attach(function, Contains(body.entity))
    for function, containment in list(w.each(Contains)):
        member = containment.entity
        for label in _NESTING:
            for part in w.get_all(member, label):
                w.attach(function, Contains(part.entity))


# -- descriptions: structure => effect -------------------------------------------

def mutates_attribute(w) -> None:
    """`obj.attr = ...` anywhere in a function -> the function MUTATES that attr.

    ⚠ Attributed via `Contains`, not by reading `Function`'s own `Body`
    directly — an assignment three `if`s deep is still the function's, and
    `Contains` is what makes that reachable without this rule re-walking
    blocks itself.
    """
    for function, containment in w.each(Contains):
        member = containment.entity
        if not w.has(member, Assign):
            continue
        for assigned in w.get_all(member, Assigned):
            target = assigned.entity
            if not w.has(target, Attribute) or not w.has(target, Readable):
                continue
            attr = w.get(target, Attribute)
            if attr is not None:
                w.attach(function, Effect("mutates", attr.attr))


def calls_effectful(w) -> None:
    """A call to a known I/O name or method anywhere in a function -> an `io` effect."""
    for function, containment in w.each(Contains):
        member = containment.entity
        if not w.has(member, Call):
            continue
        callee_part = w.get(member, Callee)
        if callee_part is None or not w.has(callee_part.entity, Readable):
            continue
        callee = callee_part.entity
        kind = None
        if w.has(callee, Name):
            name = w.get(callee, Name).id
            if name in IO_NAMES:
                kind = name
        elif w.has(callee, Attribute):
            attr = w.get(callee, Attribute).attr
            if attr in IO_ATTRS:
                kind = attr
        if kind is not None:
            w.attach(function, Effect("io", kind))


def transitive(w) -> None:
    """`outer` calls `inner` (by name, in this module) and `inner` HAS an
    effect -> `outer` has it too.

    ⭐⭐ The point of the exercise: this is not new propagation machinery, it is
    another rule reading `Effect`/`Contains`/`Call` at the same fixpoint
    everything else settles on. A call graph five deep needs no more code
    than a call graph one deep — the loop just runs a few more ticks.
    """
    by_name = {}
    for function, fn in w.each(Function):
        by_name[fn.name] = function
    for function, containment in w.each(Contains):
        member = containment.entity
        if not w.has(member, Call):
            continue
        callee_part = w.get(member, Callee)
        if callee_part is None or not w.has(callee_part.entity, Name):
            continue
        callee_name = w.get(callee_part.entity, Name).id
        target = by_name.get(callee_name)
        if target is None or target.id == function.id:
            continue
        for effect in w.get_all(target, Effect):
            w.attach(function, effect)


#: ⭐ The descriptions, in one place, so a caller can install a SUBSET — the
#: same knob `patterns.py` offers, for the same reason: proving which
#: description a given effect depends on.
DESCRIPTIONS = {"contains": contains, "mutates_attribute": mutates_attribute,
                "calls_effectful": calls_effectful, "transitive": transitive}


def install(loop, only=None) -> None:
    """Register the descriptions. `only` names a subset, for a control."""
    for name, make in DESCRIPTIONS.items():
        if only is None or name in only:
            loop.rule(make, name=f"effects.{name}")
