"""Effects — annotating a function with what it DOES to the world outside its
own return value, forward-derived off structure `intake.py` already produced.

⭐ This is `patterns.py`'s recipe, not a new mechanism: `iteration` reads
`for_stmt`/`target`/`iterated`/`body` and abstains via `readable`; `effect`
below reads `assign`/`attribute`/`call` the same way, and abstains the same
way. It is the half of the ugm→harneskills bet that survived intact — forward,
structure to description — so it costs nothing new to the substrate.

⚠⚠ WHAT `effect` DOES NOT CLAIM. A function whose syntax contains no mutation
or call intake recognizes is silent, not certified pure — `readable`/`partial`
already say when a part could not be read at all, and `application`'s own
`applies` gate on `readable` for exactly this reason. `effect` inherits the
same honesty by construction: it never asserts from a placeholder.

⭐⭐ TRANSITIVITY IS THE FREE PART. Propagating an effect across a call graph
(`outer` calls `inner`, `inner` writes, so `outer` writes) is not new
machinery either — it is one more forward system reading `effect` and
`contains`/`call` at a fixpoint, the same fixpoint `patterns.py`'s
descriptions already settle on. This is the argument for building semantic
annotation on the ECS at all: propagation is a query, not a walk this module
has to write.

⚠ WHAT THIS MODULE DOES NOT DO: write code FROM a wanted effect. That is the
other half of the bet — the one `facts.py`'s module note says is gone, not
parked, because a Python system has no antecedent to read backwards. See
`repair.py` for the shape a write-from-intent loop takes here instead: not
backward reasoning, an authored, effect-indexed family of forward repairs,
each gated on `wants` and not yet `has`.
"""
from __future__ import annotations

from ugm.facts import Facts, relation

Function = relation("function")
Contains = relation("contains")
Effect = relation("effect")

#: Known effectful callees, by their structural reading. ⚠ A REGISTRY, not an
#: inference — that `open` performs I/O is knowledge about the standard
#: library, not something the syntax alone reveals.
IO_NAMES = {"print", "open", "input"}
IO_ATTRS = {"write", "read", "append", "close", "send", "recv"}


# -- navigation: which function a nested statement belongs to --------------------

def contains(f: Facts):
    """`function` CONTAINS every node reachable through its own `body` and
    the ordinary block-nesting labels, computed as a fixpoint: one hop
    asserted per tick, the loop settling once nothing new is reachable —
    the same shape `patterns.py`'s descriptions settle in, applied to
    reachability instead of recognition.
    """

    def system(world) -> None:
        for function, _ in world.each(Function):
            body = f.one("body", function)
            if body is not None and not f.holds("contains", function, body):
                f.fact("contains", function, body)
        for function, held in list(world.each(Contains)):
            for (member,) in [r for r in held.rows if len(r) == 1]:
                for label in ("stmt", "then", "otherwise", "body"):
                    for row in f.of(label, member):
                        if len(row) != 1:
                            continue
                        child = row[0]
                        if not f.holds("contains", function, child):
                            f.fact("contains", function, child)

    return system


# -- descriptions: structure => effect -------------------------------------------

def mutates_attribute(f: Facts):
    """`obj.attr = ...` anywhere in a function -> the function MUTATES that attr.

    ⚠ Attributed via `contains`, not by reading `Function.body` directly — an
    assignment three `if`s deep is still the function's, and `contains` is
    what makes that reachable without this system re-walking blocks itself.
    """

    def system(world) -> None:
        for function, held in world.each(Contains):
            for (member,) in [r for r in held.rows if len(r) == 1]:
                if not f.has("assign", member):
                    continue
                for row in f.of("assigned", member):
                    if len(row) != 1:
                        continue
                    target = row[0]
                    if not f.has("attribute", target) or not f.has("readable", target):
                        continue
                    attr = f.one("attr", target)
                    if attr is not None and not f.holds("effect", function, f.word("mutates"), attr):
                        f.fact("effect", function, f.word("mutates"), attr)

    return system


def calls_effectful(f: Facts):
    """A call to a known I/O name or method anywhere in a function -> an `io` effect."""

    def system(world) -> None:
        for function, held in world.each(Contains):
            for (member,) in [r for r in held.rows if len(r) == 1]:
                if not f.has("call", member):
                    continue
                callee = f.one("callee", member)
                if callee is None or not f.has("readable", callee):
                    continue
                kind = None
                if f.has("name", callee):
                    name = f.text("id", callee)
                    if name in IO_NAMES:
                        kind = name
                elif f.has("attribute", callee):
                    attr = f.text("attr", callee)
                    if attr in IO_ATTRS:
                        kind = attr
                if kind is not None and not f.holds("effect", function, f.word("io"), f.word(kind)):
                    f.fact("effect", function, f.word("io"), f.word(kind))

    return system


def transitive(f: Facts):
    """`outer` calls `inner` (by name, in this module) and `inner` HAS an
    effect -> `outer` has it too.

    ⭐⭐ The point of the exercise: this is not new propagation machinery, it is
    another system reading `effect`/`contains`/`call` at the same fixpoint
    everything else settles on. A call graph five deep needs no more code
    than a call graph one deep — the loop just runs a few more ticks.
    """

    def system(world) -> None:
        by_name = {}
        for function, _ in world.each(Function):
            called = f.text("name", function)
            if called is not None:
                by_name[called] = function
        for function, held in world.each(Contains):
            for (member,) in [r for r in held.rows if len(r) == 1]:
                if not f.has("call", member):
                    continue
                callee = f.one("callee", member)
                if callee is None or not f.has("name", callee):
                    continue
                target = by_name.get(f.text("id", callee))
                if target is None or target == function:
                    continue
                for row in f.of("effect", target):
                    if not f.holds("effect", function, *row):
                        f.fact("effect", function, *row)

    return system


#: ⭐ The descriptions, in one place, so a caller can install a SUBSET — the
#: same knob `patterns.py` offers, for the same reason: proving which
#: description a given effect depends on.
DESCRIPTIONS = {"contains": contains, "mutates_attribute": mutates_attribute,
                "calls_effectful": calls_effectful, "transitive": transitive}


def install(loop, f: Facts, only=None) -> None:
    """Register the descriptions. `only` names a subset, for a control."""
    for name, make in DESCRIPTIONS.items():
        if only is None or name in only:
            f.system(make(f), name=f"effects.{name}")
