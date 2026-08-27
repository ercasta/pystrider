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
both. `ugm.engine`'s whole argument is *one world, several doors*. Two
things make it wrong here, and both are properties of what pystrider stores rather
than of the idea:

1. **The shared world is PERSISTED.** `ugm.save` writes it on every settle.
   Intaking one Python file spawns a few hundred entities and transliterating a real
   module spawns thousands, none of which anyone wants in `world.json` — which is
   7 KB today and is meant to be the thing the session KNEW, not a syntax tree it
   looked at once.

2. **⚠ `save` could not read them back anyway.** It names a component
   `module:qualname` and resolves it with `getattr`, and `facts.relation()` builds
   its classes with `type()` — so `pystrider.facts:for_stmt` serialises fine and
   raises `AttributeError` on load. It would not crash: `save.load` collects that as
   a *problem* and drops the component. **A world that silently comes back
   thinner is worse than one that refuses**, and this package has paid for exactly
   that shape of silence before.

⭐ So what lives in the shared world is the CONVERSATION — the goal a typed line
becomes, and the `Reply` it produces. Those are ordinary module-level classes,
`getattr`-resolvable and small. The derivation happens in a `Facts` of its own and
is thrown away with its answer already spoken.

⚠ If pystrider's facts should one day live in the shared world, the fix is upstream
and specific: `save` needs a registry a domain can put a class factory in, so
`pystrider.facts:for_stmt` resolves to `relation("for_stmt")`. That is a small
change and it is not this module's to make.

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


def _say(w, text: str) -> None:
    w.spawn(Reply("user", text))


# -- what a typed line means ----------------------------------------------------

def hear(w):
    """A line in -> a goal entity, or left standing for another domain to claim.

    ⚠ `Said` is destroyed only when this domain understood it. A line nobody
    claims is reported unheard by the prompt, which is what shares one world with
    `harneskills.examples.fs` without either domain having to know the other's
    vocabulary.
    """
    for entity, said in w.each(Said):
        if _understand(w, said.text):
            w.destroy(entity)


def _understand(w, text: str) -> bool:
    words = text.strip().split()
    if not words:
        return False
    verb, rest = words[0].lower(), words[1:]

    if verb == "blocks":
        w.spawn(BlocksWanted())
        return True

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
                    _say(w, "spend wants a number, e.g. `brew spend 50`")
                    return True
                i += 1
            else:
                _say(w, f"`brew` does not know {rest[i]!r} — try: irreversible, "
                        f"basic, premium, drive, spend <n>")
                return True
            i += 1
        w.spawn(wanted)
        return True

    if verb == "why" and len(rest) == 3:
        w.spawn(WhyWanted(*rest))
        return True

    if verb == "read" and len(rest) == 1:
        w.spawn(ReadWanted(rest[0]))
        return True

    return False


# -- the handlers ---------------------------------------------------------------

def _blocks(w):
    for entity, _ in w.each(BlocksWanted):
        w.destroy(entity)
        try:
            from demos.playground.brew import BLOCKS, _HERE
            from pystrider import cnl
            loaded = cnl.load_all(_HERE, BLOCKS)
        except Exception as error:                     # noqa: BLE001
            _say(w, f"could not load the blocks: {error!r}")
            continue
        _say(w, f"{len(loaded)} authored blocks, joined only by bridge.cnl:")
        for block in loaded:
            _say(w, f"  {block.name}.cnl  {len(block.facts)} facts, "
                    f"{len(block.rules)} rules")
        _say(w, f"  = {sum(len(b.rules) for b in loaded)} rules, each compiled to "
                f"one system")


