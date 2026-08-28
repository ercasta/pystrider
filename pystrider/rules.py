"""Three shapes a rule can have, and only one of them can spend the machine.

⚠⚠ WHY THIS EXISTS. `plan.lower` did not settle, and the reason was not a typo:
its edit did not falsify its own precondition, so it re-fired on its own output
and minted 18, 17, 16, 15 … one function per tick until the OOM killer took the
box. Nothing in the way that rule was WRITTEN distinguished it from a rule that
cannot do this. Both were `def system(world)` with a loop in it, and the only
thing standing between the two was the author's attention — 21 systems today,
and the whole point of the vocabulary is that there will be far more.

⭐ So the classification is by what a rule is ALLOWED TO DO, and it is enforced
rather than documented, because a discipline that is merely documented is one
somebody skips and the skipping is silent:

| shape     | may read | may deposit | may retract | may INVENT | terminates |
|-----------|----------|-------------|-------------|------------|------------|
| `derive`  | yes      | yes         | no          | no         | ALWAYS     |
| `assign`  | yes      | yes         | its own key | no         | if values settle |
| `minting` | yes      | yes         | no          | ONCE per key | by the key |

`derive` cannot diverge and the argument is short: over a FIXED set of entities
the space of possible facts is finite, and a rule that only ever adds to it is
monotone, so the fixpoint is bounded by that space. Both halves matter — take
away "fixed" (let it invent) or "only ever adds" (let it retract) and the
argument is gone. That is exactly why those two are the powers this module takes
away, and why taking them away is worth a module.

⚠ `word()` and `value()` stay available inside a `derive`. They intern a
VOCABULARY — a finite set the rules themselves name — not an open universe, and
`known()` already keeps the one door that would make them unbounded. It is
`node()` that invents.
"""
from __future__ import annotations

from contextlib import contextmanager

from ugm.facts import Facts, relation

#: What a `minting` rule has already done. ⭐ One relation for every such rule,
#: keyed by whatever that rule calls its occasion — `plan.py` wrote this by hand
#: as `enacted(occasion, scenario)` and it is the same thing.
Enacted = relation("enacted")
MARK = "enacted"


def _claims(said):
    """`say` may answer nothing, one claim, or several."""
    if said is None:
        return ()
    return (said,) if isinstance(said, tuple) and said and isinstance(said[0], str) else said


@contextmanager
def _without(f: Facts, *powers: str):
    """Take named methods off this `Facts` for the duration of one rule.

    ⚠ Instance attributes shadowing bound methods, which is blunt, and it is the
    right bluntness: the loop runs one system at a time, so the window is exactly
    the rule's own body, and a rule that reaches for a power it declared it would
    not use gets an exception naming the power — not a quiet divergence twenty
    ticks later with nothing pointing at the cause.
    """
    saved = {}
    for power in powers:
        saved[power] = getattr(f, power)

        def refuse(*_a, _power=power, **_kw):
            raise RuntimeError(
                f"a `derive` rule called `{_power}()` — a rule that only READS and "
                f"DEPOSITS is the one shape that cannot diverge, and it stops being "
                f"that the moment it {'invents an entity' if _power == 'node' else 'retracts one'}. "
                f"Use `minting` (which needs a key) or `assign` (which owns one relation)."
            )

        setattr(f, power, refuse)
    try:
        yield
    finally:
        for power, original in saved.items():
            setattr(f, power, original)


def derive(f: Facts, over, say, *, arity=None, without=()):
    """Read facts, deposit facts, over entities that already exist. Cannot diverge.

    `say(f, subject, *row)` answers a claim `(name, subject, *objects)`, or an
    iterable of them, or None for "nothing to say about this one".
    """

    def system(world) -> None:
        with _without(f, "node", "deny"):
            for subject, held in world.each(over, without=without):
                for row in held.rows:
                    if arity is not None and len(row) != arity:
                        continue
                    for claim in _claims(say(f, subject, *row)):
                        f.fact(*claim)

    return system


def assign(f: Facts, name: str, subject, *row, keys: int = 1) -> None:
    """Deposit `name(subject, *row)` as the ONE row for its key, retracting rivals.

    ⭐ The single-valued update, which `plan.py` hand-rolled twice and slightly
    differently each time (`_redenote` on `denotes`, `_move_current` on
    `current`). A rule that only ever `fact`s a new answer leaves the old one
    standing beside it, and then `f.one()` has two — the failure is a reader's,
    far from the writer that caused it.

    `keys` says how many of `row`'s leading objects form the key; the rest is the
    value. `denotes(query, scenario, entity)` is `keys=1` from the query's side.
    """
    key = row[:keys]
    for old in list(f.of(name, subject)):
        if len(old) == len(row) and old[:keys] == key and old != row:
            f.deny(name, subject, *old)
    f.fact(name, subject, *row)


def fired(f: Facts, *key) -> bool:
    """Has the minting rule for this occasion already run? See `minting`."""
    return f.holds(MARK, *key)


def minting(f: Facts, over, once_per, do, *, arity=None, without=()):
    """A rule that INVENTS entities — at most once per key, and the key is required.

    ⚠⚠ **The key is the termination argument, and there is no version of this
    without one.** A minting rule cannot be trusted to stop itself: whether its
    own output re-satisfies its trigger is a property of the edit, not of the
    rule, and `lower` versus `relax` is the whole lesson — `gt`→`ge` happens to
    falsify `operator == gt`, so `relax` terminated by LUCK, while `lower` left a
    literal where it found one and did not. So the bound is stated where it can
    be checked instead of inferred: `once_per` names the occasion, and this fires
    for each one exactly once, ever.

    `do(f, world, subject, *row)` returns False to decline (nothing minted, the
    key stays open — a rule may not APPLY yet and must be free to say so), or
    anything else to mean it acted, which spends the key for good.
    """

    def system(world) -> None:
        for subject, held in world.each(over, without=without):
            for row in held.rows:
                if arity is not None and len(row) != arity:
                    continue
                for key in once_per(f, subject, *row) or ():
                    if f.holds(MARK, *key):
                        continue
                    if do(f, world, subject, *row, key=key) is not False:
                        f.fact(MARK, *key)

    return system
