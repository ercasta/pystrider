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
both. `loopingrules.engine`'s whole argument is *one world, several doors*. What
makes it wrong here is a property of what pystrider stores rather than of the idea:

1. **The shared world is PERSISTED.** `loopingrules.save` writes it on every
   settle. Intaking one Python file spawns a few hundred entities and
   transliterating a real module spawns thousands, none of which anyone wants in
   `world.json` — which is 7 KB today and is meant to be the thing the session
   KNEW, not a syntax tree it looked at once.

⭐⭐ **THERE USED TO BE A SECOND REASON AND IT IS FIXED, so do not cite it.** An
earlier `save` could not read a generic relation back at all — it resolved
`module:qualname` with `getattr` and a dynamic relation factory built its classes
with `type()`, so a whole world of facts serialised fine and came back one named
problem per relation, silently thinner. That entire vocabulary is gone now,
replaced by explicitly-declared components `save` never had trouble with in the
first place — every remaining relation this package once carried generically is a
plain `@dataclass`, `getattr`-resolvable by construction. ⚠ The remaining reason
above is SIZE, which is a real reason and an ordinary one — not the "we cannot" it
used to be paired with. If someone wants pystrider's facts in the shared world,
what stands between is deciding they are worth persisting, not the substrate.

⭐ So what lives in the shared world is the CONVERSATION — the goal a typed line
becomes, and the `Reply` it produces. Those are ordinary module-level classes,
`getattr`-resolvable and small. The derivation happens in a private `Loop`/`World`
of its own and is thrown away with its answer already spoken.

## ⚠ NOTHING HERE BLOCKS, except when you ask it to

`engine.py` is explicit: a rule that stops the world stops it for every channel.
Reasoning and emitting are fast (three ticks, no I/O). **DRIVING the emitted app is
not** — Textual's Pilot takes about a second — so it is opt-in behind
`brew drive` and the reply says it is about to happen. A domain that blocked a
shared prompt for every `brew` would be a domain nobody leaves installed.

⚠⚠ 2026-08-29: rewritten off `Component`/`ugm.delta` onto plain `@dataclasses.
dataclass` components and direct `World` mutation — `loopingrules` dropped both
(a component is any dataclass now; a rule writes to `world` directly, the same
idiom `harneskills.examples.fs` uses). Every rule here used to build and RETURN a
list of deltas; now it mutates `w` and returns `None`.

## ⚠⚠ `help python` is a NEW dependency on `harneskills`, not on `loopingrules`

