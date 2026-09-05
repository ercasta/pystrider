"""Exceptions — recognizing a division that MIGHT raise `ZeroDivisionError`,
and repairing it by wrapping it in `try`/`except ZeroDivisionError: raise`.

The first end-to-end slice through `docs/TODO.md`'s "general cycle" that
needs all four steps for real: `may_raise` is `effects.py`'s recipe applied
to a different risk (structure => description, forward, abstaining
structurally); `wrap_in_try` is the generative half `effects.py` itself
declines, the same "propose a target semantics, then synthesize it" shape
`repair.py`/`effects_repair.py` already use for a statement-level repair —
here for the first time synthesizing a whole new BLOCK-CARRYING construct
(`try`/`except`), which needed `intake.py`/`emit.py` to grow `TryStmt`/
`ExceptHandler`/`RaiseStmt` first (see those modules' own notes).

⚠ DELIBERATELY NARROW, NAMED, NOT HIDDEN:
  - Only `x / y` / `x // y` where `y` is anything but a bare `Constant` — a
    literal divisor (zero or not) is a different question (dead code /
    guaranteed-raise), not attempted here.
  - Only an EXACT `except ZeroDivisionError:` counts as a guard — no `as`
    binding, no tuple of types, no bare `except:`, no broader supertype
    (`Exception`, `ArithmeticError`). A division inside `except ValueError:`
    is (correctly, for this scope) still wrapped — a second, nested `try`,
    not a bug.
  - Never wraps more than one STATEMENT per `try` — deliberately dodges the
    open "which span does one `try` cover" question
    `loopingrules/DECISION_PATTERNS.md`'s 2026-08-30/31 notes flag as
    unresolved (the chart-parsing shape), rather than pre-empting it.
  - Does not consult `symbolic.known_value` to rule out a non-constant
    divisor that is provably nonzero — a natural follow-on, not this slice.
  - Not wired to the live prompt (`pystrider.domain`) yet — same honest gap
    `repair.py`'s own TODO names for itself.

⭐ NO `Proposal`/`Candidate`/`arbitrate` HERE, UNLIKE `effects_repair.py` —
deliberately. That machinery exists for RIVAL repair families genuinely
disagreeing about the same fact (`via_print` vs. `via_open`); there is
exactly one family here, so the general machinery `repair.py`/
`effects_repair.py` reach for would be unneeded weight for a fact nothing
disputes. `diagnose` (folded into `wrap_in_try` below) goes straight from
"unmet" to "applied," gated only by `Guarded`/`Repaired`.

⚠⚠ THE SPLICE IS NEW GROUND. Every earlier synthesized repair
(`effects_repair._insert_call`) only ever APPENDS a new statement at the end
of a body — `World.attach` on a multi-valued, ordered component (`Stmt`)
only ever appends, never inserts. Replacing one statement IN PLACE while
keeping its siblings' order needs a full read/detach/reattach of the block's
own `Stmt` bucket, done once here (`_splice_try`) rather than folded into a
generic-looking helper that would hide how narrow this still is.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .intake import (Arithmetic, Block, Body, Constant, ExceptHandler,
                     Handler, Readable, RaiseStmt, Right, Stmt, TryStmt)
from .symbolic import _parent_of


@dataclass(frozen=True)
class MayRaise:
    """`kind`/`detail` name the risk this is about, not just a bare flag —
    `MayRaise("zero_division", "div")` — the same "name what, not just
    that" discipline `effects.Effect` already follows."""

    kind: str
    detail: str


@dataclass(frozen=True)
class Guarded:
    """An ancestor `except ZeroDivisionError:` already covers this risk."""


@dataclass(frozen=True)
class Repaired:
    """This `MayRaise` has already been wrapped — durable, unlike
    `repair.py`'s own `Repaired`-by-retraction shape, because the apply step
    here performs irreversible AST surgery: re-running it on an entity
    already wrapped would not just be redundant, it would be wrong (the
    entity it would try to move has already moved)."""


# -- recognize ---------------------------------------------------------------

