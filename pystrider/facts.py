"""The substrate adapter: propositions, on `harneskills`' entity-component world.

Engine 4 was `ugm`'s scratchpad — interned propositions, a name table, and a
matcher. This is engine 5, and it is not an engine at all: `harneskills` is an
entity-component world plus a loop that calls every system until nothing changes.
What had to be re-derived is the MAPPING, once, here:

    ugm scratchpad                    harneskills
    --------------------------------  ------------------------------------------
    `g.atom("for_stmt@3")`        ->  `world.spawn(Printed(...))` — an ENTITY
    `for_stmt(n)`                 ->  the entity carries the `for_stmt` component
    `name(n, f)`                  ->  ... carrying one ROW, `(f,)`
    `stmt(b, s1)`, `stmt(b, s2)`  ->  ... carrying two rows, in order
    `Loader.atom(name)`           ->  a Python CLASS, one per relation name

> ⭐⭐ **A kind, an attribute and an edge were three mechanisms on engine 2, ONE
> proposition on engine 4, and here they are one COMPONENT.** A relation is a
> component type; the objects are its rows. A kind is the same thing with a single
> empty row — nothing to say about the subject except that it is one.

**⭐ WHAT THIS FLOOR DELETES, and it is the largest thing the port removes.**

1. **THE TWIN TRAP IS STRUCTURALLY GONE.** `Graph.atom(name)` minted a fresh node
   every call, so a relation built in Python was a TWIN of the one an authored rule
   used, nothing matched, and the run reported a contented quiescence having done
   nothing. It cost this project four recorded readings. Here a relation IS a
   Python class, interned by name in `_RELATIONS` — two `relation("body")` calls
   are the same object because Python says so, and there is no second table to
   drift from. There is nothing left to get wrong, so there is no warning to carry.

2. **THE `no <own conclusion>` PREMISE IS NO LONGER LOAD-BEARING.** ugm had no
   inert set: an application that changed nothing was offered again, so a rule that
   did not stop itself never stopped, and the symptom was a run burning its whole
   budget on the first applicable rule while every later rule never fired. The
   `harneskills` loop settles on `world.revision`, and `World.attach` compares
   before it stores — so **re-deriving a fact that already holds is not a change**,
   and a rule that keeps concluding the same thing lets the world settle anyway.
   Systems still say `without=` where they mean *only the ones not yet described*,
   because that is the honest reading of the query; they no longer say it to avoid
   a hang.

3. **THE HAND-ROLLED INDEX IS GONE.** `Facts` used to keep its own
   `(relation, subject) -> propositions` map, catching up off `g.instances_of`,
   because the engine's matcher was quadratic in the instances a rule joins.
   `World._by_type` already is that index: `of()` is a dict lookup and `subjects()`
   walks one bucket. ⚠ The defect that map once had is worth keeping in mind —
   it indexed only what `fact()` wrote, so **a reader could not see what a RULE had
   concluded** — and it cannot recur here, because there is one store and both
   write to it.

**⚠ WHAT DID NOT CHANGE, because it was never the engine's doing.**

`word` and `value` are still different kinds of node. Conflating them is what made
`operator` store as `'gt'` — quoted — so a rule naming the bare `gt` could never
match and one of two repair families was dead while the suite stayed green. That
distinction is about what a symbol MEANS, not about how it is stored, so it
survives the substrate change untouched.

**⚠⚠ ENGINE 5, ONE CONTRACT LATER (harneskills 11c459a).** A system stopped
touching its world at all — it returns deltas, `Loop.tick` applies them. `patterns.py`,
`repair.py`, `cnl.py` and every block-driven system did not change one line of
their own LOGIC: every write already went through `fact`/`state`/`deny`, never
`world.attach` directly, so the whole adaptation lives here, in this one class.
`fact`/`state`/`deny` accumulate instead of writing; `system()` wraps a registered
function to collect what accumulated and hand it back; `_held` lets a `deny` then
a `fact` on the same (name, subject) — `relax`/`lower` do exactly that, denying an
operator and asserting its replacement in one turn — see the accumulated write
rather than the world as of the turn's start. The one genuinely new piece is
`_mint`: `word`/`value`/`node`/`reify` describe a fresh entity rather than making
one when called from inside a system (`relax` minting the operator "ge" the first
time a `>` gets repaired to `>=`, say), and since that description only resolves
within ITS OWN turn, a LATER turn needing the same text has to find what an
EARLIER one already made real — `_find`, a scan, and the one place this floor
pays a cost the old direct-write version did not. `test_repair.py`'s and
`test_spine.py`'s full suites pass unchanged; nothing about what any system
concludes moved.
"""
from __future__ import annotations

