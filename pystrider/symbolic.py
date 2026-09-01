"""`pystrider.symbolic` — thread 6 ("mental run" analysis, `docs/TODO.md`).
Two independent value domains, both PURE derivers (no caching, no world
mutation) with a forward, structural ANNOTATION built on top of each
(`patterns.py`'s exact shape: structure => description, deposited as a
component) — not a request/answer pull like `evaluator.evaluate`, and
nothing here is keyed to a `Case`.

⭐ **`fold`/`KnownValue` — THE CEILING THIS DOMAIN DELIBERATELY SITS AT**:
constant folding — every operand traced back to a bare `Constant`, no `Name`
(bound or not) anywhere in the chain. This is the value domain with no
unbound symbols and no branches: the cheapest place to prove the annotation
shape (`KnownValue` on an expression entity) before asking it to reason
about what a `Name` is BOUND TO. A `Name` gets no `KnownValue` here, ever —
`fold` stays exactly this narrow even now that binding (below) exists
alongside it; they are two SEPARATE conclusions about two separate
questions ("what value" vs. "what expression"), not one growing to subsume
the other.

⭐ **`bound_to`/`BoundTo` — the second slice, built 2026-08-31**: what a
`Name` reference is BOUND TO, through `Assign` — the actual target the
first slice was scaffolding toward (resolving `f()` through
`f = some_function`, to find call sites through indirection). See
`bound_to`'s own docstring for the ceiling it sits at (exactly one
candidate `Assign`, same immediate block, preceding position — reassignment
and cross-branch binding both abstain, honestly, rather than guess which
assignment a flow-insensitive reading can't actually tell apart).

⭐ **`bound_function`/`BoundFunction` — one hop further, built 2026-09-01**:
`bound_to` stops at the bound EXPRESSION entity (a `Name`, returned as-is
by its own docstring's admission, "not chased to whatever function it
might itself name"). This is that chase, and it is where thread 6's
motivating case actually lands: `g = helper; g()` now resolves `g()`'s
`Callee` all the way to `helper`'s own `Function` entity, not just to the
`Name` node spelling "helper". Built on `pystrider.resolve.resolve_function`
— the seam that turns a stable `(path, name)` key back into a live entity
— called with the bound `Name`'s bare `.id` and `entity`'s own `Origin`,
never a dotted `Qualname` (a `Name` node has no scope information to spell
one with). Two separate abstention points, neither hidden: `bound_to`'s
own (unchanged), and "the bound expression is not a `Name` at all, or
names nothing `resolve_function` can find in the same file" (a constant, a
call result, an unresolvable name — nothing to chase, or nothing found).

⚠⚠ **WHY `fold` IS PURE, AND `known_value` REBUILDS EVERY TICK.** Found
2026-08-31, working through the TMS design (`docs/TODO.md`): `repair.py`'s
`apply` (`relax`/`lower`) mutates a `Comparison`/`Constant` IN PLACE via
`w.replace`, keeping the entity id (rewiring every edge that points at a
fresh id has no cheap answer here — no reverse index). The FIRST version of
this module cached `KnownValue` via `w.attach` gated on `without=KnownValue`
— which, once attached, never reconsidered the entity again, so a `repair`
that changed `18` to `17` left a confidently-wrong `KnownValue("18")`
standing forever. Two fixes, together: `fold` never reads `KnownValue` (it
recomputes from `Constant`/`Arithmetic`/`Comparison`/`Left`/`Right` fresh,
recursing in Python, not across engine ticks — nesting no longer needs one
loop tick per level either, a side benefit), and `known_value` reruns it for
every candidate entity on every tick, `w.replace`-ing (never `w.attach`-ing)
the result — idempotent by `World.replace`'s own dedup, so an unchanged fold
costs nothing once settled, but a CHANGED one is corrected the very next
tick instead of never. See `pystrider.evaluation`'s own module note for the
other half of this fix: a durable receipt is never trusted without
re-deriving through `fold` again first either.

⚠ Abstains the same way every description in this repo does: nothing
asserted where the fold cannot be decided, rather than a guess. Three
distinct reasons to abstain, all silent by construction, none conflated:
an unmodelled operator (`_ARITH`/`_COMPARE` are partial by name, same
posture as `evaluator._DECIDES`), an operand with no fold yet (a `Name`,
or a fold that raises — `ZeroDivisionError` chief among them), or an
operand that is a placeholder (which never carries `Constant`/`Arithmetic`/
`Comparison` at all, so `fold` never reaches a base case for it — no
explicit `Readable` check needed here, unlike `patterns.py`'s three
constructions, because the absence is already structural).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Set

from loopingrules.world import transient
from pystrider.intake import (PARTS, Arithmetic, Assign, Assigned, Block,
                              Comparison, Constant, Function, Left, Name,
                              Origin, Right, Stmt, Value, decode_literal,
                              encode_literal)
from pystrider.resolve import resolve_function

#: Foldable arithmetic operators. ⚠ `matmul` is deliberately absent — `@` has
#: no meaning over Python's own literal types, so there is nothing honest to
#: fold it to; an unmodelled operator here is refused by name, same posture
#: as `evaluator._DECIDES`'s own membrane.
_ARITH = {
    "add": lambda a, b: a + b, "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b, "div": lambda a, b: a / b,
    "floordiv": lambda a, b: a // b, "mod": lambda a, b: a % b,
    "pow": lambda a, b: a ** b, "bitor": lambda a, b: a | b,
    "bitand": lambda a, b: a & b, "bitxor": lambda a, b: a ^ b,
    "lshift": lambda a, b: a << b, "rshift": lambda a, b: a >> b,
}

#: Foldable comparison operators. ⚠ `is`/`is_not`/`in`/`not_in` are
#: deliberately absent — identity and containment are not decidable from two
#: literal VALUES alone (CPython's small-int/string interning makes `is`
#: over literals a fact about the interpreter, not the code), so folding them
#: here would be confidently wrong the way an earlier evaluator's fall-through
#: was (see `evaluator.py`'s own ⚠⚠⚠). Refused by name, not guessed.
_COMPARE = {
    "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b, "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b, "ge": lambda a, b: a >= b,
}


@transient
@dataclass(frozen=True)
class KnownValue:
    """This expression entity's value is decidable from STRUCTURE ALONE — no
    case, no bound parameter, nothing outside the entity's own subtree. A
    CACHE of `fold`, kept in sync every tick — see the module note on why it
    is `w.replace`d rather than `w.attach`ed. `literal` is `repr`-encoded,
    the same codec as `intake.Constant.literal`.
    """

    literal: str


def fold(w, entity: int) -> Optional[Any]:
    """The value `entity` folds to, decided FRESH from its own current
    components every call — `Constant` trivially, `Arithmetic`/`Comparison`
    by recursing into `Left`/`Right`. `None` wherever the fold cannot be
    decided (see the module note's three-reasons-to-abstain).

    ⚠⚠ Never reads `KnownValue`. That component is a CACHE this function
    feeds (`known_value`, below), never a source this function may lean
    on — the whole point is a caller (`pystrider.evaluation.current`
    chief among them) can trust what THIS returns without first asking
    whether some standing annotation is still in sync with the world.
    """
    if w.has(entity, Constant):
        return decode_literal(w.get(entity, Constant).literal)
    if w.has(entity, Arithmetic):
        return _fold_binary(w, entity, _ARITH.get(w.get(entity, Arithmetic).operator))
    if w.has(entity, Comparison):
        return _fold_binary(w, entity, _COMPARE.get(w.get(entity, Comparison).operator))
    return None


def _fold_binary(w, entity: int, op) -> Optional[Any]:
    if op is None:
        return None
    left, right = w.get(entity, Left), w.get(entity, Right)
    if left is None or right is None:
        return None
    a, b = fold(w, left.entity), fold(w, right.entity)
    if a is None or b is None:
        return None
    try:
        return op(a, b)
    except (ZeroDivisionError, TypeError, ValueError, OverflowError):
        return None


def known_value(w) -> None:
    """`fold` over every `Constant`/`Arithmetic`/`Comparison` entity, kept
    in sync as a standing `KnownValue` — present and correct where `fold`
    decides a value, absent where it does not (a fold that STOPS deciding,
    because something it depended on changed, drops its stale `KnownValue`
    here too, via `w.detach`, not just skips adding a new one).
    """
    for kind in (Constant, Arithmetic, Comparison):
        for entity, _tag in w.each(kind):
            value = fold(w, entity)
            if value is None:
                w.detach(entity, KnownValue)
            else:
                w.replace(entity, KnownValue(encode_literal(value)))


@transient
@dataclass(frozen=True)
class BoundTo:
    """This `Name` reference is bound to `entity`'s CURRENT value — the
    live entity id of the deciding `Assign`'s `value` part. Kept in sync
    every tick, same posture as `KnownValue` (`w.replace`d, never
    `w.attach`ed — a reassignment, or a repair rewiring the `Assign`,
    corrects this the very next tick rather than leaving it stale).
    `entity` is a raw id ON PURPOSE: the "nothing durable may hold a raw
    entity id" rule (`pystrider.denotation`'s own ⚠) binds DURABLE facts,
    not this tier — `BoundTo` is `@transient`, exactly like `Callee`/
    `Value`/every other part edge `intake.py` mints, and means nothing
    once this file is reread.
    """

    entity: int


def bound_to(w, entity: int) -> Optional[int]:
    """The live entity id `entity` (a `Name`) is bound to, decided FRESH
    every call — the value-side entity of the one `Assign` that binds it —
    or `None` wherever the binding cannot be decided honestly. The second
    slice of thread 6 (`fold`/`KnownValue` was the first): proven here on
    the motivating case named in `docs/TODO.md` — finding a call site
    through indirection, `f = some_function; ...; f()`.

    ⭐ THE CEILING: exactly one `Assign`, anywhere in the SMALLEST enclosing
    `Function`, may target a bare `Name` sharing this reference's `id` —
    two or more (reassignment, anywhere, even in a branch never taken)
    abstains by COUNT, never by guessing which one runs last. The one
    candidate found must ALSO share this reference's exact immediate
    `Block` (not a different `if`/`for` nesting either direction) and
    precede it in that block's own `Stmt` order — abstaining by POSITION
    covers both "used before assigned" and "assigned in one branch, used
    in a sibling one," without attempting real flow-sensitivity (which
    branch runs, whether a loop body executes at all). Nothing here
    resolves what the bound value's OWN entity denotes any further (a
    `Name` on the right-hand side is returned as-is, not chased to
    whatever function it might itself name) — that is further out than
    this slice reaches.
    """
    if not w.has(entity, Name):
        return None
    name = w.get(entity, Name).id
    function = _enclosing(w, entity, Function)
    if function is None:
        return None
    candidates = [a for a in _reachable(w, function)
                  if w.has(a, Assign) and _targets(w, a, name)]
    if len(candidates) != 1:
        return None
    assign = candidates[0]
    block = _parent_of(w, assign)
    if block is None or not w.has(block, Block):
        return None
    stmts = [s.entity for s in w.get_all(block, Stmt)]
    if assign not in stmts:
        return None
    use_stmt = _owning_statement(w, entity, stmts)
    if use_stmt is None or stmts.index(use_stmt) <= stmts.index(assign):
        return None
    value = w.get(assign, Value)
    return value.entity if value is not None else None


def _targets(w, assign: int, name: str) -> bool:
    """Does `assign` bind `name` — bare `Name` targets only, `t.entity`
    read straight off `Assigned`'s own edge; an `Attribute`/other target
    never matches, since `Name.id` is not even readable off it."""
    return any(w.has(t.entity, Name) and w.get(t.entity, Name).id == name
               for t in w.get_all(assign, Assigned))


def _enclosing(w, entity: int, kind: type) -> Optional[int]:
    """The NEAREST ancestor of `entity` (walking `intake.PARTS` edges
    upward) carrying `kind`, or `None`. `entity` itself never counts —
    this is a search for an ANCESTOR, never the entity asked about."""
    node = _parent_of(w, entity)
    seen: Set[int] = set()
    while node is not None and node not in seen:
        if w.has(node, kind):
            return node
        seen.add(node)
        node = _parent_of(w, node)
    return None


def _owning_statement(w, entity: int, stmts: List[int]) -> Optional[int]:
    """The member of `stmts` that `entity` is part of — `entity` itself if
    it IS one, else the nearest ancestor that is, else `None` if `entity`
    is not reachable from any of `stmts` at all (a different block, or a
    deeper `if`/`for` nesting level)."""
    node = entity
    seen: Set[int] = set()
    while node is not None and node not in seen:
        if node in stmts:
            return node
        seen.add(node)
        node = _parent_of(w, node)
    return None


def _parent_of(w, child: int) -> Optional[int]:
    """The one entity holding a part edge to `child`, or `None` — a linear
    scan of `intake.PARTS`'s own vocabulary. No reverse index kept: same
    freshness posture as `fold`, recomputed every call, never cached.

    ⚠ Returns a plain int, always — `w.each`'s own first element is an
    `Entity` HANDLE (compares equal only to another `Entity`, never to the
    plain int a component field actually stores, see `loopingrules.world.
    Entity`'s own docstring), so a caller that fed a previous `_parent_of`
    result straight back in here would silently stop matching anything
    past the first hop if this returned the handle instead."""
    child = getattr(child, "id", child)
    for cls in set(PARTS.values()):
        for parent, comp in w.each(cls):
            if comp.entity == child:
                return parent.id
    return None


def _reachable(w, root: int) -> Set[int]:
    """Every entity reachable DOWNWARD from `root` through `intake.PARTS`
    edges, `root` itself included — a plain forward BFS, no caching (this
    module's whole ethos)."""
    seen = {root}
    frontier = [root]
    while frontier:
        node = frontier.pop()
        for cls in set(PARTS.values()):
            for comp in w.get_all(node, cls):
                if comp.entity not in seen:
                    seen.add(comp.entity)
                    frontier.append(comp.entity)
    return seen


def resolved_binding(w) -> None:
    """`bound_to` over every `Name` entity, kept in sync as a standing
    `BoundTo` — present where a binding decides, absent where it does not
    (dropped via `w.detach` the tick it stops deciding, e.g. a second
    `Assign` to the same name appearing elsewhere in the function)."""
    for entity, _tag in w.each(Name):
        target = bound_to(w, entity)
        if target is None:
            w.detach(entity, BoundTo)
        else:
            w.replace(entity, BoundTo(target))


@transient
@dataclass(frozen=True)
class BoundFunction:
    """This `Name` reference is bound, through exactly one `Assign`, to
    ANOTHER `Name` that itself currently resolves to a live `Function` in
    the SAME file — `function` is that `Function`'s current entity id. The
    one hop past `BoundTo` thread 6's motivating case actually needed:
    `f()`'s `Callee` resolved all the way to `f`'s real definition through
    `f = some_function`. `@transient`, same reason as `BoundTo` — a raw id,
    meaningless once this file is reread, never a durable fact.
    """

    function: int


def bound_function(w, entity: int) -> Optional[int]:
    """The live `Function` entity `entity` (a `Name`) ultimately names,
    chasing `bound_to` one hop further — decided FRESH every call, same
    purity discipline as `bound_to` and `fold`.

    `None` wherever `bound_to(w, entity)` itself abstains (see its own
    docstring for the ceiling: reassignment, cross-branch binding, use
    before assignment); wherever the bound expression is not itself a
    `Name` (a `Constant`, a `Call`, an `Attribute`... nothing to chase);
    or wherever `pystrider.resolve.resolve_function` finds no `Function`
    of that BARE name in `entity`'s own file (`entity`'s `Origin` supplies
    the path — never a dotted `Qualname`, which a bare `Name` node has no
    scope information to spell in the first place, see `resolve_function`'s
    own docstring on what dotting buys and what it still can't do).
    """
    bound = bound_to(w, entity)
    if bound is None or not w.has(bound, Name):
        return None
    origin = w.get(entity, Origin)
    if origin is None:
        return None
    found = resolve_function(w, origin.value, w.get(bound, Name).id)
    return found.id if found is not None else None


def resolved_function_binding(w) -> None:
    """`bound_function` over every `Name` entity, kept in sync as a
    standing `BoundFunction` — same present-where-decided, dropped-via-
    `w.detach`-where-not posture as `resolved_binding`, for the same
    reason (a reassignment, or a repair rewiring the chain, must correct
    this the very next tick, not leave a stale resolution standing)."""
    for entity, _tag in w.each(Name):
        target = bound_function(w, entity)
        if target is None:
            w.detach(entity, BoundFunction)
        else:
            w.replace(entity, BoundFunction(target))


#: ⭐ Kept as a dict for the same reason `patterns.py`'s `DESCRIPTIONS` and
#: `effects.py`'s are, even at one entry: the perturbation pin's `only=`
#: needs a name to select, not a bare function.
DESCRIPTIONS = {"known_value": known_value, "resolved_binding": resolved_binding,
                 "resolved_function_binding": resolved_function_binding}


def install(loop, only=None) -> None:
    """Register the descriptions. `only` names a subset, for a control."""
    for name, make in DESCRIPTIONS.items():
        if only is None or name in only:
            loop.rule(make, name=f"symbolic.{name}")
