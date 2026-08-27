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

⭐⭐ THE ACHIEVED EFFECT IS NEVER ASSERTED HERE. Once a family inserts the new
`call`/`stmt` facts, `effects.py`'s own `contains`/`calls_effectful` —
installed on the SAME loop — re-derive `effect(function, "io", ...)` from the
new structure on a later tick, exactly as they would for a call someone
actually typed. Nothing in this module says the word "effect".

⚠⚠ CALL `f.run()` ONCE FOR `effects.install` ALONE BEFORE INSTALLING THIS
MODULE, OR THE DIAGNOSIS RACES ITS OWN EVIDENCE. `contains` is a multi-tick
transitive closure (`effects.py`'s own note says so) — on the very first
tick, a function that ALREADY calls `print` has not been recognized as having
an `io` effect yet, only as having a body. `diagnose` reading `effect(...)` at
that moment sees nothing and wrongly proposes a repair for a function that did
not need one. Running `effects.install` to its OWN settle first (an ordinary
`Facts.run()` call — `install`/`run` may be called more than once on the same
`Facts`) means `effect(...)` is accurate before this module's diagnosis ever
looks at it. `test_a_function_that_already_calls_print_is_left_alone` is what
this protects.
"""
from __future__ import annotations

from .arbitration import commit
from .facts import Facts, relation

WantsEffect = relation("wants_effect")
MissingEffect = relation("missing_effect")
EffectRepaired = relation("effect_repaired")


def diagnose(f: Facts):
    """`missing_effect(function)` when `wants_effect` holds and the function
    has no `io` effect yet — forward, off what `effects.py` already derived,
    the same shape `repair.diagnose` uses off `evaluated`.
    """

    def system(world) -> None:
        for function, _ in world.each(WantsEffect, without=EffectRepaired):
            has_io = any(row[0] == f.word("io") for row in f.of("effect", function))
            if not has_io:
                f.fact("missing_effect", function)

    return system


def _insert_call(f: Facts, function, callee_name: str) -> None:
    """Append `callee_name()` — zero arguments — as a new statement at the
    end of `function`'s body. Naive on purpose; see the module note."""
    block = f.one("body", function)
    callee = f.node(f"name@synthesized:{callee_name}")
    f.fact("name", callee)
    f.fact("id", callee, f.word(callee_name))
    f.fact("readable", callee)
    call = f.node(f"call@synthesized:{callee_name}")
    f.fact("call", call)
    f.fact("callee", call, callee)
    f.fact("readable", call)
    f.fact("stmt", block, call)


def via_print(f: Facts):
    """`print()` — safe to actually execute, and ranked above `via_open` for
    exactly that reason: an authored preference `via_print` states about
    itself, not a check on whether `via_open` also applies."""

    def system(world) -> None:
        for function, _ in world.each(MissingEffect, without=EffectRepaired):
            f.fact("candidate", function, f.word("via_print"))
            f.fact("ranked", function, f.word("via_print"), f.value(2))
            if f.holds("winner", function, f.word("via_print")):
                _insert_call(f, function, "print")
                f.fact("effect_repaired", function)

    return system


def via_open(f: Facts):
    """`open()` — an `io` effect by the same registry `effects.py` uses, but
    a zero-argument call raises at runtime. Kept as a genuine rival so
    arbitration has something to decide between, ranked below `via_print`,
    not a recommendation to ever call it this way."""

    def system(world) -> None:
        for function, _ in world.each(MissingEffect, without=EffectRepaired):
            f.fact("candidate", function, f.word("via_open"))
            f.fact("ranked", function, f.word("via_open"), f.value(1))
            if f.holds("winner", function, f.word("via_open")):
                _insert_call(f, function, "open")
                f.fact("effect_repaired", function)

    return system


#: ⚠ No tie-break lives here — see `ranked` inside each family. This dict is
#: just which ones exist to install, the same role it plays in `repair.py`.
FAMILIES = {"via_print": via_print, "via_open": via_open}


def install(loop, f: Facts, families=None) -> None:
    """The diagnosis and the two families, as systems — mirrors
    `repair.install`'s shape. `arbitration.commit` is registered once, after
    whichever families are installed.
    """
    f.system(diagnose(f), name="effects_repair.diagnose")
    installed = [name for name in FAMILIES if families is None or name in families]
    for name in installed:
        f.system(FAMILIES[name](f), name=f"effects_repair.{name}")
    if installed:
        f.system(commit(f), name="arbitration.commit")