def may_raise(w) -> None:
    """`Arithmetic("div"/"floordiv")` whose divisor is not a bare
    `Constant` — the entire recognizer, on purpose. Silence here never means
    "provably safe," only "not this narrow pattern.\""""
    for entity, arith in w.each(Arithmetic):
        if arith.operator not in ("div", "floordiv"):
            continue
        right = w.get(entity, Right)
        if right is None or w.has(right.entity, Constant):
            continue
        w.attach(entity, MayRaise("zero_division", arith.operator))


# -- diagnose: is it already guarded? -----------------------------------------

def _enclosing_stmt(w, entity: int) -> Optional[Tuple[int, int]]:
    """`(block, statement)` — the block `entity` is (transitively) part of,
    and the member of THAT block's own `Stmt` list that contains it (itself,
    if it already is one). `None` if `entity` is unreachable from any
    block's `Stmt` list at all. Same generic-walker shape as `symbolic.
    _owning_statement`/`_enclosing` (`_parent_of`, one hop at a time,
    nothing construct-specific) — a local variant because the existing ones
    need the candidate list, or the target kind, handed in, and here
    neither is known ahead of the walk."""
    node = entity
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
    for entity, _tag in w.each(MayRaise):
        if _guarding_try(w, entity, "ZeroDivisionError"):
            w.attach(entity, Guarded())


# -- repair: synthesize the wrap ----------------------------------------------

def _splice_try(w, block: int, stmt: int) -> None:
    """Replace `stmt`, in place, inside `block`'s own `Stmt` list with a new
    `try: <stmt>\\n except ZeroDivisionError: raise` — see the module note
    on why this needs a full detach/reattach rather than one `attach`."""
    try_block = w.spawn(Block(), Readable())
    w.attach(try_block, Stmt(stmt))

    raise_stmt = w.spawn(RaiseStmt(), Readable())
    handler_block = w.spawn(Block(), Readable())
    w.attach(handler_block, Stmt(raise_stmt.id))

    handler = w.spawn(ExceptHandler("ZeroDivisionError"), Readable())
    w.attach(handler, Body(handler_block.id))

    try_stmt = w.spawn(TryStmt(), Readable())
    w.attach(try_stmt, Body(try_block.id))
    w.attach(try_stmt, Handler(handler.id))

    ordered = [try_stmt.id if s.entity == stmt else s.entity
               for s in w.get_all(block, Stmt)]
    w.detach(block, Stmt)
    for e in ordered:
        w.attach(block, Stmt(e))


def wrap_in_try(w) -> None:
    for entity, _tag in w.each(MayRaise, without=(Guarded, Repaired)):
        found = _enclosing_stmt(w, entity)
        if found is None:
            continue
        block, stmt = found
        _splice_try(w, block, stmt)
        w.attach(entity, Repaired())


#: name -> (rule, watched types) -- explicit per-rule `watches=`, unlike
#: `effects.install`/`symbolic.install`'s own current gap (`docs/TODO.md`
#: names it as a known, not-yet-fixed cost there); nothing forces this
#: module to repeat it. ⚠ `guarded`/`wrap_in_try` watch `MayRaise` alone,
#: not also `TryStmt`/`Guarded` -- `World.populated()` is an ANY-of-these
#: check across the whole world (`loop.py`'s own docstring), not scoped to
#: which entity changed, so once `MayRaise` exists anywhere both rules are
#: awake and rescan their full antecedents (including `TryStmt`, `Guarded`)
#: every tick regardless of what else is in the tuple -- adding those two
#: would cost nothing extra but claims a precision this substrate cannot
#: keep, so they are left out honestly rather than added for looks.
_RULES = (
    ("may_raise", may_raise, (Arithmetic,)),
    ("guarded", guarded, (MayRaise,)),
    ("wrap_in_try", wrap_in_try, (MayRaise,)),
)


def install(loop, only=None) -> None:
    """Register the rules. `only` names a subset, for a control."""
    for name, fn, watches in _RULES:
        if only is None or name in only:
            loop.rule(fn, name=f"exceptions.{name}", watches=watches)