import ast
import functools
import os
from typing import Any, Dict, List, Optional, Tuple

from ugm.delta import Pending, attach, detach, spawn
from ugm.loop import Loop
from ugm.world import Component, Entity, World

#: ⚠⚠ **WHAT THIS PACKAGE USES OF `ugm`, ASSERTED ON IMPORT.**
#:
#: `mf.py` did exactly this for the FIRST `ugm` and it paid off four times — a
#: packaging fix, a rename, a rewrite, and an engine collapse — because the
#: alternative is an `AttributeError` three frames into a run, or worse, a method
#: that still exists and means something else. This is a SECOND `ugm`: the graph
#: substrate `mf.py` guarded is gone; this one is `harneskills`' own engine,
#: carved back into its own package (harneskills 37d6fca) and reached here as
#: `../harneskills/engine` on `PYTHONPATH` -- a sibling checkout's sibling
#: checkout, not a pinned dependency, so the surface it offers can move between
#: one run and the next just as `harneskills` itself always could.
#:
#: ⭐ The whole dependency is these fourteen names. That is the number worth
#: keeping small: everything `pystrider` needs of its substrate is an entity store
#: with set-semantics attach and a loop that settles, and if the list ever grows
#: much past this, the adapter has started leaking.
#:
#: ⚠ `ugm.Engine` is deliberately NOT in this list. As of harneskills 47dd9a2
#: upstream splits the loop from the CHANNELS attached to it — one thread owning
#: the world, with terminals and WebSocket clients posting into it. That is the
#: right shape for a session someone is sitting at, and the wrong one for a
#: derivation: pystrider settles a world and reads the answer, with no channel to
#: route a `Reply` to and nothing that may block. So this package keeps calling
#: `Loop.run` directly, and `Engine` is an available door it has no reason to open.
#:
#: ⚠ A name here that upstream renames is a loud refusal naming the checkout. It is
#: NOT a version pin and does not check behaviour — `attach` comparing before it
#: stores is load-bearing (it is what makes the world settle) and no assertion here
#: can see that. `test_the_world_SETTLES` is what catches it.
_NEEDS = {
    "World": ("spawn", "attach", "detach", "get", "each", "revision"),
    "Loop": ("system", "run", "errors", "systems"),
    "Component": ("__eq__",),
    "Entity": ("id",),
}

#: ⚠ `ugm.delta` joined this list the day `Facts` stopped touching its own
#: `World` from inside a system's turn -- `fact`/`state`/`deny`/`node`/`word`/
#: `value`/`reify` describe a change now, they no longer make one, and
#: `Pending` is what lets one of them use the entity another just described
#: in the SAME turn. A module, not an instance, so it is checked by name
#: rather than constructed.
_NEEDS_DELTA = ("Pending", "spawn", "attach", "detach", "destroy")


def _check_substrate() -> None:
    """⚠ Checked on an INSTANCE, not on the class.

    `revision`, `errors` and `systems` are assigned in `__init__`, so
    `hasattr(World, "revision")` is False and a class-level check reports the
    substrate broken when it is fine. That is not a detail — a guard that
    false-alarms gets deleted, and then the real drift goes unnoticed.
    """
    import ugm.delta as _delta
    import ugm.loop as _loop
    import ugm.world as _world

    try:
        instances = {"World": _world.World(), "Loop": _loop.Loop(),
                     "Component": _world.Component(), "Entity": _world.Entity(None, 0)}
    except Exception as error:            # noqa: BLE001 — any failure means drift
        raise ImportError(
            f"`ugm` at {os.path.dirname(_world.__file__)} could not be "
            f"constructed as this package expects: {error!r}"
        ) from error

    missing = [f"{name}.{member}"
               for name, members in _NEEDS.items()
               for member in members
               if not hasattr(instances[name], member)]
    missing += [f"delta.{member}" for member in _NEEDS_DELTA
               if not hasattr(_delta, member)]
    if missing:
        raise ImportError(
            f"`ugm` at {os.path.dirname(_world.__file__)} is missing "
            f"{', '.join(missing)} — that is not the substrate this package is "
            f"written against. It is a sibling checkout's sibling checkout rather "
            f"than a pinned dependency, so it moves; see `_NEEDS` in this module "
            f"for the whole surface pystrider uses."
        )


