"""Achieving a wanted effect — the half of the bet `effects.py` explicitly
declines, built the way `repair.py` now is: propose, arbitrate, apply. See
`docs/decision_patterns.md` for the argument and `repair.py`'s own module note
for why this is not backward-reading a recognizer.

⚠⚠ DELIBERATELY NARROW, THE SAME WAY `repair.py` SAYS OF ITSELF. This
synthesizes exactly one new statement — a zero-argument call, always appended
at the END of a function's body, never before an existing `return` — chosen
from a small, authored family of ways to give a function an `io` effect it
does not have. No argument selection, no choice of where in the body to
insert, no handling of `mutates` effects at all. The point is the wiring, not
the coverage.

⭐⭐ THE ACHIEVED EFFECT IS NEVER ASSERTED HERE. Once a family attaches the new
`Call`/`Stmt` components, `effects.py`'s own `contains`/`calls_effectful` —
installed on the SAME loop — re-derive `Effect(function, "io", ...)` from the
new structure on a later tick, exactly as they would for a call someone
actually typed. Nothing in this module says the word "effect".

⚠⚠ RUN THE LOOP ONCE FOR `effects.install` ALONE BEFORE INSTALLING THIS
MODULE, OR THE DIAGNOSIS RACES ITS OWN EVIDENCE. `contains` is a multi-tick
transitive closure (`effects.py`'s own note says so) — on the very first
tick, a function that ALREADY calls `print` has not been recognized as having
an `io` effect yet, only as having a body. `diagnose` reading `Effect(...)` at
that moment sees nothing and wrongly proposes a repair for a function that did
not need one. Running to a settle first (an ordinary `Loop.run()` call —
`install`/`run` may be called more than once on the same loop) means
`Effect(...)` is accurate before this module's diagnosis ever looks at it.
`test_a_function_that_already_calls_print_is_left_alone` is what this
protects.

⚠⚠ 2026-08-29: `arbitration.commit` is gone from upstream — deleted outright,
not ported. `arbitrate` below is this module's OWN small reader, the same
shape `repair.arbitrate` uses and deliberately NOT shared with it: a function
could in principle be an occasion for both modules at once, and one shared
`Candidate`/`Winner` type would let the two arbitrations read each other's
proposals by accident. Two rivals genuinely competing (`via_print` never
checks whether `via_open` also applies) is exactly the case
`docs/decision_patterns.md` argues needs this shape, not the trivial
"first wins" `harneskills.examples.fs.arbitrate_parse` gets away with.
"""
from __future__ import annotations

from dataclasses import dataclass

from .effects import Effect
from .intake import Body, Call, Callee, Name, Readable, Stmt


@dataclass(frozen=True)
class WantsEffect:
    pass


@dataclass(frozen=True)
class MissingEffect:
    pass


@dataclass(frozen=True)
class EffectRepaired:
    pass


@dataclass(frozen=True)
class Candidate:
    name: str
    priority: int


@dataclass(frozen=True)
class Winner:
    name: str


@dataclass(frozen=True)
class Verdict:
    value: str


def diagnose(w) -> None:
    """`MissingEffect(function)` when `WantsEffect` holds and the function
    has no `io` effect yet — forward, off what `effects.py` already derived,
    the same shape `repair.diagnose` uses off `Evaluated`.
    """
    for function, _tag in w.each(WantsEffect, without=EffectRepaired):
        has_io = any(effect.kind == "io" for effect in w.get_all(function, Effect))
        if not has_io:
            w.attach(function, MissingEffect())


def _insert_call(w, function, callee_name: str) -> None:
    """Append `callee_name()` — zero arguments — as a new statement at the
    end of `function`'s body. Naive on purpose; see the module note."""
    block = w.get(function, Body).entity
    callee = w.spawn(Name(callee_name), Readable())
    call = w.spawn(Call(), Readable())
    w.attach(call, Callee(callee.id))
    w.attach(block, Stmt(call.id))


def via_print(w) -> None:
    """`print()` — safe to actually execute, and ranked above `via_open` for
    exactly that reason: an authored preference `via_print` states about
    itself, not a check on whether `via_open` also applies."""
    for function, _tag in w.each(MissingEffect, without=EffectRepaired):
        w.attach(function, Candidate("via_print", 2))
        winner = w.get(function, Winner)
        if winner is not None and winner.name == "via_print":
            _insert_call(w, function, "print")
            w.attach(function, EffectRepaired())


def via_open(w) -> None:
    """`open()` — an `io` effect by the same registry `effects.py` uses, but
    a zero-argument call raises at runtime. Kept as a genuine rival so
    arbitration has something to decide between, ranked below `via_print`,
    not a recommendation to ever call it this way."""
    for function, _tag in w.each(MissingEffect, without=EffectRepaired):
        w.attach(function, Candidate("via_open", 1))
        winner = w.get(function, Winner)
        if winner is not None and winner.name == "via_open":
            _insert_call(w, function, "open")
            w.attach(function, EffectRepaired())


#: ⚠ No tie-break lives here — see `Candidate.priority` inside each family.
#: This dict is just which ones exist to install, the same role it plays in
#: `repair.py`.
FAMILIES = {"via_print": via_print, "via_open": via_open}


def arbitrate(w) -> None:
    """This module's own local reader: for every function either family
    proposed a `Candidate` for, pick the highest priority — a tie is
    `Verdict("ambiguous")`. See `repair.arbitrate`, which this deliberately
    duplicates rather than shares — see the module note."""
    seen = set()
    for function, _candidate in w.each(Candidate):
        if function.id in seen:
            continue
        seen.add(function.id)
        candidates = w.get_all(function, Candidate)
        best = max(c.priority for c in candidates)
        top = [c for c in candidates if c.priority == best]
        if len(top) == 1:
            w.replace(function, Winner(top[0].name))
            w.replace(function, Verdict("forced"))
        else:
            w.detach(function, Winner)
            w.replace(function, Verdict("ambiguous"))


def install(loop, families=None) -> None:
    """The diagnosis and the two families, as rules — mirrors
    `repair.install`'s shape. `arbitrate` is registered once, after
    whichever families are installed.
    """
    loop.rule(diagnose, name="effects_repair.diagnose")
    installed = [name for name in FAMILIES if families is None or name in families]
    for name in installed:
        loop.rule(FAMILIES[name], name=f"effects_repair.{name}")
    if installed:
        loop.rule(arbitrate, name="effects_repair.arbitrate")
