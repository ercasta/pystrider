"""The composition stage — `grammapy`'s three combinators, as harneskills systems.

The retired playground resolved every design-time decision through `grammapy`
objects: `Accumulate.check` for the widget set, §12 `resolve` for the screen shape,
`Scope.check` for effect reachability. `grammapy` is gone, and re-deriving it as a
library would have put the design layer back in a place the blocks cannot reach.

⭐⭐ **SO THE CHECKS RUN IN THE SAME WORLD AND THE SAME LOOP AS THE BUSINESS RULES.**
There is one settle from `cart customer_tier premium` all the way to *this design is
admitted*, and a decision is an ordinary entity carrying ordinary components — so
`why` reaches it, the REPL can show it, and a block author can read the outcome in
the same vocabulary they wrote.

## Why these three are systems and the rest of the block is text

`design.cnl` holds everything sayable as `head when body and body`. These three are
not, and each fails for a different reason worth naming:

    Accumulate   pairwise, with an inequality   "two widgets, and NOT the same one"
    resolve      a universal                    "provides EVERY required capability"
    Scope        a negation                     "NO handler covers this signal"

A Horn triple rule has no `not`, no `!=` and no `forall`. Faking any of them in the
authored surface would have meant inventing a syntax whose meaning is a Python
function anyway — so the function is the honest form, and the DATA it reasons over
stays in the block where an author can argue with it.

⚠ **Each system is idempotent, and on this floor that is what "settles" means.**
Decisions are `state()`d rather than `fact()`ed: a system that re-resolves the
screen every tick must replace its answer, not accumulate two. `World.attach`
compares before it stores, so restating the same verdict does not move `revision`.
"""
from __future__ import annotations

from typing import List, Optional

from harneskills.world import Entity

from pystrider.facts import Facts, relation

#: The three decision points, in the order the runner prints them.
POINTS = ("widgets", "screen", "effect")


# -- reading the world ----------------------------------------------------------

def _cart(f: Facts) -> Optional[Entity]:
    """The cart under design. ⚠ Found by what it IS (`has_checkout yes`) rather
    than passed in, so the systems never hold a handle the blocks cannot name."""
    yes = f.known("yes")
    for entity, held in f.world.each(relation("has_checkout")):
        if yes is not None and (yes,) in held.rows:
            return entity
    return None


def _subjects_relating_to(f: Facts, name: str, target: Entity) -> List[Entity]:
    """Every `?s <name> <target>` — the join the blocks spell `?s name ?target`."""
    return [e for e, held in f.world.each(relation(name)) if (target,) in held.rows]


def _objects(f: Facts, name: str, subject: Entity) -> List[Entity]:
    return [row[0] for row in f.of(name, subject) if len(row) == 1]


def _decide(f: Facts, point: str, combinator: str, value: str,
            admitted: bool, detail: str = "") -> None:
    """Record one design decision, replacing whatever it said last tick.

    ⚠ The decision entity is INTERNED on its point, so `widgets` is one entity
    across every tick and every re-derivation. Spawning a fresh one per pass would
    move `revision` for ever and the world would never settle — the loop would
    report the design systems as hot and `Facts.run` would refuse the run.
    """
    d = f.word(f"decision:{point}")
    f.fact("decision", d)
    f.state("point", d, f.word(point))
    f.state("combinator", d, f.word(combinator))
    f.state("value", d, f.value(value))
    f.state("admitted", d, f.word("yes" if admitted else "no"))
    f.state("detail", d, f.value(detail))


def decisions(f: Facts) -> List[dict]:
    """The decision table, in `POINTS` order, for a caller that wants to print it."""
    out = []
    for point in POINTS:
        d = f.known(f"decision:{point}")
        if d is None or not f.has("decision", d):
            continue
        out.append({
            "point": point,
            "combinator": f.text("combinator", d),
            "value": f.literal("value", d),
            "admitted": f.text("admitted", d) == "yes",
            "detail": f.literal("detail", d),
        })
    return out


def admitted(f: Facts) -> bool:
    """Whether every decision point resolved. The gate on emitting anything."""
    table = decisions(f)
    return bool(table) and all(d["admitted"] for d in table)


def chosen_screen(f: Facts) -> Optional[str]:
    cart = _cart(f)
    if cart is None:
        return None
    chosen = _subjects_relating_to(f, "chosen_for", cart)
    return f.show(chosen[0]) if len(chosen) == 1 else None


# -- the three systems ----------------------------------------------------------

