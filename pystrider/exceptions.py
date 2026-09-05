"""Exceptions — recognizing code that MIGHT raise, and repairing it by
wrapping it in `try`/`except <Type>: raise`.

The first end-to-end slice through `docs/TODO.md`'s "general cycle" that
needs all four steps for real: `may_raise_*` is `effects.py`'s recipe
applied to a different risk (structure => description, forward, abstaining
structurally); the repair pipeline below is the generative half
`effects.py` itself declines, the same "propose a target semantics, then
synthesize it" shape `repair.py`/`effects_repair.py` already use for a
statement-level repair — the first module here to synthesize a whole new
BLOCK-CARRYING construct (`try`/`except`), which needed `intake.py`/
`emit.py` to grow `TryStmt`/`ExceptHandler`/`RaiseStmt` first (see those
modules' own notes).

⚠ DELIBERATELY NARROW, NAMED, NOT HIDDEN:
  - Only `x / y` / `x // y` where `y` is anything but a bare `Constant`
    (risking `ZeroDivisionError`), and `int(x)`/`float(x)` where `x` is
    anything but a bare `Constant` (risking `ValueError`) — a literal
    argument either way is a different question (dead code /
    guaranteed-raise), not attempted here.
  - Only an EXACT `except <Type>:` counts as a guard — no `as` binding, no
    tuple of types, no bare `except:`, no broader supertype (`Exception`,
    `ArithmeticError`). A risk inside `except SomeOtherType:` is
    (correctly, for this scope) still wrapped — a second, nested `try`,
    not a bug.
  - Never wraps more than one STATEMENT per `try` — deliberately dodges the
    open "which span does one `try` cover" question
    `loopingrules/DECISION_PATTERNS.md`'s 2026-08-30/31 notes flag as
    unresolved (the chart-parsing shape), rather than pre-empting it.
  - Does not consult `symbolic.known_value` to rule out an argument that is
    provably safe despite not being a bare `Constant` — a natural
    follow-on, not this slice.

⭐⭐ 2026-09-05: WIRED TO THE LIVE PROMPT — `pystrider.domain`'s `harden
<path.py>` installs nothing (this module's rules are STANDING, registered
once by `domain.install()`, same as `patterns.install`); it asserts
`WantsHardening(path)`, the gate the repair pipeline reads below.
`may_raise_*`/`guarded` were already unconditional and safe to run
globally; the repair rules were NOT, before that gate existed — see
`WantsHardening`'s own docstring for why that only became visible once
something outside this module's own tests ever called it.

⭐⭐ 2026-09-05, later the same day: REBUILT ON PROPOSE/ARBITRATE/APPLY, a
second risk kind added specifically to force the question. `wrap_in_try`
(gone now) diagnosed and applied in one step, correctly, for exactly as
long as exactly one repair family existed — its own docstring said so
plainly. The moment a SECOND risk (`int`/`float`, above) can land on the
SAME statement as the first, that shortcut stops being innocent: nesting
one `try` per risk, in whatever order two independent rules happen to run,
is not obviously the fix anyone wants, and nothing had ever DECIDED it was
— `docs/TODO.md`'s own "there are NO mechanical transformations... always a
passage through semantics" names exactly this failure mode. So there are
now two rival families, `propose_per_issue`/`propose_combined`, and a local
`arbitrate_repair`/`Candidate`/`Winner` — the SAME shape `effects_repair.py`
already established (`Candidate`/`Winner`/`arbitrate`, local to the module,
deliberately not shared with `repair.py`'s own, for the identical reason:
two independently-evolving modules must not read each other's proposals by
accident of a shared type). `per_issue` (today's original mechanism,
renamed, priority 1) is kept as a genuine, fully-working rival that
`combined` (one `try`, one `except` per distinct risk, priority 2) always
outranks — the same role `effects_repair.via_open` already plays for a
different pair of families: a losing candidate that is still real code,
provably reachable via `install(..., only=...)`, not a code path removed
because it never wins by default.

⭐⭐ 2026-09-05, later still: THE FIRST CUT OF THAT REBUILD PUT THE GATE IN
THE WRONG PLACE, caught the same session on a straight read of what "not
touching individual rules" actually requires. `propose_per_issue`,
`propose_combined`, AND `apply_repair` each independently re-walked
`_enclosing_stmt` and re-applied `WantsHardening`/`Guarded`/`Repaired`
themselves — three call sites re-deriving one fact, which is not a seam,
it is the same logic pasted three times with different endings. `group_
risks` (below) is the actual fix: ONE rule does the gated walk, deposits
the answer as an ordinary edge (`RiskOn`), and every rule downstream reads
that edge the way it reads `Stmt`/`Arg` — knowing nothing about the three
gates at all. See that section's own note for the precedent this follows
(`effects_repair.diagnose` -> `MissingEffect` -> `via_print`/`via_open`,
diagnose once, consume many times) and why it is the right shape for
introducing arbitration into a set of rules without touching or re-guarding
each one.

⚠⚠ THE SPLICE IS NEW GROUND (unchanged from the first slice, still true).
Every earlier synthesized repair (`effects_repair._insert_call`) only ever
APPENDS a new statement at the end of a body — `World.attach` on a
multi-valued, ordered component (`Stmt`) only ever appends, never inserts.
Replacing one statement IN PLACE while keeping its siblings' order needs a
full read/detach/reattach of the block's own `Stmt` bucket, done once here
(`_splice_try`) rather than folded into a generic-looking helper that would
hide how narrow this still is.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .intake import (Arg, Arithmetic, Block, Body, Call, Callee, Constant,
                     ExceptHandler, Handler, Name, Origin, Readable,
                     RaiseStmt, Right, Stmt, TryStmt)
from .symbolic import _parent_of


@dataclass(frozen=True)
class MayRaise:
    """`exc_type`/`detail` name the risk this is about, not just a bare
    flag — `MayRaise("ZeroDivisionError", "div")` — the same "name what,
    not just that" discipline `effects.Effect` already follows. `exc_type`
    is the literal Python exception class name, read directly by `guarded`
    and the repair pipeline below — not a `kind` tag some other table has
    to translate."""

    exc_type: str
    detail: str


@dataclass(frozen=True)
class Guarded:
    """An ancestor `except <exc_type>:` already covers this risk."""


@dataclass(frozen=True)
class Repaired:
    """This `MayRaise` has already been wrapped — durable, unlike
    `repair.py`'s own `Repaired`-by-retraction shape, because the apply step
    here performs irreversible AST surgery: re-running it on an entity
    already wrapped would not just be redundant, it would be wrong (the
    entity it would try to move has already moved)."""


@dataclass(frozen=True)
class WantsHardening:
    """A standing request: repair every `MayRaise` found under this path,
    not just report it — the desired-semantics step `docs/TODO.md`'s cycle
    names, and the same gating role `effects_repair.WantsEffect` plays for
    that module's own repair. `may_raise_*`/`guarded` stay unconditional
    and global (recognition is cheap, pure, and harmless to run for every
    file, same as `effects.py`'s own `contains`/`calls_effectful`) — only
    the repair pipeline, the code-MUTATING half, is gated on this.

    Durable (no `@transient`) and keyed by PATH, never by an entity id —
    same reasoning as `pystrider.domain.WatchedFunction`'s own docstring:
    intake's entities are transient and gone on every reread, so a standing
    request cannot point at one."""

    path: str


# -- recognize ---------------------------------------------------------------

def may_raise_zero_division(w) -> None:
    """`Arithmetic("div"/"floordiv")` whose divisor is not a bare
    `Constant` — the entire recognizer, on purpose. Silence here never means
    "provably safe," only "not this narrow pattern.\""""
    for entity, arith in w.each(Arithmetic):
        if arith.operator not in ("div", "floordiv"):
            continue
        right = w.get(entity, Right)
        if right is None or w.has(right.entity, Constant):
            continue
        w.attach(entity, MayRaise("ZeroDivisionError", arith.operator))


#: `int`/`float` NAMES this recognizes as raising `ValueError` on a bad
#: argument — a REGISTRY, not an inference, same posture as `effects.
#: IO_NAMES`: that these two convert and can fail is knowledge about the
#: builtins, not something the syntax alone reveals.
_VALUE_ERROR_CALLEES = {"int", "float"}


def may_raise_value_error(w) -> None:
    """`int(x)`/`float(x)`, exactly one argument, that argument not a bare
    `Constant` — a call with zero or two-or-more arguments (`int(x, base)`,
    a real, differently-shaped call this recognizer has no opinion about)
    is refused, not guessed at."""
    for entity, _tag in w.each(Call):
        callee = w.get(entity, Callee)
        if callee is None:
            continue
        name = w.get(callee.entity, Name)
        if name is None or name.id not in _VALUE_ERROR_CALLEES:
            continue
        args = w.get_all(entity, Arg)
        if len(args) != 1 or w.has(args[0].entity, Constant):
            continue
        w.attach(entity, MayRaise("ValueError", f"{name.id}_call"))


# -- diagnose: is it already guarded? -----------------------------------------

def _enclosing_stmt(w, entity: int) -> Optional[Tuple[int, int]]:
    """`(block, statement)` — the block `entity` is (transitively) part of,
    and the member of THAT block's own `Stmt` list that contains it (itself,
    if it already is one). `None` if `entity` is unreachable from any
    block's `Stmt` list at all. Same generic-walker shape as `symbolic.
    _owning_statement`/`_enclosing` (`_parent_of`, one hop at a time,
    nothing construct-specific) — a local variant because the existing ones
    need the candidate list, or the target kind, handed in, and here
    neither is known ahead of the walk.

    ⚠ `entity` is normalized to a plain id UP FRONT — a caller may hand in
    the `Entity` HANDLE `w.each()` returns (every call site here does); a
    component field's own `.entity` is always already a plain id (`World.
    attach`'s own docstring), so leaving the handle unnormalized would make
    the very first membership check below silently never match (`Entity.
    __eq__` refuses a plain int on the other side, see `loopingrules.
    world.Entity`'s own docstring) whenever `entity` itself, not some
    ancestor of it, is the block member being looked for."""
    node = getattr(entity, "id", entity)
    seen = set()
    while node is not None and node not in seen:
        seen.add(node)
        parent = _parent_of(w, node)
        if parent is None:
            return None
        if any(s.entity == node for s in w.get_all(parent, Stmt)):
            return parent, node
        node = parent
    return None


def _guarding_try(w, entity: int, exc_type: str) -> bool:
    """Whether some ancestor block of `entity` is a `TryStmt`'s own `Body`,
    with a `Handler` naming EXACTLY `exc_type` — climbs past the nearest
    enclosing block, since the guard may sit several nesting levels up (an
    `if` inside a `try`, say)."""
    node = entity
    seen = set()
    while node is not None and node not in seen:
        seen.add(node)
        parent = _parent_of(w, node)
        if parent is None:
            return False
        for try_stmt, _tag in w.each(TryStmt):
            body = w.get(try_stmt, Body)
            if body is None or body.entity != parent:
                continue
            for h in w.get_all(try_stmt, Handler):
                clause = w.get(h.entity, ExceptHandler)
                if clause is not None and clause.exc_type == exc_type:
                    return True
        node = parent
    return False


def guarded(w) -> None:
    for entity, tag in w.each(MayRaise):
        if _guarding_try(w, entity, tag.exc_type):
            w.attach(entity, Guarded())


# -- the chokepoint: group which risks share a statement, ONCE ---------------
# ⭐⭐ THE SEAM. Every rule downstream of `group_risks` (`propose_per_issue`,
# `propose_combined`, `apply_repair`) reads `RiskOn` the way it would read
# `Stmt`/`Arg`/`Handler` — an ordinary structural fact — and knows NOTHING
# about `WantsHardening`, `Guarded`, or `Repaired`. That is deliberate, not
# an accident of what got refactored: the alternative (each of those three
# rules independently re-walking `_enclosing_stmt` and re-applying the same
# three gates) was tried first and rejected the same session it was built —
# three call sites quietly re-deriving one fact is not a seam, it is the
# same logic pasted three times with different endings. `effects_repair.py`'s
# own `diagnose` -> `MissingEffect` -> `via_print`/`via_open` is the
# precedent this follows: diagnose once, consume many times.

@dataclass(frozen=True)
class RiskOn:
    """`entity` (a `MayRaise` entity) applies to the statement this is
    attached to — multi-valued and UNORDERED (unlike `Stmt`/`Arg`: nothing
    downstream cares which risk on a statement was found first), the edge
    vocabulary shape `intake.py`'s `Handler`/`Arg` already establish,
    applied to a DERIVED relationship instead of a syntactic one."""

    entity: int


def group_risks(w) -> None:
    """THE CHOKEPOINT — see the section note above. Recomputes the full,
    correct `RiskOn` extension every tick (this module's usual "never
    cache" posture) but only touches a statement's own bucket when it
    actually changed, the same TMS discipline `symbolic.py`'s own
    `KnownValue`/`BoundTo` follow — so a settled world does not move
    `world.revision` just because this rule ran again, and a risk that
    becomes `Guarded`/`Repaired` after having been grouped is dropped from
    `RiskOn`, not left stale."""
    wanted = {h.path for _e, h in w.each(WantsHardening)}
    current: Dict[int, List[int]] = {}
    for entity, _tag in w.each(MayRaise, without=(Guarded, Repaired)):
        origin = w.get(entity, Origin)
        if origin is None or origin.value not in wanted:
            continue
        found = _enclosing_stmt(w, entity)
        if found is None:
            continue
        _block, stmt = found
        current.setdefault(stmt, []).append(entity.id)

    known = {s.id for s, _tag in w.each(RiskOn)}
    for stmt in known | set(current.keys()):
        target = sorted(current.get(stmt, []))
        existing = sorted(r.entity for r in w.get_all(stmt, RiskOn))
        if target == existing:
            continue
        w.detach(stmt, RiskOn)
        for entity_id in current.get(stmt, []):
            w.attach(stmt, RiskOn(entity_id))


# -- propose / arbitrate / apply ----------------------------------------------
# ⭐ Local to this module, deliberately not shared with `effects_repair.
# Candidate`/`Winner`/`arbitrate` even though the shape is identical — that
# module's own note already makes the argument: two independently-evolving
# modules must not be able to read each other's proposals by accident of a
# shared type.

@dataclass(frozen=True)
class Candidate:
    """One rival repair for a risky STATEMENT (the occasion)."""

    name: str
    priority: int


@dataclass(frozen=True)
class Winner:
    name: str


@dataclass(frozen=True)
class Verdict:
    value: str


@dataclass(frozen=True)
class StatementRepaired:
    """`apply_repair`'s own guard, keyed on the STATEMENT occasion rather
    than any one `MayRaise` — the per-entity `Repaired` mark alone is not
    enough here, because `apply_repair` acts on the whole GROUP at once,
    and `Candidate`/`Winner` are deliberately never cleaned up once
    resolved (`repair.py`'s own "a losing... `Candidate` is never
    destroyed" precedent), so the query they came from does not simply go
    empty on its own."""


def propose_per_issue(w) -> None:
    """One `try` per risk, nested — today's original mechanism, kept as a
    genuine, fully-working rival that `propose_combined` (below) always
    outranks, the same role `effects_repair.via_open` already plays for a
    different pair of families. Reads `RiskOn` alone — no gate of its own,
    all of that already happened at the seam (`group_risks`)."""
    seen = set()
    for stmt, _tag in w.each(RiskOn):
        if stmt.id in seen:
            continue
        seen.add(stmt.id)
        w.attach(stmt, Candidate("per_issue", 1))


def propose_combined(w) -> None:
    """ONE `try` wrapping the statement, one `except <Type>: raise` per
    DISTINCT exception type found on it — identical output to `per_issue`
    for a lone risk, and the whole point once ≥2 risks share a statement.
    Reads `RiskOn` alone, same as `propose_per_issue`."""
    seen = set()
    for stmt, _tag in w.each(RiskOn):
        if stmt.id in seen:
            continue
        seen.add(stmt.id)
        w.attach(stmt, Candidate("combined", 2))


def arbitrate_repair(w) -> None:
    """This module's own local reader — see `Candidate`'s own note on why
    it is not shared. Structural copy of `effects_repair.arbitrate`, keyed
    on the statement entity instead of a function."""
    seen = set()
    for stmt, _candidate in w.each(Candidate):
        if stmt.id in seen:
            continue
        seen.add(stmt.id)
        candidates = w.get_all(stmt, Candidate)
        best = max(c.priority for c in candidates)
        top = [c for c in candidates if c.priority == best]
        if len(top) == 1:
            w.replace(stmt, Winner(top[0].name))
            w.replace(stmt, Verdict("forced"))
        else:
            w.detach(stmt, Winner)
            w.replace(stmt, Verdict("ambiguous"))


def _splice_try(w, block: int, stmt: int, exc_types: List[str]) -> int:
    """Replace `stmt`, in place, inside `block`'s own `Stmt` list with a new
    `try: <stmt>` carrying one `except <Type>: raise` per entry in
    `exc_types`, all on the SAME `TryStmt` — `emit._try_stmt` already
    renders however many `Handler` edges one `TryStmt` carries (built
    generally in the first slice; `propose_combined`'s repair is the first
    caller to ever hand it more than one). Returns the new inner `Block`
    entity now containing `stmt` — `apply_repair`'s `"per_issue"` family
    nests by feeding this straight back in as the next call's `block`,
    `stmt` itself never moving again after this call returns.

    See the module note on why this needs a full detach/reattach of
    `block`'s own `Stmt` bucket rather than one `attach` call."""
    try_block = w.spawn(Block(), Readable())
    w.attach(try_block, Stmt(stmt))

    try_stmt = w.spawn(TryStmt(), Readable())
    w.attach(try_stmt, Body(try_block.id))
    for exc_type in exc_types:
        raise_stmt = w.spawn(RaiseStmt(), Readable())
        handler_block = w.spawn(Block(), Readable())
        w.attach(handler_block, Stmt(raise_stmt.id))
        handler = w.spawn(ExceptHandler(exc_type), Readable())
        w.attach(handler, Body(handler_block.id))
        w.attach(try_stmt, Handler(handler.id))

    ordered = [try_stmt.id if s.entity == stmt else s.entity
               for s in w.get_all(block, Stmt)]
    w.detach(block, Stmt)
    for e in ordered:
        w.attach(block, Stmt(e))
    return try_block.id


def apply_repair(w) -> None:
    """Reads `Winner` back and synthesizes it — the entities it repairs
    come straight off `RiskOn`, the same seam `propose_per_issue`/
    `propose_combined` read, not a re-walk. `block` is the one thing
    `RiskOn` does not carry (nothing downstream needed it until now); it is
    a single `_parent_of` hop off `stmt` itself — an adjacent structural
    fact, not the gated walk `group_risks` already did.

    Gated by `StatementRepaired` — see that component's own docstring for
    why `Repaired`/`RiskOn` going empty for this statement is not, by
    itself, enough of a guard."""
    for stmt, winner in w.each(Winner):
        if w.has(stmt, StatementRepaired):
            continue
        entities = [r.entity for r in w.get_all(stmt, RiskOn)]
        if not entities:
            continue
        block = _parent_of(w, stmt.id)
        if block is None:
            continue
        exc_types = sorted({w.get(e, MayRaise).exc_type for e in entities})
        if winner.name == "combined":
            _splice_try(w, block, stmt.id, exc_types)
        else:
            current_block = block
            for exc_type in exc_types:
                current_block = _splice_try(w, current_block, stmt.id, [exc_type])
        for entity in entities:
            w.attach(entity, Repaired())
        w.attach(stmt, StatementRepaired())


#: name -> (rule, watched types) -- explicit per-rule `watches=`, unlike
#: `effects.install`/`symbolic.install`'s own current gap (`docs/TODO.md`
#: names it as a known, not-yet-fixed cost there); nothing forces this
#: module to repeat it. ⚠ Every rule here watches only the type it reads to
#: decide whether to WAKE, not every type its body eventually touches --
#: `World.populated()` is an ANY-of-these check across the WHOLE world
#: (`loop.py`'s own docstring), not scoped to which entity changed, so once
#: e.g. `MayRaise` exists anywhere, a rule watching it is awake and
#: rescans its full antecedents every tick regardless of what else is in
#: the tuple -- adding more would cost nothing extra but claims a
#: precision this substrate cannot keep, so it is left out honestly.
_RULES = (
    ("may_raise_zero_division", may_raise_zero_division, (Arithmetic,)),
    ("may_raise_value_error", may_raise_value_error, (Call,)),
    ("guarded", guarded, (MayRaise,)),
    ("group_risks", group_risks, (MayRaise,)),
    ("propose_per_issue", propose_per_issue, (RiskOn,)),
    ("propose_combined", propose_combined, (RiskOn,)),
    ("arbitrate_repair", arbitrate_repair, (Candidate,)),
    ("apply_repair", apply_repair, (Winner,)),
)


def install(loop, only=None) -> None:
    """Register the rules. `only` names a subset — the control a test uses
    to force `per_issue` to win outright, by installing every rule except
    `propose_combined` (mirrors `effects_repair.install`'s own `families=`)."""
    for name, fn, watches in _RULES:
        if only is None or name in only:
            loop.rule(fn, name=f"exceptions.{name}", watches=watches)