_check_substrate()

#: Where the substrate resolved to, so a probe can PRINT what it measured rather
#: than assert it and hope.
import ugm.world as _world_module  # noqa: E402
SUBSTRATE = os.path.dirname(_world_module.__file__)

#: Attribute payloads are stored as their `repr`, which round-trips exactly for
#: every constant Python's grammar can express (`str`, `bytes`, `int`, `float`,
#: `complex`, `bool`, `None`, and the ellipsis). ⚠ The value therefore lives IN
#: the world as an entity's printed name rather than in a Python dict beside it —
#: a side map would be state the systems cannot see, which is the thing this
#: substrate is for.
_ELLIPSIS = "..."


class Printed(Component):
    """What an entity is called when something has to show it to a person.

    ⚠ For PRINTING, never for identity — an AST node is not a name a corpus wrote,
    and two `x`s in two functions are two entities that happen to print the same.
    `word()` and `value()` are the two places identity does go by name.
    """

    def __init__(self, text: str) -> None:
        self.text = text


class Relation(Component):
    """One relation, on one subject: the ordered rows of objects it relates it to.

    `body(n, b)` is one row, `(b,)`. `stmt(block, s1)` and `stmt(block, s2)` are two
    rows on the same component, in deposit order — **a body is an ordered thing**,
    and describing a three-line loop by its first statement is the bug that
    ordering exists to prevent.

    A KIND (`for_stmt(n)`) is the degenerate case: one row with no objects. There
    is nothing to say about the subject except that it is one.

    ⚠ Rows are DEDUPED, which is `ugm`'s interning arriving as an ordinary set
    check. It is what makes `fact()` idempotent, and `attach` comparing before it
    stores is what turns that into *the loop settles*. See the module note.
    """

    def __init__(self, rows: Tuple[Tuple[Entity, ...], ...] = ()) -> None:
        self.rows = tuple(rows)


#: relation name -> its component class. ⭐ The name table that used to be
#: `Loader`'s, and the reason the twin trap cannot recur: interning is Python's.
_RELATIONS: Dict[str, type] = {}


def relation(name: str) -> type:
    """The component class for this relation. The SAME class every call.

    ⭐ This is what a system names: `world.each(relation("for_stmt"), ...)`. A
    domain that wants to read well binds them once at module scope —
    `ForStmt = relation("for_stmt")` — and its systems then look like the
    `harneskills` examples, because they are.
    """
    cls = _RELATIONS.get(name)
    if cls is None:
        # ⚠ `type()` takes the relation's own name so a stray `repr` in a traceback
        # says `body(...)` rather than `Relation(...)` about four different things.
        cls = _RELATIONS[name] = type(name, (Relation,), {"relation": name})
    return cls


