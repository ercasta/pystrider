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
"""
from __future__ import annotations

import ast
import os
from typing import Any, Dict, List, Optional, Tuple

from harneskills.loop import Loop
from harneskills.world import Component, Entity, World

#: ⚠⚠ **WHAT THIS PACKAGE USES OF `harneskills`, ASSERTED ON IMPORT.**
#:
#: `mf.py` did exactly this for `ugm` and it paid off four times — a packaging fix,
#: a rename, a rewrite, and an engine collapse — because the alternative is an
#: `AttributeError` three frames into a run, or worse, a method that still exists
#: and means something else. `harneskills` is a SIBLING CHECKOUT under active
#: development, not a pinned dependency, so the surface it offers can move between
#: one run and the next.
#:
#: ⭐ The whole dependency is these fourteen names. That is the number worth
#: keeping small: everything `pystrider` needs of its substrate is an entity store
#: with set-semantics attach and a loop that settles, and if the list ever grows
#: much past this, the adapter has started leaking.
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


def _check_substrate() -> None:
    """⚠ Checked on an INSTANCE, not on the class.

    `revision`, `errors` and `systems` are assigned in `__init__`, so
    `hasattr(World, "revision")` is False and a class-level check reports the
    substrate broken when it is fine. That is not a detail — a guard that
    false-alarms gets deleted, and then the real drift goes unnoticed.
    """
    import harneskills.loop as _loop
    import harneskills.world as _world

    try:
        instances = {"World": _world.World(), "Loop": _loop.Loop(),
                     "Component": _world.Component(), "Entity": _world.Entity(None, 0)}
    except Exception as error:            # noqa: BLE001 — any failure means drift
        raise ImportError(
            f"`harneskills` at {os.path.dirname(_world.__file__)} could not be "
            f"constructed as this package expects: {error!r}"
        ) from error

    missing = [f"{name}.{member}"
               for name, members in _NEEDS.items()
               for member in members
               if not hasattr(instances[name], member)]
    if missing:
        raise ImportError(
            f"`harneskills` at {os.path.dirname(_world.__file__)} is missing "
            f"{', '.join(missing)} — that is not the substrate this package is "
            f"written against. It is a sibling checkout rather than a pinned "
            f"dependency, so it moves; see `_NEEDS` in this module for the whole "
            f"surface pystrider uses."
        )


_check_substrate()

#: Where the substrate resolved to, so a probe can PRINT what it measured rather
#: than assert it and hope.
import harneskills.world as _world_module  # noqa: E402
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
        #: between two worlds would compare unequal to itself.
        self._words: Dict[str, Entity] = {}
        self._values: Dict[str, Entity] = {}
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
        """Register one system. `Loop.system`'s signature, forwarded."""
        return self.loop.system(fn, name=name)

    # -- naming -----------------------------------------------------------

    def node(self, printed: str) -> Entity:
        """A fresh individual. The name is for printing; identity is the entity."""
        return self.world.spawn(Printed(printed))

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
        if got is None:
            got = self._words[text] = self.world.spawn(Printed(text))
        return got

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
        if got is None:
            got = self._values[text] = self.world.spawn(Printed(text))
        return got

    def show(self, n: Entity) -> str:
        got = self.world.get(n, Printed)
        return repr(n) if got is None else got.text

    #: The word back out of the entity. The inverse of `word`.
    word_of = show

    def payload(self, n: Entity) -> Any:
        """The literal back out of the entity. The inverse of `value`."""
        text = self.show(n)
        return Ellipsis if text == _ELLIPSIS else ast.literal_eval(text)

    # -- writing ----------------------------------------------------------

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
        held = self.world.get(subject, cls)
        rows = () if held is None else held.rows
        if row not in rows:
            # ⭐ A new component rather than a mutated one — `attach` compares by
            # value, and a component mutated in place is a change nothing can see.
            self.world.attach(subject, cls(rows + (row,)))
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
        self.world.attach(subject, relation(name)((tuple(objects),)))
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
        """
        cls = relation(name)
        held = self.world.get(subject, cls)
        if held is None or tuple(objects) not in held.rows:
            return False
        rows = tuple(r for r in held.rows if r != tuple(objects))
        if rows:
            self.world.attach(subject, cls(rows))
        else:
            self.world.detach(subject, cls)
        return True

    def reify(self, name: str, *members: Entity) -> Entity:
        """An entity standing for the proposition `name(members...)`, interned.

        For the places a claim is made ABOUT a claim — `unmet($p, evaluated(...))`.
        ⚠ Interned on its printed form, so asking twice about the same proposition
        gets the same subject and the rules join.
        """
        key = "%s(%s)" % (name, ", ".join(self.show(m) for m in members))
        got = self._values.get(key)
        if got is None:
            got = self._values[key] = self.world.spawn(Printed(key))
            self.fact("proposition", got)
            self.fact("about", got, self.word(name), *members)
        return got

    # -- reading ----------------------------------------------------------

    def of(self, name: str, subject: Entity) -> List[Tuple[Entity, ...]]:
        """Every `name(subject, ...)` that holds, in deposit order.

        Insertion-ordered, because a body is an ordered thing.
        """
        held = self.world.get(subject, relation(name))
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
        """Every entity this relation is asserted of, in spawn order."""
        return [e for e, _ in self.world.each(relation(name))]

    def has(self, name: str, subject: Entity) -> bool:
        """Whether `name(subject)` — a kind, or any claim at all — holds now."""
        held = self.world.get(subject, relation(name))
        return held is not None and bool(held.rows)

    def holds(self, name: str, subject: Entity, *objects: Entity) -> bool:
        """Whether this exact proposition holds right now."""
        held = self.world.get(subject, relation(name))
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
