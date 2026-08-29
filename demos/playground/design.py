"""The composition stage — `grammapy`'s three combinators, as loop rules.

The retired playground resolved every design-time decision through `grammapy`
objects: `Accumulate.check` for the widget set, §12 `resolve` for the screen shape,
`Scope.check` for effect reachability. `grammapy` is gone, and re-deriving it as a
library would have put the design layer back in a place the blocks cannot reach.

⭐⭐ **SO THE CHECKS RUN IN THE SAME WORLD AND THE SAME LOOP AS THE BUSINESS RULES.**
There is one settle from `cart customer_tier premium` all the way to *this design is
admitted*, and a decision is an ordinary entity carrying ordinary components — so
`why` reaches it, the REPL can show it, and a block author can read the outcome in
the same vocabulary they wrote.

## Why these three are rules and the rest of the block is text

`design.cnl` holds everything sayable as `head when body and body`. These three are
not, and each fails for a different reason worth naming:

    Accumulate   pairwise, with an inequality   "two widgets, and NOT the same one"
    resolve      a universal                    "provides EVERY required capability"
    Scope        a negation                     "NO handler covers this signal"

A Horn triple rule has no `not`, no `!=` and no `forall`. Faking any of them in the
authored surface would have meant inventing a syntax whose meaning is a Python
function anyway — so the function is the honest form, and the DATA it reasons over
stays in the block where an author can argue with it.

⚠ **Each rule is idempotent, and on this floor that is what "settles" means.**
Decisions are REPLACED rather than accumulated: a rule that re-resolves the
screen every tick must replace its answer, not attach a second one. `World.attach`/
`.replace` compare before they store, so restating the same verdict does not move
`revision`.

⚠⚠ 2026-08-29: **reads and writes the SAME predicates `business.cnl`/`ux.cnl`/
`textual.cnl`/`bridge.cnl`/`design.cnl` author** (`has_checkout`, `chosen_for`,
`produces`, `admitted_for`, `demands`, `provides`, `is_default`, `placed_for`,
`writes`, `emits`, `handles`, `inside`, ...) — so it shares `cnl.py`'s
`Vocabulary`/`predicate_component` rather than declaring its own fixed
components for them, the same late-bound reason `cnl.py` itself keeps that
machinery. `interferes_with` and `covered`, by contrast, are PURELY this
module's own bookkeeping — no `.cnl` file ever mentions either — so those two
stay ordinary fixed `@dataclass` components, same as `decision`/`point`/
`combinator`/... below, which record what a decision WAS for `brew.py` to
print, in a vocabulary no CNL rule reads either.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from pystrider import cnl
from pystrider.intake import decode_literal, encode_literal

#: The three decision points, in the order the runner prints them.
POINTS = ("widgets", "screen", "effect")


# -- this module's OWN vocabulary: bookkeeping no `.cnl` file ever reads --------

@dataclass(frozen=True)
class Decision:
    pass


@dataclass(frozen=True)
class Point:
    word: str


@dataclass(frozen=True)
class Combinator:
    word: str


@dataclass(frozen=True)
class DecisionValue:
    text: str  # `repr`-encoded -- see `intake.encode_literal`


@dataclass(frozen=True)
class Admitted:
    word: str  # "yes" / "no"


@dataclass(frozen=True)
class Detail:
    text: str  # `repr`-encoded


@dataclass(frozen=True)
class InterferesWith:
    right: int
    slot: int


@dataclass(frozen=True)
class Covered:
    signal: int


# -- reading the world ----------------------------------------------------------

def _cart(v: cnl.Vocabulary) -> Optional[int]:
    """The cart under design. ⚠ Found by what it IS (`has_checkout yes`) rather
    than passed in, so the rules never hold a handle the blocks cannot name."""
    yes = v.known("yes")
    for entity, held in v.world.each(cnl.predicate_component("has_checkout")):
        if yes is not None and held.object == yes:
            return entity.id
    return None


def _subjects_relating_to(v: cnl.Vocabulary, name: str, target: int) -> List[int]:
    """Every `?s <name> <target>` — the join the blocks spell `?s name ?target`."""
    return [e.id for e, held in v.world.each(cnl.predicate_component(name))
            if held.object == target]


def _objects(v: cnl.Vocabulary, name: str, subject: int) -> List[int]:
    return [held.object for held in v.world.get_all(subject, cnl.predicate_component(name))]


def _decide(v: cnl.Vocabulary, point: str, combinator: str, value: str,
            admitted: bool, detail: str = "") -> None:
    """Record one design decision, replacing whatever it said last tick.

    ⚠ The decision entity is INTERNED on its point, so `widgets` is one entity
    across every tick and every re-derivation. Spawning a fresh one per pass would
    move `revision` for ever and the world would never settle — the loop would
    report the design rules as hot and `pystrider.strict.run` would refuse the run.
    """
    d = v.word(f"decision:{point}")
    v.world.attach(d, Decision())
    v.world.replace(d, Point(point))
    v.world.replace(d, Combinator(combinator))
    v.world.replace(d, DecisionValue(encode_literal(value)))
    v.world.replace(d, Admitted("yes" if admitted else "no"))
    v.world.replace(d, Detail(encode_literal(detail)))


def decisions(v: cnl.Vocabulary) -> List[dict]:
    """The decision table, in `POINTS` order, for a caller that wants to print it."""
    out = []
    for point in POINTS:
        d = v.known(f"decision:{point}")
        if d is None or not v.world.has(d, Decision):
            continue
        out.append({
            "point": point,
            "combinator": v.world.get(d, Combinator).word,
            "value": decode_literal(v.world.get(d, DecisionValue).text),
            "admitted": v.world.get(d, Admitted).word == "yes",
            "detail": decode_literal(v.world.get(d, Detail).text),
        })
    return out


def admitted(v: cnl.Vocabulary) -> bool:
    """Whether every decision point resolved. The gate on emitting anything."""
    table = decisions(v)
    return bool(table) and all(d["admitted"] for d in table)


def chosen_screen(v: cnl.Vocabulary) -> Optional[str]:
    cart = _cart(v)
    if cart is None:
        return None
    chosen = _subjects_relating_to(v, "chosen_for", cart)
    return v.text(chosen[0]) if len(chosen) == 1 else None


# -- the three rules --------------------------------------------------------

def resolve_screen(v: cnl.Vocabulary):
    """§12 `resolve`: the screen shape is FORCED by what the admitted features demand.

    ⭐⭐ **THIS IS WHERE THE UX RULE BECOMES A SCREEN.** Nothing here knows what a
    confirmation is. `confirmation_step demands confirmation` is authored in
    `design.cnl`, `confirm_screen provides confirmation` beside it, and the
    obligation that put `confirmation_step` in play came from `ux.cnl`'s deontic
    rule off a business fact. The shape flips because the demand set changed —
    which is the difference between a derived UI and an `if irreversible:`.

    ⚠ It refuses to pick between two candidates rather than taking the first.
    A decision point with two satisfying productions is an UNDERSPECIFIED
    design, and choosing quietly is how a tie-break nobody wrote becomes policy.
    """
    chosen_for = cnl.predicate_component("chosen_for")

    def rule(w) -> None:
        cart = _cart(v)
        if cart is None:
            return
        screen = v.known("screen")
        if screen is None:
            return
        productions = _subjects_relating_to(v, "produces", screen)
        required = {cap for feature in _subjects_relating_to(v, "admitted_for", cart)
                    for cap in _objects(v, "demands", feature)}
        candidates = [p for p in productions
                      if required <= set(_objects(v, "provides", p))]

        default = _subjects_relating_to(v, "is_default", screen)
        if not required and default:
            winner, verdict = default[0], "Defaulted"
        elif len(candidates) == 1:
            winner, verdict = candidates[0], "Forced"
        else:
            winner, verdict = None, ("Ambiguous" if len(candidates) > 1 else "Unresolved")

        for production in productions:
            if production == winner:
                w.attach(production, chosen_for(cart))
            else:
                w.remove(production, chosen_for(cart))

        wanted = ", ".join(sorted(v.text(c) for c in required)) or "nothing"
        _decide(v, "screen", "resolve",
               v.text(winner) if winner is not None else verdict.lower(),
               winner is not None, f"{verdict}; demanded: {wanted}")

    return rule


def check_interference(v: cnl.Vocabulary):
    """`Accumulate`'s frame rule: the placed widgets compose iff their writes are
    pairwise DISJOINT.

    Two widgets claiming one screen slot is a UI that overwrites itself, and it is
    a fact about the widget set rather than about any one widget — so it is only
    visible here, at design time, once the bridge has settled which widgets are
    placed at all.
    """

    def rule(w) -> None:
        cart = _cart(v)
        if cart is None:
            return
        placed = _subjects_relating_to(v, "placed_for", cart)
        clashes = []
        for i, left in enumerate(placed):
            for right in placed[i + 1:]:
                shared = set(_objects(v, "writes", left)) & set(_objects(v, "writes", right))
                for slot in sorted(shared, key=v.text):
                    w.attach(left, InterferesWith(right, slot))
                    clashes.append(f"{v.text(left)} and {v.text(right)} both write "
                                   f"{v.text(slot)}")
        _decide(v, "widgets", "Accumulate",
               f"{len(placed)} placed, writes disjoint" if not clashes
               else f"{len(clashes)} clash(es)",
               not clashes, "; ".join(clashes))

    return rule


def check_coverage(v: cnl.Vocabulary):
    """`Scope`: every emitted control signal must be handled by a node it sits INSIDE.

    ⭐ This is the check that makes the confirm gate a CONSEQUENCE. An irreversible
    checkout emits `needs_confirmation` from its completion leaf (`design.cnl`);
    only `confirm_screen` handles it, and `inside` holds only when that screen was
    the one chosen. So a design that resolved to `one_screen` while the action is
    irreversible is REJECTED here — the app is not emitted, rather than emitted
    without its gate.

    ⚠ The negation is why this is a rule: a triple rule can conclude *covered*,
    but it cannot conclude *nothing covers this*.
    """
    emits = cnl.predicate_component("emits")
    inside = cnl.predicate_component("inside")

    def rule(w) -> None:
        uncovered = []
        seen_emits = False
        for node, held in list(w.each(emits)):
            seen_emits = True
            signal = held.object
            insiders = {x.object for x in w.get_all(node.id, inside)}
            handlers = [h for h in _subjects_relating_to(v, "handles", signal)
                       if h in insiders]
            if handlers:
                w.attach(node.id, Covered(signal))
            else:
                uncovered.append(f"{v.text(node.id)} emits {v.text(signal)}, unhandled")
        _decide(v, "effect", "Scope",
               "no effect" if not uncovered and not seen_emits
               else ("handled" if not uncovered else f"{len(uncovered)} uncovered"),
               not uncovered, "; ".join(uncovered))

    return rule


def install(loop, v: cnl.Vocabulary) -> None:
    """The three checks, as rules on the same loop the CNL rules run on.

    ⚠ Registered AFTER the block rules, so a first tick derives the admitted
    feature set before anything tries to resolve a screen from it. Order is only a
    matter of how many ticks it takes — the loop runs to quiescence either way —
    but reading the trace is much easier when it flows the way the argument does.
    """
    loop.rule(resolve_screen(v), name="design.resolve_screen")
    loop.rule(check_interference(v), name="design.check_interference")
    loop.rule(check_coverage(v), name="design.check_coverage")