class Facts:
    """One world, one loop, and the propositions deposited into it."""

    def __init__(self, *domains, budget: int = 400) -> None:
        self.world = World()
        self.loop = Loop(self.world, budget=budget)
        #: Interning tables. ⚠ Per-world, because an entity belongs to a world:
        #: `Entity.__eq__` checks `other.world is self.world`, so a word shared
        #: between two worlds would compare unequal to itself. Only ever hold a
        #: REAL `Entity`, never a `Pending` -- see `_mint`.
        self._words: Dict[str, Entity] = {}
        self._values: Dict[str, Entity] = {}
        #: THIS TURN's own not-yet-applied writes, or `None` between turns --
        #: see `system()`. `_pending` is the flat list `ugm.loop.Loop.tick`
        #: applies; `_overlay` and `_minting` are what let `fact`/`deny`/`word`
        #: read back what THIS SAME turn already described, before any of it
        #: is real.
        self._pending: Optional[list] = None
        self._overlay: Optional[Dict[Tuple[Entity, type], Optional[Component]]] = None
        self._minting: Optional[Dict[str, Entity]] = None
        for domain in domains:
            self.install(domain)

    # -- domains ----------------------------------------------------------

    def install(self, domain):
        """Hand this loop to a domain's `install(loop, facts)`.

        ⚠ Two arguments where `harneskills` passes one: a domain here needs the
        naming table as well as the world, because a system that wants to deposit
        `iteration(n)` needs the same `Facts` the reader will ask.
        """
        return domain(self.loop, self)

    def system(self, fn=None, *, name=None):
        """Register one system -- wrapped so `fact`/`state`/`deny`/`node`/
        `word`/`value`/`reify`, called from inside it, describe a change
        instead of making one.

        ⚠⚠ **This is the whole of what changed for `patterns.py`, `repair.py`
        and `cnl.py` — nothing in them did.** `harneskills` 11c459a made a
        system return deltas rather than touch the world; every system this
        package registers already went through `f.fact(...)`, never
        `world.attach(...)` directly, so ONE place absorbs the new contract:
        `f.fact`/`state`/`deny` accumulate instead of writing, this wrapper
        collects what accumulated and hands it back, and `Loop.tick` applies
        it exactly as it always applied whatever a system returned.

        `functools.wraps` is load-bearing, not tidiness: `ugm.loop`'s own
        `_name_of` reads `fn.__module__`/`fn.__name__` to name a system
        `patterns.iteration` rather than `facts.wrapped`, and the SYSTEMS
        registry `/systems` prints is only legible if it does.
        """
        if fn is None:
            return lambda f: self.system(f, name=name)

        @functools.wraps(fn)
        def wrapped(world):
            self._pending, self._overlay, self._minting = [], {}, {}
            try:
                fn(world)
            finally:
                pending = self._pending
                self._pending = self._overlay = self._minting = None
            return pending

        return self.loop.system(wrapped, name=name)

    # -- reading back THIS TURN's own not-yet-applied writes ---------------

    def _held(self, subject: Entity, cls: type) -> Optional[Component]:
        """The component of this type on this subject, as of RIGHT NOW —
        this turn's own writes first (even a `None` recorded there, a
        `deny` down to nothing), the world under them otherwise.

        `subject` may be a `Pending` from a `spawn`/`node`/`word`/`value`
        earlier in THIS SAME turn — nothing on the real world yet, so
        there is nothing to fall back to but what the overlay itself
        already knows about it.
        """
        if self._overlay is not None:
            key = (subject, cls)
            if key in self._overlay:
                return self._overlay[key]
        if isinstance(subject, Pending):
            return None
        return self.world.get(subject, cls)

    # -- naming -----------------------------------------------------------

    def _find(self, text: str) -> Optional[Entity]:
        """A REAL `Printed(text)` already in the world, if one exists.

        The fallback for exactly what `_words`/`_values`/`_minting` do not
        cover: a word or value first minted mid-turn is a `Pending`, never
        cached in the global tables (see `_mint`), so a LATER turn -- even
        the very next tick, the same system reasoning about the same
        thing again -- has nothing to look up and would otherwise mint a
        SECOND entity for the same text every single time it asks. That
        is not a slow path, it is a world that never settles: `answer`
        deriving `could_not_evaluate(f, c, value(refused))` fresh every
        tick, each with a DIFFERENT entity for the identical refusal
        string, so the row never repeats and the system never stops
        firing -- `test_an_unmodelled_operator_is_refused_BY_NAME` is
        what this looked like before `_find` existed.
        """
        for entity, printed in self.world.each(Printed):
            if printed.text == text:
                return entity
        return None

    def _mint(self, text: str):
        """A fresh `Printed(text)` -- an `Entity` outside a system's turn
        (nothing to describe instead of), a `Pending` inside one, the same
        way `spawn()` itself hands one back. `_find` first, mid-turn: an
        EARLIER turn's own mint may already be real by now (`Loop.tick`
        applies a system's deltas the moment it returns, before the next
        one runs), just not yet reflected in `_words`/`_values`.

        ⚠⚠ **`word`/`value` cache only a REAL entity, never a `Pending`.**
        `_words`/`_values` are read by ANY system, on ANY later tick — a
        `Pending` only resolves within the list its own `Spawn` came back
        in, so caching one globally would hand a LATER turn a token that
        blows up the moment it is used (`ugm.delta` refuses it by name).
        `_minting` is the one place a `Pending` IS cached, and only for the
        rest of THIS turn: `word("ge")` called twice while proposing one
        repair must return the SAME token both times, or the second call
        mints a second, different "ge".
        """
        if self._pending is not None:
            cached = self._minting.get(text)
            if cached is not None:
                return cached
            found = self._find(text)
            if found is not None:
                return found
            made = spawn(Printed(text))
            self._pending.append(made)
            self._minting[text] = made.entity
            self._overlay[(made.entity, Printed)] = Printed(text)
            return made.entity
        return self.world.spawn(Printed(text))

    def node(self, printed: str) -> Entity:
        """A fresh individual. The name is for printing; identity is the entity."""
        return self._mint(printed)

    def word(self, text: str) -> Entity:
        """A VOCABULARY word — an operator, an identifier, a CNL atom.

        ⚠⚠ **Not a literal, and conflating the two made a corpus unable to talk
        about code.** `value()` encodes by `repr`, so the operator `gt` was stored
        under the name `'gt'` — quoted — while a rule naming `gt` means the bare
        word. The two never matched, so one of two repair families could never fire
        **ever**, and the only reason the suite looked healthy is that its rival
        keys on an integer, where `repr(18)` and the token `18` agree by luck.

        ⭐ The distinction is real rather than a workaround: `age > 18` holds one
        Python literal, `18`. `gt` is not a value the program computes with — it is
        a word from our vocabulary, and words are what rules are made of.
        """
        got = self._words.get(text)
        if got is not None:
            return got
        made = self._mint(text)
        if not isinstance(made, Pending):
            self._words[text] = made
        return made

    #: CNL's name for the same thing. A block's `premium` is a word.
    atom = word

    def known(self, text: str) -> Optional[Entity]:
        """The word for this text IF it has already been interned, else None.

        ⚠⚠ **THE ONE READ THAT MUST NOT MINT, and minting here is a world that never
        settles.** `word()` spawns on a miss, so a matcher that resolved an atom
        through it would `spawn` on every failed unification — the revision moves,
        the loop calls that a firing system, and it ticks until the budget runs out
        having concluded nothing. It is the old no-inert-set hang arriving through a
        different door, so the door is closed rather than documented: a system reads
        the vocabulary, it does not extend it.
        """
        return self._words.get(text)

    def value(self, payload: Any) -> Entity:
        """An entity standing for a literal, named by its `repr` so a reader recovers it.

        ⭐ Interned, and it is the RIGHT identity rather than merely the working
        one: two `10`s in two functions are the same *value*, while the two
        `constant` nodes holding them stay distinct because those come from
        `node()`. Identity of a value is its value; identity of an occurrence is
        the occurrence.
        """
        text = _ELLIPSIS if payload is Ellipsis else repr(payload)
        got = self._values.get(text)
        if got is not None:
            return got
        made = self._mint(text)
        if not isinstance(made, Pending):
            self._values[text] = made
        return made

    def show(self, n: Entity) -> str:
        got = self._held(n, Printed)
        return repr(n) if got is None else got.text

    #: The word back out of the entity. The inverse of `word`.
    word_of = show

    def payload(self, n: Entity) -> Any:
        """The literal back out of the entity. The inverse of `value`."""
        text = self.show(n)
        return Ellipsis if text == _ELLIPSIS else ast.literal_eval(text)

    # -- writing ----------------------------------------------------------

    def _write(self, subject: Entity, component: Component) -> None:
        """Put this component on that subject -- described as a delta if
        this is inside a system's turn (staged in the overlay too, so
        THIS SAME turn reads it back), attached directly otherwise. The
        one place `fact`/`state` actually write.
        """
        cls = type(component)
        if self._pending is not None:
            self._pending.append(attach(subject, component))
            self._overlay[(subject, cls)] = component
        else:
            self.world.attach(subject, component)

    def _erase(self, subject: Entity, cls: type) -> None:
        """Take this component type off that subject entirely -- staged or
        direct, the same way `_write` is."""
        if self._pending is not None:
            self._pending.append(detach(subject, cls))
            self._overlay[(subject, cls)] = None
        else:
            self.world.detach(subject, cls)

    def fact(self, name: str, subject: Entity, *objects: Entity) -> Entity:
        """Deposit `name(subject, objects...)`, and return the SUBJECT.

        ⚠ Engine 4 returned the proposition, because a proposition was a node and
        `unreadable`/the gap vocabulary needed somewhere to hang. Here a relation
        is not a thing in the world — it is a component ON the subject — so there
        is nothing to hand back but the subject. Where a claim ABOUT a claim is
        wanted, the subject is minted for it (`reify`).
        """
        cls = relation(name)
        row = tuple(objects)
        held = self._held(subject, cls)
        rows = () if held is None else held.rows
        if row not in rows:
            # ⭐ A new component rather than a mutated one — `attach` compares by
            # value, and a component mutated in place is a change nothing can see.
            self._write(subject, cls(rows + (row,)))
        return subject

    def state(self, name: str, subject: Entity, *objects: Entity) -> Entity:
        """Deposit `name(subject, objects...)` as the ONLY row of that relation.

        ⭐ `fact()` appends, which is what a body of statements needs; this
        REPLACES, which is what a conclusion that can be revised needs. A system
        that re-resolves a screen shape every tick must not leave both answers
        standing — `one()` would then refuse to pick between them, correctly, about
        a question that has exactly one answer.

        ⚠ Still idempotent: `attach` compares before it stores, so restating the
        same answer does not move `revision` and the world still settles.
        """
        self._write(subject, relation(name)((tuple(objects),)))
        return subject

    def deny(self, name: str, subject: Entity, *objects: Entity) -> bool:
        """Withdraw `name(subject, objects...)`. True if it was there to withdraw.

        ⚠ Engine 4's chain was append-only, so *change this* had to be spelled
        `-old, +new` and a reader that walked its own deposit log would see BOTH —
        engine 2 shipped a repair that "succeeded" while emitting byte-identical
        source, and only an independent gate caught it. Here there is one store and
        removal is removal, so a reader cannot see a withdrawn claim at all. The
        deny-then-assert SHAPE stays because it is what a repair means; the hazard
        it guarded against is gone.

        ⚠ Reads `_held`, not `self.world.get` — `relax`/`lower` `deny` an
        operator and `fact` its replacement in the SAME turn, and the second
        call has to see the first's own effect or both rows would stand.
        """
        cls = relation(name)
        held = self._held(subject, cls)
        if held is None or tuple(objects) not in held.rows:
            return False
        rows = tuple(r for r in held.rows if r != tuple(objects))
        if rows:
            self._write(subject, cls(rows))
        else:
            self._erase(subject, cls)
        return True

    def reify(self, name: str, *members: Entity) -> Entity:
        """An entity standing for the proposition `name(members...)`, interned.

        For the places a claim is made ABOUT a claim — `unmet($p, evaluated(...))`.
        ⚠ Interned on its printed form, so asking twice about the same proposition
        gets the same subject and the rules join.
        """
        key = "%s(%s)" % (name, ", ".join(self.show(m) for m in members))
        got = self._values.get(key)
        if got is not None:
            return got
        made = self._mint(key)
        if not isinstance(made, Pending):
            self._values[key] = made
        self.fact("proposition", made)
        self.fact("about", made, self.word(name), *members)
        return made

    # -- reading ----------------------------------------------------------

    def of(self, name: str, subject: Entity) -> List[Tuple[Entity, ...]]:
        """Every `name(subject, ...)` that holds, in deposit order.

        Insertion-ordered, because a body is an ordered thing. Reads
        `_held`, not `self.world.get` — a system that `fact`s or `deny`s
        and then reads the SAME (name, subject) again before its own turn
        ends must see what it just described, not the world as of the
        turn's start.
        """
        held = self._held(subject, relation(name))
        return [] if held is None else list(held.rows)

    def one(self, name: str, subject: Entity) -> Optional[Entity]:
        """The single object of a relation, or None. Refuses to guess between two.

        ⚠ Engine 2's `targets(n, label)[0]` silently described a three-line loop by
        its first statement, and later described `f(a, b)` by its first argument
        after a gap renumbered the rest. Taking the first of several is the shape of
        both bugs, so this will not do it.
        """
        got = self.of(name, subject)
        if not got:
            return None
        if len(got) > 1:
            raise ValueError(
                f"{name} of {self.show(subject)} has {len(got)} objects — "
                f"`one` refuses to pick; the caller wants `of`"
            )
        if len(got[0]) != 1:
            # ⚠ The same refusal in the other axis, and it was once missing: a
            # THREE-place relation has two objects, and this quietly returned the
            # first — `text("wants", f)` handed back the CASE where the caller meant
            # the value, and the error surfaced two frames away in `literal_eval`.
            raise ValueError(
                f"{name} of {self.show(subject)} is {len(got[0]) + 1}-place — "
                f"`one` answers about a single object; the caller wants `of`"
            )
        return got[0][0]

    def subjects(self, name: str) -> List[Entity]:
        """Every entity this relation is asserted of, in spawn order.

        ⚠ Reads `self.world` straight, NOT `_held` — this asks across every
        entity there is, and the overlay only ever knows about the ones a
        single subject-keyed write already named. A system that `fact`s a
        NEW subject onto `name` and then calls `subjects(name)` in the SAME
        turn will not see that subject until the next one; nothing
        currently does both in one turn, and `test_the_world_SETTLES`
        (`facts.py`'s own guard, not a mention here) is what would catch it
        if that ever changes.
        """
        return [e for e, _ in self.world.each(relation(name))]

    def has(self, name: str, subject: Entity) -> bool:
        """Whether `name(subject)` — a kind, or any claim at all — holds now."""
        held = self._held(subject, relation(name))
        return held is not None and bool(held.rows)

    def holds(self, name: str, subject: Entity, *objects: Entity) -> bool:
        """Whether this exact proposition holds right now."""
        held = self._held(subject, relation(name))
        return held is not None and tuple(objects) in held.rows

    def text(self, name: str, subject: Entity) -> Optional[str]:
        """A WORD-valued attribute (`name`, `id`, `attr`, `operator`), back as a `str`."""
        n = self.one(name, subject)
        return None if n is None else self.show(n)

    def literal(self, name: str, subject: Entity) -> Any:
        """A VALUE-valued attribute (`literal`, `origin`, `source_line`), decoded.

        The counterpart to `text`, and named so a caller has to say which kind it
        expects — reaching for the wrong one fails loudly instead of handing back
        `"'gt'"` where `"gt"` was meant.
        """
        n = self.one(name, subject)
        return None if n is None else self.payload(n)

    # -- running ----------------------------------------------------------

    def run(self, budget: Optional[int] = None):
        """Call every system until a whole pass changes nothing.

        ⚠⚠ **A system that raised is RE-RAISED here, which `harneskills` does not
        do.** Its loop records the exception on `loop.errors` and carries on,
        because a typo in one domain should not take a person's REPL down with it.
        That is right for a prompt and wrong for a derivation: a rule that raised
        did not fire, so the world settles *looking* quiescent while the conclusion
        it owed is simply absent — which is the exact shape of the silence this
        project has already paid for four times. A batch caller gets the error.
        """
        settled = self.loop.run(budget=budget)
        if self.loop.errors:
            name, error = self.loop.errors[0]
            raise RuntimeError(
                f"the system {name!r} raised, so whatever it concludes is missing "
                f"from a world that otherwise looks settled: {error!r}"
            ) from error
        if settled.hot:
            raise RuntimeError(
                f"the world did not settle in {settled.ticks} ticks — still firing: "
                f"{', '.join(settled.hot)}. Two systems are feeding each other, or "
                f"one concludes something it cannot recognise as already concluded."
            )
        return settled
