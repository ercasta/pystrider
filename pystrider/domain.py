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
    watch <path.py> <name>   durably track one function's loop count -- see
                            `WatchedFunction`'s own docstring for why this is
                            the domain's first fact that survives a restart

## 2026-08-30: `read` moved into the SHARED world — `@transient` is what made it safe

Until this date, `_read` spun up a whole private `Loop`/`World`, ran `intake()`
and `patterns` in it, read off what it needed, and threw the rest away — because
the shared world is PERSISTED (`loopingrules.save` writes it on every settle) and
intaking one Python file spawns a few hundred entities, none of which anyone
wants in `world.json`. That reasoning was correct and is recorded, in more
detail, in `docs/TODO.md`'s "2026-08-30" sections — worth reading for the
argument this rewrite is the payoff of, not repeated here.

What changed: `loopingrules.world` grew `@transient` — a component class can be
marked disposable, and `loopingrules.save.dump()` skips every instance of it, so
it never reaches `world.json` regardless of which world it lives in. Every
component `intake.py`/`patterns.py`/`spans.py` declare is marked this way now
(see `intake.py`'s own transient block). So the SIZE reason above no longer
forces a private world — `read <path.py>` now intakes straight into `w`, the
one this domain's own rules already share with `harneskills.examples.fs` and
everyone else on the prompt, and `patterns` is installed on the SAME loop
(`install`, below) rather than a throwaway one per call.

⭐⭐ **THERE USED TO BE A SECOND REASON AND IT IS FIXED TOO, so do not cite it
either.** An earlier `save` could not read a generic relation back at all — see
`intake.py`'s own history note. Long fixed; not why anything here works the way
it does.

⭐ **This is not "code facts durably compose with business rules now."** They
don't, and can't yet — `@transient` means these entities are still gone the
moment nothing holds their ids any more (`purge_transient`, not yet called by
anything here — nothing has needed to reclaim the memory yet), and NOTHING
durable is allowed to hold one of their raw ids in the first place (see
`loopingrules.world.transient`'s own docstring). What a durable fact reaches for
instead is `pystrider.resolve` — a stable key (`path`, function `name`),
resolved to a live entity ONLY where the work happens. Nothing in this domain
writes a durable code fact yet; `resolve.resolve_function` exists for the day
something does, verified today only by re-reading the SAME path twice and
confirming the second read is not a duplicate (`resolve.forget`'s whole job).

### `_read`/`_report_read`: two rules, not one, and the order between them is load-bearing

`_read` intakes and reports everything that does NOT depend on `patterns` having
run yet (function/loop counts, the round-trip check) — but `Iteration`, patterns'
own conclusion, is not attached to anything the SAME tick `_read` mints it,
because `Loop.tick()` calls every registered rule once, in order, and a write is
visible to whatever runs AFTER it in that same pass, not to whatever already ran.
Reporting "N loops, M recognized as iterations" inside `_read` itself would read
`Iteration` before `patterns` had its turn — so `_read` instead spawns a
`ReadDone` marker (transient) and a SECOND rule, `_report_read`, reads it back
and reports.

Two invariants make that correct, and both are enforced in `install()`, below,
not by accident of file order:

1. `_read` must run BEFORE `patterns`'s rules, in the SAME tick, so `patterns`
   sees this tick's freshly-minted entities rather than missing them by one
   tick — `install()` gets this from REGISTRATION order (`_read` registered
   before `patterns.install(loop)` is called), both at the same default
   priority.
2. `_report_read` must run AFTER `patterns`'s rules, in the SAME tick,
   regardless of registration order — `install()` gets this from an EXPLICIT
   lower `priority`, because relying on registration order for this side too
   would silently break the day someone reorders the two `install()` lines
   without knowing why they were ordered that way.

Also scoped by `path`, not just by kind: `w.each(Function)` today may hold
functions from every file this session has ever `read`, not just the one just
read (the shared world does not forget on its own — see `resolve.forget`) — so
`_report_read` filters every query by `Origin(path) == done.path`. The private-
world version never needed this, because a private `World` never held more than
one file's worth of anything.

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

## `help python` answers `loopingrules.help`'s occasion, not `harneskills`'s

`hear`'s own docstring above says this domain shares one world with
`harneskills.examples.fs` "without either domain having to know the other's
vocabulary" — still true, `propose_help_python` included: `HelpTopic`/
`HelpAnswer` come from `loopingrules.help`, the substrate this package
already depends on unconditionally, not from `harneskills`.

⚠ That module lived in `harneskills.help` for about a day first, and
this package DID import it from there briefly — the wrong call, caught
the same day: this domain is meant to be host-agnostic, installable
under any harness that runs a `loopingrules.Loop`, and depending on
`harneskills` specifically (rather than on the substrate every domain
already sits on) tied it to one host it should not need to know
exists. `help` is one occasion two independently-installed domains
both want to answer, and neither `fs` nor `pystrider` is the other's
to import from — `loopingrules` is the thing BOTH unconditionally
depend on already, which `harneskills` never was for this package. See
`loopingrules.help`'s own docstring for the full argument and
`loopingrules.world.arbitrate` for the mechanism that makes answering
an occasion this module did not create safe regardless of which
domain's `install()` the config lists first.

`propose_help_census_python` answers a SECOND `loopingrules.help`
occasion, `HelpCommandCensus` -- what a bare `help` becomes now, not a
topic anyone typed. `arbitrate_help`'s "one winner" contest is the
wrong shape for it (nothing here rivals `fs`'s own answer for a bare
`help`; both are real at once), so it goes through `loopingrules.world.
census` instead -- see `loopingrules.help`'s own docstring, "The
shape, for a bare help," for why that needed a different mechanism
than `arbitrate`.
"""
from __future__ import annotations

import os
import traceback
from dataclasses import dataclass, replace

from loopingrules.help import HelpAnswer, HelpCommandCensus, HelpTopic, HelpTopicName
from loopingrules.world import Proposal, Reply, Said, propose, transient

#: What the prompt should pull a typo towards. `world.learn` is autocorrect only —
#: nothing here changes what a rule finds.
WORDS = ("blocks", "brew", "why", "read", "watch", "drive", "irreversible",
         "basic", "premium", "spend", "python")


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


@transient
@dataclass(frozen=True)
class ReadDone:
    """Bridges `_read` (the intake phase) to `_report_read` (the report
    phase, once `patterns` has had this tick's turn too) — see this
    module's own docstring, "`_read`/`_report_read`," for why this is two
    rules and not one. `path` is `Intaken.origin` — already the expanded
    path `Origin` components in `w` carry, so `_report_read` can filter by
    it directly. `roundtrip_line` is precomputed in `_read` because it does
    NOT depend on `patterns` — only the loop/iteration count does.

    `@transient`, same reasoning as `intake.py`'s own components even
    though nothing here comes FROM `intake.py`: a report still in flight,
    meant to be gone within the tick that spawned it, and disposable if
    something ever leaves it standing longer than that (a rule that raised
    before `_report_read` got to consume it, say) — see
    `loopingrules.world.transient`'s own docstring on what the marker
    actually promises; it was never only about code-derived data."""

    path: str
    module: int
    unmodelled: tuple
    roundtrip_line: str


@dataclass(frozen=True)
class WatchWanted:
    path: str
    name: str


@dataclass(frozen=True)
class WatchedFunction:
    """This domain's first DURABLE, stable-keyed business fact — a
    person's standing interest in one function, by `(path, name)`, never
    by any entity id `intake()` ever minted. Survives a restart (ordinary
    module-level class, `getattr`-resolvable, ⚠ same as `ReadWanted`'s
    own neighbors) — the whole point `pystrider.resolve` exists for: on
    restart, every `@transient` entity this fact could have pointed at is
    simply gone, and `_reconcile_watch` (below) is what finds the SAME
    function again, resolved fresh, not restored.

    `path` is stored already-expanded (`_understand` does it, matching
    `resolve.resolve_function`'s own normalization) so a later `==`
    against `Origin.value` — which is always the expanded form — is a
    plain string compare, not a path-equivalence problem this class would
    otherwise have to solve twice."""

    path: str
    name: str


@dataclass(frozen=True)
class FunctionStatus:
    """`_reconcile_watch`'s own conclusion about one `WatchedFunction` —
    kept singular via `w.replace()` (the CURRENT answer, not a history of
    them), and re-derived through `pystrider.resolve` every time
    `WatchedFunction` might have something new to say, never by holding
    the entity `resolve_function` last handed back. Durable, same as
    `WatchedFunction` — this is the payoff `docs/TODO.md` thread 2 named
    as unverified: a business fact surviving a forget-and-reread (or a
    whole restart) because it was never holding a raw id to begin with."""

    path: str
    name: str
    exists: bool
    loops: int


def _say(w, text: str) -> None:
    w.spawn(Reply("user", text))


def _loops_in(w, function) -> int:
    """How many `for` statements sit DIRECTLY in `function`'s own body —
    not recursing into a nested block (an `if`'s body, a nested `def`),
    a real, named simplification: "how many loops does this function
    have," not "how many loops does its whole subtree have." Needs
    nothing from `patterns` — raw `intake.py` structure (`Body`/`Stmt`/
    `ForStmt`) is enough to count, unlike `_report_read`'s `Iteration`
    check, so `_reconcile_watch` needs no two-phase split the way
    `_read`/`_report_read` did."""
    from pystrider.intake import Body, ForStmt, Stmt
    body = w.get(function, Body)
    if body is None:
        return 0
    return sum(1 for stmt in w.get_all(w.entity(body.entity), Stmt)
              if w.has(w.entity(stmt.entity), ForStmt))


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

    if verb == "watch" and len(rest) == 2:
        w.spawn(WatchWanted(os.path.expanduser(rest[0]), rest[1]))
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
    # ⚠ TODO: recognition only -- installs `patterns` (below, in `install`),
    # never `repair`, and spawns no `Wants`/`Case`. `repair.py`'s rebuilt
    # relax/lower is verified by its own suite and by hand, not by anything
    # typed here yet -- see `repair.py`'s own "Where this goes next."
    #
    # ⚠⚠ Reports nothing itself past the read/intake errors below -- see this
    # module's own docstring, "`_read`/`_report_read`," for why the actual
    # summary is a SEPARATE rule reading `ReadDone` back, not this one.
    for entity, wanted in w.each(ReadWanted):
        w.destroy(entity)
        try:
            from pystrider import resolve
            from pystrider.emit import Unrenderable, emit
            taken, source = resolve.reread(w, wanted.path)
        except OSError as error:
            _say(w, f"cannot read {wanted.path}: {error.strerror}")
            continue
        except Exception as error:                     # noqa: BLE001
            _say(w, f"could not read {wanted.path}: {error!r}")
            continue
        try:
            roundtrip_line = ("  round-trips byte-exact against the "
                              f"source: {emit(w, taken.module) == source}")
        except Unrenderable as refusal:
            roundtrip_line = ("  refuses to write it back: "
                              f"{str(refusal).split(' — ')[-1]}")
        w.spawn(ReadDone(path=taken.origin, module=taken.module,
                         unmodelled=taken.unmodelled,
                         roundtrip_line=roundtrip_line))


def _report_read(w) -> None:
    """The other half of `_read` — see this module's own docstring. Runs
    strictly AFTER `patterns` has had this tick's turn (`install()`'s own
    `priority=`), so `Iteration` is already attached to whatever this read
    is about to report on.

    ⚠ Filters every query by `Origin(path) == done.path` -- `w` may hold
    entities from every file this session has ever `read`, not just this
    one (the shared world does not forget on its own), which the private-
    world version never had to account for."""
    from pystrider.intake import ForStmt, Function, Origin
    from pystrider.patterns import Iteration
    for entity, done in w.each(ReadDone):
        w.destroy(entity)
        functions = [f for _e, origin, f in w.each(Origin, Function)
                    if origin.value == done.path]
        loops = [e.id for e, origin, _tag in w.each(Origin, ForStmt)
                if origin.value == done.path]
        described = [n for n in loops if w.has(n, Iteration)]
        _say(w, f"{os.path.basename(done.path)}: {len(functions)} "
                f"functions, {len(loops)} loops, {len(described)} "
                f"recognized as iterations")
        if done.unmodelled:
            counts: dict = {}
            for name in done.unmodelled:
                counts[name] = counts.get(name, 0) + 1
            named = ", ".join(f"{k}x{v}" if v > 1 else k
                              for k, v in sorted(counts.items()))
            _say(w, f"  unmodelled ({len(done.unmodelled)}): {named}")
        else:
            _say(w, "  nothing unread")
        _say(w, done.roundtrip_line)


def _watch(w) -> None:
    """`watch <path.py> <name>` -> a durable `WatchedFunction`, unless one
    already answers to this `(path, name)` — `watch` said twice is not two
    standing interests, it is one, reported again."""
    for entity, wanted in w.each(WatchWanted):
        w.destroy(entity)
        already = any(existing.path == wanted.path and existing.name == wanted.name
                      for _e, existing in w.each(WatchedFunction))
        if already:
            _say(w, f"already watching {wanted.name} in "
                    f"{os.path.basename(wanted.path)}")
            continue
        w.spawn(WatchedFunction(wanted.path, wanted.name))
        _say(w, f"now watching {wanted.name} in {os.path.basename(wanted.path)}")


def _reconcile_watch(w) -> None:
    """The standing model `install()`'s own docstring says this domain
    otherwise lacks — every `WatchedFunction` gets its `FunctionStatus`
    kept current, resolved FRESH through `pystrider.resolve` every time
    this runs, never by holding on to whichever entity `resolve_function`
    happened to hand back last (see `WatchedFunction`'s own docstring for
    why: that entity is `@transient` and may already be gone).

    Reports only on an actual CHANGE (`FunctionStatus` compares by value,
    same as everything else in this world) — first resolution included,
    since `before` reads `None` then — not once a tick forever just
    because `WatchedFunction` still exists. Gated by `watches=` in
    `install()`, so this costs nothing on any tick nobody is watching
    anything.
    """
    from pystrider import resolve
    for entity, watched in w.each(WatchedFunction):
        before = w.get(entity, FunctionStatus)
        function = resolve.resolve_function(w, watched.path, watched.name)
        if function is None:
            after = FunctionStatus(watched.path, watched.name,
                                   exists=False, loops=0)
        else:
            after = FunctionStatus(watched.path, watched.name, exists=True,
                                   loops=_loops_in(w, function))
        if after == before:
            continue
        w.replace(entity, after)
        base = os.path.basename(watched.path)
        if after.exists:
            _say(w, f"{watched.name} in {base}: {after.loops} loop(s)")
        else:
            _say(w, f"{watched.name} in {base}: no longer found")


def propose_help_python(w) -> None:
    """`help python` -> a candidate carrying this domain's own summary.
    `HelpTopic` is `loopingrules.help`'s occasion, not this module's own
    goals above -- see that module's docstring, and this file's own
    note on the new dependency it is."""
    for occasion, topic in w.each(HelpTopic):
        if topic.topic == "python":
            w.spawn(Proposal(occasion.id), HelpAnswer(
                "blocks, brew [irreversible|basic|premium] [spend N] "
                "[drive], why <subject> <predicate> <object>, "
                "read <path.py>"))


def propose_help_census_python(w) -> None:
    """A bare `help` -> this domain offers `python` for the list, not a
    candidate to win anything -- see this file's own docstring, "a
    SECOND `loopingrules.help` occasion." `propose`, not `w.spawn
    (Proposal(...), ...)` by hand: `loopingrules.world`'s own one-line
    spelling of it."""
    for occasion, _census in w.each(HelpCommandCensus):
        propose(w, occasion, HelpTopicName("python"))


#: ⚠ `hear` first, then one handler per goal — the order IS the schedule, and a
#: goal spawned this tick is answered on the next one. `propose_help_python`/
#: `propose_help_census_python` are not part of that schedule at all -- they
#: answer `loopingrules.help`'s own occasions, resolved there, not here.
#: `_report_read`/`_reconcile_watch` are ALSO not here -- `install()` registers
#: both separately, with an explicit `priority`/`watches`, since neither's
#: place in the schedule is "somewhere after" a goal handler in this tuple --
#: see this module's own docstring and each rule's own.
RULES = (hear, _blocks, _brew, _why, _read, _watch, propose_help_python,
         propose_help_census_python)


def install(loop) -> None:
    """Register the rules, install `patterns` onto the SAME loop, and teach
    the prompt this domain's words.

    ⚠ The two lines below are not interchangeable in order, and neither is
    an accident -- see this module's own docstring, "`_read`/`_report_read`":
    `RULES` (which includes `_read`) must be registered BEFORE
    `patterns.install(loop)`, so that within one tick, `_read` runs first
    and `patterns` sees what it just minted; `_report_read` is registered
    with a `priority` BELOW every default-priority rule (`_read` and
    `patterns` both included) precisely so it does not also need to worry
    about which of these two lines came first.

    ⚠⚠ 2026-08-30, later still: this domain now DOES have a standing model
    to reconcile against a restored world after all -- `WatchedFunction`/
    `FunctionStatus` (`watch <path.py> <name>`), the first durable,
    stable-keyed fact this domain owns. `_reconcile_watch` is what
    reconciles it, `watches=(WatchedFunction,)` so it costs nothing on any
    tick nobody is watching anything -- see its own docstring for why this
    IS the `harneskills.examples.fs`-style standing model the older note
    below said this domain lacked. Everything `patterns`/`intake.py` mint
    is still `@transient` (never reaches `world.json` regardless of which
    world they live in, see `loopingrules.world.transient`) -- that part of
    the older claim still holds; only "nothing durable is spawned here" no
    longer does.
    """
    for rule in RULES:
        loop.rule(rule)
    loop.rule(_report_read, priority=-1)
    # `priority=-2`, one below `_report_read`'s -1 -- purely for reading
    # order: a `read` that happens to jog a watched function's status
    # should report its OWN summary before the side effect that noticed,
    # not the other way around. No data dependency requires this (unlike
    # `_report_read`'s own -- `_reconcile_watch` never reads `Iteration`
    # or anything `patterns` produces), only the prompt reading naturally.
    loop.rule(_reconcile_watch, watches=(WatchedFunction,), priority=-2)
    from pystrider import patterns
    patterns.install(loop)
    loop.world.learn(*WORDS)
