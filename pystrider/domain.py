"""pystrider as a harneskills DOMAIN — drive the bridge from the shared prompt.

    # ~/.config/harneskills/config
    harneskills.examples.fs:install
    pystrider.domain:install

Then, at the prompt (or from any attached channel — `Reply("user", ...)` is heard
by all of them):

    blocks                 which authored blocks are loaded, and what each contributes
    brew                   reason -> compose -> emit, and report every decision
    brew irreversible      ...with the knob flipped; watch the screen shape follow
    brew drive             ...and RUN the emitted app under Textual's Pilot
    why <subj> <pred> <obj>   what makes a derived fact so, across the blocks
    read <path.py>         intake a Python file and say what was recognized

## ⚠⚠ THE DERIVATIONS RUN IN A PRIVATE WORLD, AND THAT IS NOT THE OBVIOUS CHOICE

The obvious choice is the good one — put pystrider's facts in the SHARED world, so
a business rule and a file listing are entities side by side and one settle covers
both. `ugm.engine`'s whole argument is *one world, several doors*. What makes it
wrong here is a property of what pystrider stores rather than of the idea:

1. **The shared world is PERSISTED.** `ugm.save` writes it on every settle.
   Intaking one Python file spawns a few hundred entities and transliterating a real
   module spawns thousands, none of which anyone wants in `world.json` — which is
   7 KB today and is meant to be the thing the session KNEW, not a syntax tree it
   looked at once.

⭐⭐ **THERE USED TO BE A SECOND REASON AND IT IS FIXED, so do not cite it.** `save`
could not read a relation back at all: it resolves `module:qualname` with `getattr`
and `facts.relation()` builds its classes with `type()`, so a whole world of facts
serialised fine and came back one named problem per relation, silently thinner. A
`Relation` now says how to name itself (`ugm.facts:relation(for_stmt)`), and
interning survives a restart because it lives in the world as an `Interned` mark
rather than in a dict beside it. ⚠ The remaining reason above is SIZE, which is a
real reason and an ordinary one — not the "we cannot" it used to be paired with. If
someone wants pystrider's facts in the shared world, what stands between is
deciding they are worth persisting, not the substrate.

⭐ So what lives in the shared world is the CONVERSATION — the goal a typed line
becomes, and the `Reply` it produces. Those are ordinary module-level classes,
`getattr`-resolvable and small. The derivation happens in a `Facts` of its own and
is thrown away with its answer already spoken.

## ⚠ NOTHING HERE BLOCKS, except when you ask it to

`engine.py` is explicit: a system that stops the world stops it for every channel.
Reasoning and emitting are fast (three ticks, no I/O). **DRIVING the emitted app is
not** — Textual's Pilot takes about a second — so it is opt-in behind
`brew drive` and the reply says it is about to happen. A domain that blocked a
shared prompt for every `brew` would be a domain nobody leaves installed.
"""
from __future__ import annotations

import os
import traceback

from ugm.delta import destroy, spawn
from ugm.world import Component, Reply, Said

#: What the prompt should pull a typo towards. `world.learn` is autocorrect only —
#: nothing here changes what a system finds.
WORDS = ("blocks", "brew", "why", "read", "drive", "irreversible", "basic",
         "premium", "spend")


# -- the goals a typed line becomes ---------------------------------------------
# ⚠ Ordinary module-level classes, on purpose: `ugm.save` resolves a
# component by `module:qualname`, so these survive a restart where a
# `facts.relation()` class would not. See the module note.

class BrewWanted(Component):
    def __init__(self, irreversible: bool = False, tier: str = "premium",
                 spend: float = 150.0, drive: bool = False) -> None:
        self.irreversible = irreversible
        self.tier = tier
        self.spend = spend
        self.drive = drive


class BlocksWanted(Component):
    pass


class WhyWanted(Component):
    def __init__(self, subject: str, predicate: str, object: str) -> None:
        self.subject = subject
        self.predicate = predicate
        self.object = object


class ReadWanted(Component):
    def __init__(self, path: str) -> None:
        self.path = path


def _say(text: str):
    return spawn(Reply("user", text))


# -- what a typed line means ----------------------------------------------------