def _brew(w):
    for entity, wanted in w.each(BrewWanted):
        w.destroy(entity)
        if wanted.drive:
            # ⚠ Said BEFORE the block, not after: the reply is drained on the tick
            # it is spawned, so a person watching sees why the prompt paused.
            _say(w, "driving the emitted app under Textual's Pilot (~1s, and the "
                    "world is stopped for every channel while it runs)...")
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
            _say(w, f"brew failed: {error!r}")
            _say(w, traceback.format_exc().strip().splitlines()[-1])
            continue

        _say(w, f"CART tier={cart.customer_tier} spend={cart.order_spend} "
                f"irreversible={cart.irreversible}")
        _say(w, f"  reason  : discount={r.granted} (rate {r.rate}%), settled in "
                f"{r.ticks} ticks")
        _say(w, f"  features: {', '.join(r.features) or '(none admitted)'}")
        for d in table:
            mark = "ok" if d["admitted"] else "REJECTED"
            _say(w, f"  {d['point']:8} {d['combinator']:11} {mark:8} {d['value']}"
                    + (f"  [{d['detail']}]" if d["detail"] else ""))
        _say(w, f"  screen  : {screen}")

        if not admitted:
            _say(w, "  emit    : nothing — a decision point refused, so no app is "
                    "claimed.")
            continue
        source = emit(cart, r, screen)
        _say(w, f"  emit    : {len(source.splitlines())} lines of Textual"
                + (", with the confirm gate" if screen == "confirm_screen" else "")
                + (", with the discount highlight"
                   if "def _show_discount" in source else ""))
        if not wanted.drive:
            _say(w, "  (`brew drive` to RUN it and read what actually happened)")
            continue
        try:
            v = verify(source, cart, r)
        except Exception as error:                     # noqa: BLE001
            _say(w, f"  drive   : failed — {error!r}")
            continue
        _say(w, f"  drive   : {v.events}")
        _say(w, f"  safety(ok)={v.ok} liveness(live)={v.live} shown={v.shown}"
                f"   => {'WORKS' if v.works else 'FAILS'}")


def _why(w):
    for entity, wanted in w.each(WhyWanted):
        w.destroy(entity)
        try:
            from demos.playground.brew import Cart, reason
            r = reason(Cart(irreversible=True))
            lines = r.why(wanted.subject, wanted.predicate, wanted.object)
        except Exception as error:                     # noqa: BLE001
            _say(w, f"why failed: {error!r}")
            continue
        if not lines:
            _say(w, f"nothing derives `{wanted.subject} {wanted.predicate} "
                    f"{wanted.object}` — it is a stated fact, or it does not hold")
            continue
        # ⚠ Says RE-DERIVED, not *because*: forward chaining keeps conclusions, not
        # the routes to them. `cnl.explain` names every rule that WOULD derive this,
        # which is a different claim from which one did. See its docstring.
        _say(w, "re-derived (which rules would conclude this, and from what):")
        for line in lines:
            _say(w, f"  {line}")


def _read(w):
    for entity, wanted in w.each(ReadWanted):
        w.destroy(entity)
        path = os.path.expanduser(wanted.path)
        try:
            source = open(path, encoding="utf-8").read()
        except OSError as error:
            _say(w, f"cannot read {wanted.path}: {error.strerror}")
            continue
        try:
            from pystrider import patterns
            from pystrider.emit import Unrenderable, emit
            from pystrider.facts import Facts
            from pystrider.intake import intake
            f = Facts(patterns.install)
            taken = intake(source, f, path)
            f.run()
        except Exception as error:                     # noqa: BLE001
            _say(w, f"could not read {wanted.path}: {error!r}")
            continue
        loops = [n for n in f.subjects("for_stmt")]
        described = [n for n in loops if f.has("iteration", n)]
        _say(w, f"{os.path.basename(path)}: {len(f.subjects('function'))} functions, "
                f"{len(loops)} loops, {len(described)} recognized as iterations")
        if taken.unmodelled:
            counts: dict = {}
            for name in taken.unmodelled:
                counts[name] = counts.get(name, 0) + 1
            named = ", ".join(f"{k}x{v}" if v > 1 else k
                              for k, v in sorted(counts.items()))
            _say(w, f"  unmodelled ({len(taken.unmodelled)}): {named}")
        else:
            _say(w, "  nothing unread")
        try:
            _say(w, "  round-trips byte-exact against the source: "
                    f"{emit(f, taken.module) == source}")
        except Unrenderable as refusal:
            _say(w, f"  refuses to write it back: {str(refusal).split(' — ')[-1]}")


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
