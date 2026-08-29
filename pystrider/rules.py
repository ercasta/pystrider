"""Three shapes a rule can have, and only one of them can spend the machine.

⚠⚠ WHY THIS EXISTS. `plan.lower` did not settle, and the reason was not a typo:
its edit did not falsify its own precondition, so it re-fired on its own output
and minted 18, 17, 16, 15 … one function per tick until the OOM killer took the
box. Nothing in the way that rule was WRITTEN distinguished it from a rule that
cannot do this. Both were `def rule(world)` with a loop in it, and the only
thing standing between the two was the author's attention — and the whole point
of this vocabulary is that there will be far more than one such rule.

⭐ So the classification is by what a rule is ALLOWED TO DO, and it is enforced
rather than documented, because a discipline that is merely documented is one
somebody skips and the skipping is silent:

| shape     | may read | may attach | may retract | may INVENT | terminates |
|-----------|----------|-------------|-------------|------------|------------|
| `derive`  | yes      | yes         | no          | no         | ALWAYS     |
| `assign`  | yes      | yes         | its own key | no         | if values settle |
| `minting` | yes      | yes         | no          | ONCE per key | by the key |

`derive` cannot diverge and the argument is short: over a FIXED set of entities
the space of possible components is finite, and a rule that only ever attaches
is monotone, so the fixpoint is bounded by that space. Both halves matter — take
away "fixed" (let it invent) or "only ever attaches" (let it retract) and the
argument is gone. That is exactly why those two are the powers this module takes
away, and why taking them away is worth a module.

⚠⚠ 2026-08-29: **generalized over component TYPES, not relation-name strings.**
`loopingrules` deleted `Facts`/`arbitration.py`, so there is no longer a shared
adapter to take powers away from — the powers this module restricts are now
`World`'s own `spawn`/`detach`/`remove`/`destroy`, and `over`/`say`/`do` all
speak in component classes and instances rather than relation names and rows.
Only `plan.py` uses this module; nobody else in this package needed the
discipline generalized past a single relation before now.
"""
from __future__ import annotations

import dataclasses
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Enacted:
    """What a `minting` rule has already done. ⭐ One component type for every
    such rule, keyed by whatever that rule calls its occasion — `plan.py`
    wrote this by hand as `Enacted(occasion, scenario)` and it is the same
    thing, generalized to however many key elements follow the subject."""

    rest: Tuple[int, ...]


def _claims(said):
    """`say` may answer nothing, one claim, or several.

    A claim is `(entity, component_instance)`. One claim is a 2-tuple whose
    second element is a dataclass INSTANCE (not itself an iterable of
    claims) — that is the one thing that tells "one claim" apart from "many".
    """
    if said is None:
        return ()
    if isinstance(said, tuple) and len(said) == 2 and dataclasses.is_dataclass(said[1]) \
            and not isinstance(said[1], type):
        return (said,)
    return said


@contextmanager
def _without(w, *powers: str):
    """Take named methods off this `World` for the duration of one rule.

    ⚠ Instance attributes shadowing bound methods, which is blunt, and it is the
    right bluntness: the loop runs one rule at a time, so the window is exactly
    the rule's own body, and a rule that reaches for a power it declared it would
    not use gets an exception naming the power — not a quiet divergence twenty
    ticks later with nothing pointing at the cause.
    """
    saved = {}
    for power in powers:
        saved[power] = getattr(w, power)

        def refuse(*_a, _power=power, **_kw):
            raise RuntimeError(
                f"a `derive` rule called `{_power}()` — a rule that only READS and "
                f"ATTACHES is the one shape that cannot diverge, and it stops being "
                f"that the moment it {'invents an entity' if _power == 'spawn' else 'retracts one'}. "
                f"Use `minting` (which needs a key) or `assign` (which owns one component type)."
            )

        setattr(w, power, refuse)
    try:
        yield
    finally:
        for power, original in saved.items():
            setattr(w, power, original)


def derive(over: type, say):
    """Read components, attach components, over entities that already exist.
    Cannot diverge.

    `say(w, subject, component)` answers a claim `(entity, new_component)`, or
    an iterable of them, or `None` for "nothing to say about this one".
    """

    def rule(w) -> None:
        with _without(w, "spawn", "detach", "remove", "destroy"):
            for entity, component in w.each(over):
                for claim in _claims(say(w, entity.id, component)):
                    w.attach(*claim)

    return rule


def assign(w, subject, component_type: type, new_instance, key=lambda c: c) -> None:
    """Attach `new_instance` as the ONE component of its key group on
    `subject`, retracting any stale sibling with the same key but a
    different value.

    ⭐ The single-valued update, which `plan.py` hand-rolled twice and slightly
    differently each time (`_redenote` on `Denotes`, `_move_current` on
    `Current`). A rule that only ever attaches a new answer leaves the old one
    standing beside it, and then a reader expecting one has two — the failure
    is a reader's, far from the writer that caused it.

    `key(instance)` says which of `new_instance`'s fields form the key; the
    rest is the value. `Denotes(scenario, entity)` keyed on `scenario` is
    `key=lambda d: d.scenario`.
    """
    new_key = key(new_instance)
    for old in list(w.get_all(subject, component_type)):
        if key(old) == new_key and old != new_instance:
            w.remove(subject, old)
    w.attach(subject, new_instance)


def fired(w, *key: int) -> bool:
    """Has the minting rule for this occasion already run? See `minting`."""
    subject, rest = key[0], tuple(key[1:])
    return Enacted(rest) in w.get_all(subject, Enacted)


def minting(over: type, once_per, do):
    """A rule that INVENTS entities — at most once per key, and the key is required.

    ⚠⚠ **The key is the termination argument, and there is no version of this
    without one.** A minting rule cannot be trusted to stop itself: whether its
    own output re-satisfies its trigger is a property of the edit, not of the
    rule — `plan.lower` versus `plan.relax` is the whole lesson: `gt`→`ge`
    happens to falsify `operator == gt`, so `relax` terminated by LUCK, while
    `lower` left a literal where it found one and did not. So the bound is
    stated where it can be checked instead of inferred: `once_per` names the
    occasion, and this fires for each one exactly once, ever.

    `do(w, subject, component, key=key)` returns `False` to decline (nothing
    minted, the key stays open — a rule may not APPLY yet and must be free to
    say so), or anything else to mean it acted, which spends the key for good.
    """

    def rule(w) -> None:
        for entity, component in list(w.each(over)):
            for key in once_per(w, entity.id, component) or ():
                if fired(w, *key):
                    continue
                if do(w, entity.id, component, key=key) is not False:
                    subject, rest = key[0], tuple(key[1:])
                    w.attach(subject, Enacted(rest))

    return rule