def hear(w):
    """A line in -> a goal entity, or left standing for another domain to claim.

    ⚠ `Said` is destroyed only when this domain understood it. A line nobody
    claims is reported unheard by the prompt, which is what shares one world with
    `harneskills.examples.fs` without either domain having to know the other's
    vocabulary.
    """
    deltas = []
    for entity, said in w.each(Said):
        understood = _understand(said.text)
        if understood is not None:
            deltas.extend(understood)
            deltas.append(destroy(entity))
    return deltas


def _understand(text: str):
    """The deltas this line asks for, if this domain has a reading of it
    -- `None` if it does not."""
    words = text.strip().split()
    if not words:
        return None
    verb, rest = words[0].lower(), words[1:]

    if verb == "blocks":
        return [spawn(BlocksWanted())]

    if verb == "brew":
        wanted = BrewWanted()
        i = 0
        while i < len(rest):
            token = rest[i].lower()
            if token == "irreversible":
                wanted.irreversible = True
            elif token in ("basic", "premium"):
                wanted.tier = token
            elif token == "drive":
                wanted.drive = True
            elif token == "spend" and i + 1 < len(rest):
                try:
                    wanted.spend = float(rest[i + 1])
                except ValueError:
                    return [_say("spend wants a number, e.g. `brew spend 50`")]
                i += 1
            else:
                return [_say(f"`brew` does not know {rest[i]!r} — try: irreversible, "
                             f"basic, premium, drive, spend <n>")]
            i += 1
        return [spawn(wanted)]

    if verb == "why" and len(rest) == 3:
        return [spawn(WhyWanted(*rest))]

    if verb == "read" and len(rest) == 1:
        return [spawn(ReadWanted(rest[0]))]

    return None


# -- the handlers ---------------------------------------------------------------

def _blocks(w):
    deltas = []
    for entity, _tag in w.each(BlocksWanted):
        deltas.append(destroy(entity))
        try:
            from demos.playground.brew import BLOCKS, _HERE
            from pystrider import cnl
            loaded = cnl.load_all(_HERE, BLOCKS)
        except Exception as error:                     # noqa: BLE001
            deltas.append(_say(f"could not load the blocks: {error!r}"))
            continue
        deltas.append(_say(f"{len(loaded)} authored blocks, joined only by bridge.cnl:"))
        for block in loaded:
            deltas.append(_say(f"  {block.name}.cnl  {len(block.facts)} facts, "
                               f"{len(block.rules)} rules"))
        deltas.append(_say(f"  = {sum(len(b.rules) for b in loaded)} rules, each "
                           f"compiled to one system"))
    return deltas


def _brew(w):
    deltas = []
    for entity, wanted in w.each(BrewWanted):
        deltas.append(destroy(entity))
        if wanted.drive:
            # ⚠ Said BEFORE the block, not after: the reply reaches every
            # channel once this turn's deltas are applied, so a person
            # watching sees why the prompt paused before `verify` blocks
            # for it.
            deltas.append(_say("driving the emitted app under Textual's Pilot (~1s, "
                               "and the world is stopped for every channel while "
                               "it runs)..."))
        try:
            from demos.playground import design
            from demos.playground.brew import Cart, emit, reason, verify
            cart = Cart(customer_tier=wanted.tier, order_spend=wanted.spend,
                        irreversible=wanted.irreversible)
            r = reason(cart)
            table = design.decisions(r.facts)
            screen = design.chosen_screen(r.facts) or "one_screen"
            admitted = bool(table) and all(d["admitted"] for d in table)
        except Exception as error:                     # noqa: BLE001
            deltas.append(_say(f"brew failed: {error!r}"))
            deltas.append(_say(traceback.format_exc().strip().splitlines()[-1]))
            continue

        deltas.append(_say(f"CART tier={cart.customer_tier} spend={cart.order_spend} "
                           f"irreversible={cart.irreversible}"))
        deltas.append(_say(f"  reason  : discount={r.granted} (rate {r.rate}%), "
                           f"settled in {r.ticks} ticks"))
        deltas.append(_say(f"  features: {', '.join(r.features) or '(none admitted)'}"))
        for d in table:
            mark = "ok" if d["admitted"] else "REJECTED"
            deltas.append(_say(f"  {d['point']:8} {d['combinator']:11} {mark:8} "
                               f"{d['value']}"
                               + (f"  [{d['detail']}]" if d["detail"] else "")))
        deltas.append(_say(f"  screen  : {screen}"))

        if not admitted:
            deltas.append(_say("  emit    : nothing — a decision point refused, so "
                               "no app is claimed."))
            continue
        source = emit(cart, r, screen)
        deltas.append(_say(f"  emit    : {len(source.splitlines())} lines of Textual"
                           + (", with the confirm gate"
                              if screen == "confirm_screen" else "")
                           + (", with the discount highlight"
                              if "def _show_discount" in source else "")))
        if not wanted.drive:
            deltas.append(_say("  (`brew drive` to RUN it and read what actually "
                               "happened)"))
            continue
        try:
            v = verify(source, cart, r)
        except Exception as error:                     # noqa: BLE001
            deltas.append(_say(f"  drive   : failed — {error!r}"))
            continue
        deltas.append(_say(f"  drive   : {v.events}"))
        deltas.append(_say(f"  safety(ok)={v.ok} liveness(live)={v.live} "
                           f"shown={v.shown}   => {'WORKS' if v.works else 'FAILS'}"))
    return deltas