def resolve_screen(f: Facts):
    """§12 `resolve`: the screen shape is FORCED by what the admitted features demand.

    ⭐⭐ **THIS IS WHERE THE UX RULE BECOMES A SCREEN.** Nothing here knows what a
    confirmation is. `confirmation_step demands confirmation` is authored in
    `design.cnl`, `confirm_screen provides confirmation` beside it, and the
    obligation that put `confirmation_step` in play came from `ux.cnl`'s deontic
    rule off a business fact. The shape flips because the demand set changed —
    which is the difference between a derived UI and an `if irreversible:`.

    ⚠ It refuses to pick between two candidates rather than taking the first.
    `one()`'s lesson, in the design layer: a decision point with two satisfying
    productions is an UNDERSPECIFIED design, and choosing quietly is how a
    tie-break nobody wrote becomes policy.
    """

    def system(world) -> None:
        cart = _cart(f)
        if cart is None:
            return
        screen = f.known("screen")
        if screen is None:
            return
        productions = _subjects_relating_to(f, "produces", screen)
        required = {cap for feature in _subjects_relating_to(f, "admitted_for", cart)
                    for cap in _objects(f, "demands", feature)}
        candidates = [p for p in productions
                      if required <= set(_objects(f, "provides", p))]

        default = _subjects_relating_to(f, "is_default", screen)
        if not required and default:
            winner, verdict = default[0], "Defaulted"
        elif len(candidates) == 1:
            winner, verdict = candidates[0], "Forced"
        else:
            winner, verdict = None, ("Ambiguous" if len(candidates) > 1 else "Unresolved")

        for production in productions:
            if production == winner:
                f.fact("chosen_for", production, cart)
            else:
                f.deny("chosen_for", production, cart)

        wanted = ", ".join(sorted(f.show(c) for c in required)) or "nothing"
        _decide(f, "screen", "resolve",
                f.show(winner) if winner is not None else verdict.lower(),
                winner is not None, f"{verdict}; demanded: {wanted}")

    return system


def check_interference(f: Facts):
    """`Accumulate`'s frame rule: the placed widgets compose iff their writes are
    pairwise DISJOINT.

    Two widgets claiming one screen slot is a UI that overwrites itself, and it is
    a fact about the widget set rather than about any one widget — so it is only
    visible here, at design time, once the bridge has settled which widgets are
    placed at all.
    """

    def system(world) -> None:
        cart = _cart(f)
        if cart is None:
            return
        placed = _subjects_relating_to(f, "placed_for", cart)
        clashes = []
        for i, left in enumerate(placed):
            for right in placed[i + 1:]:
                shared = set(_objects(f, "writes", left)) & set(_objects(f, "writes", right))
                for slot in sorted(shared, key=f.show):
                    f.fact("interferes_with", left, right, slot)
                    clashes.append(f"{f.show(left)} and {f.show(right)} both write "
                                   f"{f.show(slot)}")
        _decide(f, "widgets", "Accumulate",
                f"{len(placed)} placed, writes disjoint" if not clashes
                else f"{len(clashes)} clash(es)",
                not clashes, "; ".join(clashes))

    return system


def check_coverage(f: Facts):
    """`Scope`: every emitted control signal must be handled by a node it sits INSIDE.

    ⭐ This is the check that makes the confirm gate a CONSEQUENCE. An irreversible
    checkout emits `needs_confirmation` from its completion leaf (`design.cnl`);
    only `confirm_screen` handles it, and `inside` holds only when that screen was
    the one chosen. So a design that resolved to `one_screen` while the action is
    irreversible is REJECTED here — the app is not emitted, rather than emitted
    without its gate.

    ⚠ The negation is why this is a system: a triple rule can conclude *covered*,
    but it cannot conclude *nothing covers this*.
    """

    def system(world) -> None:
        uncovered = []
        for node, held in list(f.world.each(relation("emits"))):
            for row in held.rows:
                if len(row) != 1:
                    continue
                signal = row[0]
                handlers = [h for h in _subjects_relating_to(f, "handles", signal)
                            if f.holds("inside", node, h)]
                if handlers:
                    f.fact("covered", node, signal)
                else:
                    uncovered.append(f"{f.show(node)} emits {f.show(signal)}, unhandled")
        _decide(f, "effect", "Scope",
                "no effect" if not uncovered and not f.subjects("emits")
                else ("handled" if not uncovered else f"{len(uncovered)} uncovered"),
                not uncovered, "; ".join(uncovered))

    return system


def install(loop, f: Facts) -> None:
    """The three checks, as systems on the same loop the CNL rules run on.

    ⚠ Registered AFTER the block rules, so a first tick derives the admitted
    feature set before anything tries to resolve a screen from it. Order is only a
    matter of how many ticks it takes — the loop runs to quiescence either way —
    but reading the trace is much easier when it flows the way the argument does.
    """
    loop.system(resolve_screen(f), name="design.resolve_screen")
    loop.system(check_interference(f), name="design.check_interference")
    loop.system(check_coverage(f), name="design.check_coverage")