`hear`'s own docstring above says this domain shares one world with
`harneskills.examples.fs` "without either domain having to know the other's
vocabulary" — true of everything else in this file, no longer true of
`propose_help_python`, which imports `HelpTopic`/`HelpAnswer` from
`harneskills.help`. That module exists because `help` is one occasion two
independently-installed domains both want to answer, and neither `fs` nor
`pystrider` is the other's to import from — `harneskills` is the one thing
both already sit on top of. See `harneskills.help`'s own docstring for the
full argument and `loopingrules.world.arbitrate` for the mechanism that
makes answering an occasion this module did not create safe regardless of
which domain's `install()` the config lists first.
"""
from __future__ import annotations

import os
import traceback
from dataclasses import dataclass, replace

from loopingrules.world import Proposal, Reply, Said

from harneskills.help import HelpAnswer, HelpTopic

#: What the prompt should pull a typo towards. `world.learn` is autocorrect only —
#: nothing here changes what a rule finds.
WORDS = ("blocks", "brew", "why", "read", "drive", "irreversible", "basic",
         "premium", "spend", "python")


# -- the goals a typed line becomes ---------------------------------------------
# ⚠ Ordinary module-level classes, on purpose: `loopingrules.save` resolves a
# component by `module:qualname`, so these survive a restart.

@dataclass(frozen=True)
class BrewWanted:
    irreversible: bool = False
    tier: str = "premium"
    spend: float = 150.0
    drive: bool = False


@dataclass(frozen=True)
class BlocksWanted:
    pass


@dataclass(frozen=True)
class WhyWanted:
    subject: str
    predicate: str
    object: str


@dataclass(frozen=True)
class ReadWanted:
    path: str


def _say(w, text: str) -> None:
    w.spawn(Reply("user", text))


# -- what a typed line means ----------------------------------------------------

def hear(w) -> None:
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
    """Whether this domain has a reading of `text` — and if so, act on it
    directly. `True`/`False` in place of the old "deltas or None," since a
    rule mutates `w` itself now instead of describing a change to apply."""
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
                wanted = replace(wanted, irreversible=True)
            elif token in ("basic", "premium"):
                wanted = replace(wanted, tier=token)
            elif token == "drive":
                wanted = replace(wanted, drive=True)
            elif token == "spend" and i + 1 < len(rest):
                try:
                    wanted = replace(wanted, spend=float(rest[i + 1]))
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

def _blocks(w) -> None:
    for entity, _tag in w.each(BlocksWanted):
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
        _say(w, f"  = {sum(len(b.rules) for b in loaded)} rules, each "
                f"compiled to one rule")


def _brew(w) -> None:
    for entity, wanted in w.each(BrewWanted):
        w.destroy(entity)
        if wanted.drive:
            # ⚠ Said BEFORE the block, not after: the reply reaches every
            # channel once this tick settles, so a person watching sees why
            # the prompt paused before `verify` blocks for it.
            _say(w, "driving the emitted app under Textual's Pilot (~1s, "
                    "and the world is stopped for every channel while "
                    "it runs)...")
        try:
            from demos.playground import design
            from demos.playground.brew import Cart, emit, reason, verify
            cart = Cart(customer_tier=wanted.tier, order_spend=wanted.spend,
                        irreversible=wanted.irreversible)
            r = reason(cart)
            table = design.decisions(r.vocabulary)
            screen = design.chosen_screen(r.vocabulary) or "one_screen"
            admitted = bool(table) and all(d["admitted"] for d in table)
        except Exception as error:                     # noqa: BLE001
            _say(w, f"brew failed: {error!r}")
            _say(w, traceback.format_exc().strip().splitlines()[-1])
            continue

        _say(w, f"CART tier={cart.customer_tier} spend={cart.order_spend} "
                f"irreversible={cart.irreversible}")
        _say(w, f"  reason  : discount={r.granted} (rate {r.rate}%), "
                f"settled in {r.ticks} ticks")
        _say(w, f"  features: {', '.join(r.features) or '(none admitted)'}")
        for d in table:
            mark = "ok" if d["admitted"] else "REJECTED"
            _say(w, f"  {d['point']:8} {d['combinator']:11} {mark:8} "
                    f"{d['value']}"
                    + (f"  [{d['detail']}]" if d["detail"] else ""))
        _say(w, f"  screen  : {screen}")

        if not admitted:
            _say(w, "  emit    : nothing — a decision point refused, so "
                    "no app is claimed.")
            continue
        source = emit(cart, r, screen)
        _say(w, f"  emit    : {len(source.splitlines())} lines of Textual"
                + (", with the confirm gate"
                   if screen == "confirm_screen" else "")
                + (", with the discount highlight"
                   if "def _show_discount" in source else ""))
        if not wanted.drive:
            _say(w, "  (`brew drive` to RUN it and read what actually "
                    "happened)")
            continue
        try:
            v = verify(source, cart, r)
        except Exception as error:                     # noqa: BLE001
            _say(w, f"  drive   : failed — {error!r}")
            continue
        _say(w, f"  drive   : {v.events}")
        _say(w, f"  safety(ok)={v.ok} liveness(live)={v.live} "
                f"shown={v.shown}   => {'WORKS' if v.works else 'FAILS'}")


def _why(w) -> None:
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
                    f"{wanted.object}` — it is a stated fact, or it does "
                    f"not hold")
            continue
        # ⚠ Says RE-DERIVED, not *because*: forward chaining keeps conclusions, not
        # the routes to them. `cnl.explain` names every rule that WOULD derive this,
        # which is a different claim from which one did. See its docstring.
        _say(w, "re-derived (which rules would conclude this, and from what):")
        for line in lines:
            _say(w, f"  {line}")


def _read(w) -> None:
    for entity, wanted in w.each(ReadWanted):
        w.destroy(entity)
        path = os.path.expanduser(wanted.path)
        try:
            source = open(path, encoding="utf-8").read()
        except OSError as error:
            _say(w, f"cannot read {wanted.path}: {error.strerror}")
            continue
        try:
            from loopingrules.loop import Loop

            from pystrider import patterns, strict
            from pystrider.emit import Unrenderable, emit
            from pystrider.intake import ForStmt, Function, intake
            from pystrider.patterns import Iteration
            loop = Loop()
            patterns.install(loop)
            taken = intake(source, loop.world, path)
            strict.run(loop)
        except Exception as error:                     # noqa: BLE001
            _say(w, f"could not read {wanted.path}: {error!r}")
            continue
        functions = list(loop.world.each(Function))
        loops = [e.id for e, _tag in loop.world.each(ForStmt)]
        described = [n for n in loops if loop.world.has(n, Iteration)]
        _say(w, f"{os.path.basename(path)}: {len(functions)} "
                f"functions, {len(loops)} loops, {len(described)} "
                f"recognized as iterations")
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
                    f"{emit(loop.world, taken.module) == source}")
        except Unrenderable as refusal:
            _say(w, f"  refuses to write it back: "
                    f"{str(refusal).split(' — ')[-1]}")


def propose_help_python(w) -> None:
    """`help python` -> a candidate carrying this domain's own summary.
    `HelpTopic` is `harneskills.help`'s occasion, not this module's own
    goals above -- see that module's docstring, and this file's own
    note on the new dependency it is."""
    for occasion, topic in w.each(HelpTopic):
        if topic.topic == "python":
            w.spawn(Proposal(occasion.id), HelpAnswer(
                "blocks, brew [irreversible|basic|premium] [spend N] "
                "[drive], why <subject> <predicate> <object>, "
                "read <path.py>"))


#: ⚠ `hear` first, then one handler per goal — the order IS the schedule, and a
#: goal spawned this tick is answered on the next one. `propose_help_python`
#: is not part of that schedule at all -- it answers `harneskills.help`'s own
#: occasion, arbitrated there, not here.
RULES = (hear, _blocks, _brew, _why, _read, propose_help_python)


def install(loop) -> None:
    """Register the rules and teach the prompt this domain's words.

    ⚠ Nothing is spawned here. Unlike `harneskills.examples.fs`, this domain has no
    standing model to reconcile against a restored world — every derivation builds
    its own `Loop`/`World` and discards it, so there is nothing that could come
    back stale.
    """
    for rule in RULES:
        loop.rule(rule)
    loop.world.learn(*WORDS)