def _why(w):
    deltas = []
    for entity, wanted in w.each(WhyWanted):
        deltas.append(destroy(entity))
        try:
            from demos.playground.brew import Cart, reason
            r = reason(Cart(irreversible=True))
            lines = r.why(wanted.subject, wanted.predicate, wanted.object)
        except Exception as error:                     # noqa: BLE001
            deltas.append(_say(f"why failed: {error!r}"))
            continue
        if not lines:
            deltas.append(_say(f"nothing derives `{wanted.subject} {wanted.predicate} "
                               f"{wanted.object}` — it is a stated fact, or it does "
                               f"not hold"))
            continue
        # ⚠ Says RE-DERIVED, not *because*: forward chaining keeps conclusions, not
        # the routes to them. `cnl.explain` names every rule that WOULD derive this,
        # which is a different claim from which one did. See its docstring.
        deltas.append(_say("re-derived (which rules would conclude this, and from what):"))
        for line in lines:
            deltas.append(_say(f"  {line}"))
    return deltas


def _read(w):
    deltas = []
    for entity, wanted in w.each(ReadWanted):
        deltas.append(destroy(entity))
        path = os.path.expanduser(wanted.path)
        try:
            source = open(path, encoding="utf-8").read()
        except OSError as error:
            deltas.append(_say(f"cannot read {wanted.path}: {error.strerror}"))
            continue
        try:
            from pystrider import patterns
            from pystrider.emit import Unrenderable, emit
            from ugm.facts import Facts
            from pystrider.intake import intake
            f = Facts(patterns.install)
            taken = intake(source, f, path)
            f.run()
        except Exception as error:                     # noqa: BLE001
            deltas.append(_say(f"could not read {wanted.path}: {error!r}"))
            continue
        loops = [n for n in f.subjects("for_stmt")]
        described = [n for n in loops if f.has("iteration", n)]
        deltas.append(_say(f"{os.path.basename(path)}: {len(f.subjects('function'))} "
                           f"functions, {len(loops)} loops, {len(described)} "
                           f"recognized as iterations"))
        if taken.unmodelled:
            counts: dict = {}
            for name in taken.unmodelled:
                counts[name] = counts.get(name, 0) + 1
            named = ", ".join(f"{k}x{v}" if v > 1 else k
                              for k, v in sorted(counts.items()))
            deltas.append(_say(f"  unmodelled ({len(taken.unmodelled)}): {named}"))
        else:
            deltas.append(_say("  nothing unread"))
        try:
            deltas.append(_say("  round-trips byte-exact against the source: "
                               f"{emit(f, taken.module) == source}"))
        except Unrenderable as refusal:
            deltas.append(_say(f"  refuses to write it back: "
                               f"{str(refusal).split(' — ')[-1]}"))
    return deltas


#: ⚠ `hear` first, then one handler per goal — the order IS the schedule, and a
#: goal spawned this tick is answered on the next one.
SYSTEMS = (hear, _blocks, _brew, _why, _read)


def install(loop) -> None:
    """Register the systems and teach the prompt this domain's words.

    ⚠ Nothing is spawned here. Unlike `harneskills.examples.fs`, this domain has no
    standing model to reconcile against a restored world — every derivation builds
    its own `Facts` and discards it, so there is nothing that could come back stale.
    """
    for system in SYSTEMS:
        loop.system(system)
    loop.world.learn(*WORDS)
