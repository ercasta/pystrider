"""Python → components, TOTALLY — and the membrane moved out of the reading.

⭐⭐ **THE SPLIT THIS FILE IS.** `intake.py` does two jobs in one pass, and they
have opposite obligations:

    (a) TRANSLITERATION   mirror the AST into components
    (b) THE MEMBRANE      decide which constructs this project's vocabulary covers

Conflating them is what makes reach 3.1 %. Intake's load-bearing rule — *an
unmodelled construct makes its CONTAINER partial, and a partial node is refused* —
is exactly right for (b): a loop understood two-thirds and presented as complete is
worse than a refusal. It is exactly wrong for (a), because one `ListComp` in a
`return` costs the return, the block, the function and the module, and the
`docs/transplant.md` backlog is then not hard reasoning but ordinary fields nobody
transliterated: `Assert` 234, `Tuple` 221, `FunctionDef.returns` 206,
`Call.keywords` 197, `arg.annotation` 186, `Subscript` 111.

**A compiler pass does not need the tree UNDERSTOOD. It needs the tree PRESENT.**
It matches the handful of nodes it cares about and leaves the rest alone. So this
module does (a) and only (a) — every AST node, every field, no judgement — and (b)
becomes authored rules over the result, where another author can argue with it.

## What this deposits, and it is the whole vocabulary

    AstNode(n)                   every node, so a rule can quantify over "syntax"
    Syntax(n, "ListComp")        the AST class name, as a WORD, spelled as Python
                                 spells it — no case mangling, so `While` in a
                                 backlog report and `While` in a rule are one word
    Origin(n, "path")            provenance, a PARAMETER (`intake.py`'s reason)
    SourceLine(n, 12)            attribution OBSERVED, never derived
    FromCode(n)                  kept from `intake`: what makes a later recognition
                                  a claim about the ARTIFACT and not about our own
                                  intention
    <field>(n, x)                one component PER AST FIELD NAME, named as the
                                  AST names it
    SeqNode(s), Item(s, 0, c)    a LIST field is one node with POSITIONED `Item` parts

⚠ **`Readable` IS NOT DEPOSITED HERE, and that is the point.** It was intake's way
of saying *this is not a placeholder*, and there are no placeholders any more.
Abstention is still needed — a description can still refuse to describe a loop
whose sequence it could not read — but it is now a claim about whether the
DESCRIBING vocabulary covers a node, which is a corpus's judgement and not a
reader's. It belongs beside the rules that would abstain.

## Why a list gets a node of its own

`intake.py` learned this for bodies — *a body is ONE `Block` node with ordered
`Stmt` parts, never N parts on the container* — or a description can only point at
the first statement. It generalises, and a pass makes the reason sharper: **a pass
that inserts a statement needs the list to be a thing it can attach to.** A new
`Item` appends; N components on the container give a pass nothing to hold.

⚠ An EMPTY list still gets its `SeqNode`. It costs a node per `decorator_list`
nobody wrote, and it buys the one case that matters: appending to an empty body is
the same rule as appending to a full one.

**⚠⚠ AND AN ITEM CARRIES ITS POSITION, BECAUSE ATTACH ORDER CANNOT COUNT TO TWO.**
The first version of this file leaned on deposit order alone, arguing an index
would be a second place the order lived. That is true and it is not the problem —
**components are DEDUPED BY VALUE**, so a list holding the same node twice would
attach the same `Item` twice, which `World.attach` refuses as a no-op, and the
list comes back short. Measured on the standard library: `{**a, **b}` is
`Dict.keys = [None, None]` and rendered as `{**a}`; `def f(*, a, b)` is
`kw_defaults = [None, None]` and lost a parameter. Fourteen functions, every one
silently wrong. A positional index on `Item` is not bookkeeping beside the order;
on a deduping substrate it is the only thing that makes two identical members two
members.

⚠ So a pass that reorders a list owns the renumbering, and `detransliterate` reads by
POSITION rather than by attach order — otherwise a renumbered list would still be
read in the order it was written, which is the drift the index was supposed to end.

## The two encodings, and the invariant that keeps them apart

`intake.py` has words and literals for a reason it paid for: `operator=gt` stored as
`'gt'` made a rule naming the bare `gt` unmatchable and one of two repair families
could never fire. Here:

* **an IDENTIFIER is a WORD** — `name`, `id`, `attr`, `arg`, `asname`, and the rest
  of the fields Python's grammar declares as names. A rule must be able to spell them.
* **a `Constant`'s payload is a LITERAL** — `repr`-encoded, `literal_eval` back. It
  is a value the program computes with, not vocabulary, which is `intake.py`'s own
  distinction. So are `level`, `is_async`, `simple`, and the `None`s inside
  `kw_defaults`.

**⚠⚠ AND THE DECODER'S INVARIANT IS ENFORCED BY THE ENCODER, BECAUSE REASONING IT
TRUE WAS WRONG.** `detransliterate` decides which encoding it is looking at by
trying `literal_eval` — succeeded means literal, failed means word. The first
version of this file argued that was safe *because an identifier can never be a
numeric literal and `True`/`False`/`None` are keywords*, and word-encoded every
`str`. Measured on 587 functions, that lost five of them and refused nine more —
a string literal is arbitrary text, and plenty of it reads as something else
entirely (an empty-list literal, an int, a quoted string one layer down). So
`_primitive` now word-encodes only text that does NOT read as a literal, and
everything else goes through `repr` — the decoder's premise is a postcondition of
the encoder rather than a claim about Python.

⚠ A word may therefore contain spaces (`type_comment`), which no CNL surface can
spell. Such a constant is reachable by a rule through a variable and not by name.

## ⭐⭐ `names` — the collision that WAS here, and the one that structurally CANNOT be, now

`names` used to be renamed to `py_names` because an earlier engine's reserved-name
table mapped `names` to ITS OWN machinery node, so `Import.names`/`Global.names`/
`Nonlocal.names` deposited into engine internals — loud nowhere, wrong everywhere
downstream. `_RENAMED` stays EMPTY, kept for the record rather than deleted: there
is no reserved table on `loopingrules` to collide with.

⚠⚠ 2026-08-29: **the collision `check_vocabulary` still checks for is no longer
possible even in principle, not merely retargeted.** Every AST field name becomes
its OWN dynamically-built component CLASS (`field_component`, below), interned by
name in a dict private to this module — never the same Python object as this
module's own fixed vocabulary (`AstNode`, `Syntax`, `SeqNode`, `Item`). A field
that happened to be called `"syntax"` would attach instances of a *different*
class than the fixed `Syntax` tag, so nothing could overwrite anything even if the
strings coincide — the same "a relation is a class, not a name in a shared table"
argument that made the twin trap structurally impossible on `intake.py`, one level
up. `check_vocabulary` is kept anyway, unconditionally cheap and now genuinely
unable to fire, the same spirit that keeps `_RENAMED` empty rather than deleted.

⚠ `check_vocabulary()` no longer checks the field-component names against this
module's fixed vocabulary for safety (nothing can collide) — it is kept as a
diagnostic: if `ast` ever grows a field with the same spelling as `AstNode`/
`Syntax`/`SeqNode`/`Item`, a human reading both would be confused even though the
substrate would not be.
"""
from __future__ import annotations

import ast
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .intake import FromCode, Origin, SourceLine

#: AST field names this cannot deposit under their own name, and what they become.
#: ⚠⚠ **EMPTY SINCE THE HARNESKILLS PORT, and the entry that was here is worth
#: keeping in the record.** See the module note on `names`.
_RENAMED: Dict[str, str] = {}

#: Our own FIXED vocabulary — the classes this module declares itself, as opposed
#: to the per-field classes `field_component` builds dynamically. ⚠
#: `check_vocabulary` guards this set as a human-readability diagnostic only; see
#: the module note on why a real collision is no longer possible.
_OURS = ("ast_node", "syntax", "seq", "item", "origin", "source_line", "from_code")

#: The fields carrying a VALUE rather than a name. `intake.py`'s distinction, and
#: the only place this module makes one — a `Constant`'s payload is what the
#: program computes with, everything else primitive is vocabulary if it can be.
_VALUED = {("Constant", "value"), ("Constant", "kind")}


@dataclass(frozen=True)
class AstNode:
    """Every transliterated node carries this, so a rule can quantify over
    "syntax" without knowing which construct it is."""


@dataclass(frozen=True)
class Syntax:
    """The AST class name, as a WORD, spelled as Python spells it."""

    kind: str


@dataclass(frozen=True)
class SeqNode:
    """A list field, reified as its own entity — see the module note on why
    a list gets a node of its own."""


@dataclass(frozen=True)
class Item:
    """One member of a `SeqNode`, at its POSITION. Multi-valued and
    order-independent to read (sort by `index`) — see the module note on
    why the position is not decoration."""

    index: int
    value: Any


def reads_as_literal(text: str) -> bool:
    """Whether `ast.literal_eval` would take this text for a Python value.

    ⚠ Broad `except`, deliberately: `literal_eval` raises `ValueError` and
    `SyntaxError` on ordinary text and `MemoryError`/`RecursionError` on pathological
    text, and every one of them means the same thing here — *not a literal*. A
    narrower catch would turn a long string constant into a crash in the middle of a
    sweep.
    """
    try:
        ast.literal_eval(text)
    except Exception:      # noqa: BLE001 — see the docstring
        return False
    return True


def _ast_field_names() -> Set[str]:
    """Every field name every `ast.AST` subclass in THIS interpreter declares.

    Derived, never listed: a hand-written list is a list that is right until the
    Python this runs on changes, and the whole point of a transliterator is that it
    has no opinion about which constructs exist.
    """
    seen: Set[str] = set()

    def walk(cls: type) -> None:
        seen.update(getattr(cls, "_fields", ()))
        for sub in cls.__subclasses__():
            walk(sub)

    walk(ast.AST)
    return seen


def check_vocabulary() -> None:
    """A human-readability diagnostic — see the module note on why a real
    collision between an AST field and this module's own fixed vocabulary is
    no longer possible, only confusing if it happened."""
    clash = sorted(_ast_field_names() & set(_OURS))
    if clash:
        raise RuntimeError(
            f"this Python's `ast` declares field(s) {clash}, which read the same "
            f"as this module's own fixed vocabulary — harmless (different "
            f"classes), but confusing to a human. Add each to `_RENAMED`."
        )


_checked = False

#: field name -> its component class. Interned the same way `intake.py`'s fixed
#: vocabulary is a fixed set of classes, except THIS name table is built at
#: runtime because an AST field name is late-bound — whatever THIS Python's
#: `ast` module declares, not something this module authors itself. The same
#: exception `cnl.py`'s predicates need, for the same reason.
_FIELDS: Dict[str, type] = {}


def field_component(name: str) -> type:
    """The component class for AST field `name`. The SAME class every call —
    two lookups are the same object because Python says so, same guarantee
    `intake.py`'s fixed classes give for free and this module has to build
    because its vocabulary is not fixed in advance."""
    cls = _FIELDS.get(name)
    if cls is None:
        cls = _FIELDS[name] = dataclasses.make_dataclass(
            name, [("value", "typing.Any")], frozen=True)
    return cls


@dataclass
class Transliterated:
    """The module node and a census — never a refusal list.

    ⚠ There is no `complete` and no `unmodelled`, and their absence is the claim:
    this reader does not refuse, so a caller asking *did it all come through* is
    asking the wrong half. `experiments/transliterate_reach.py` answers it the only
    way that can be trusted — by writing the graph back out and diffing the SOURCE.
    """

    module: int
    origin: str = "<unknown>"
    #: How many of each AST class came through. The reach report's raw material,
    #: and the thing a pass author reads to know what is actually in the corpus.
    census: Dict[str, int] = field(default_factory=dict)
    world: Optional[Any] = field(default=None, repr=False)


class Transliterate:
    """One AST → components. No membrane, no dispatch table, no handlers.

    ⭐ There is nothing to add here when Python grows a construct. `ast.iter_fields`
    is total, so `match`/`TypeAlias`/whatever comes next arrives as
    `Syntax(n, "TypeAlias")` plus its fields, and only the corpora that want to
    UNDERSTAND it need editing. That is the whole difference from `intake.py`, where
    a new construct is a missing handler and therefore a hole.
    """

    def __init__(self, world, origin: str) -> None:
        self.w = world
        self.origin = origin
        self.census: Dict[str, int] = {}

    # -- writing -----------------------------------------------------------

    def _primitive(self, payload: Any, valued: bool = False) -> str:
        """A leaf that is not an AST node. See the module note on the two encodings.

        `valued` is the `Constant` payload — a value the program computes with, so
        `repr` whatever it is. Everything else is a name if it can be one: text that
        `reads_as_literal` is `repr`-ed instead, which is what makes the decoder's
        try-`literal_eval` a decision rather than a guess.
        """
        if not valued and isinstance(payload, str) and payload and not reads_as_literal(payload):
            return payload
        return repr(payload)

    def _rel(self, field_name: str) -> str:
        return _RENAMED.get(field_name, field_name)

    def _seq(self, values: List[Any]) -> int:
        """A list field, as one node with POSITIONED `Item` parts.

        ⚠ The position is not decoration — see the module note on what
        deduping did to `{**a, **b}`.
        """
        s = self.w.spawn(SeqNode(), FromCode())
        for i, v in enumerate(values):
            self.w.attach(s, Item(i, self.node(v) if isinstance(v, ast.AST)
                                  else self._primitive(v)))
        return s

    def node(self, t: ast.AST) -> int:
        kind = type(t).__name__
        self.census[kind] = self.census.get(kind, 0) + 1
        n = self.w.spawn(AstNode(), Syntax(kind), FromCode(), Origin(self.origin))
        line = getattr(t, "lineno", None)
        if line is not None:
            self.w.attach(n, SourceLine(line))
        for field_name, value in ast.iter_fields(t):
            # ⚠ A `None` field deposits NOTHING, and `detransliterate` rebuilds an
            # absent field as `None`. Absence is absence; attaching one for every
            # optional slot in the language would be a component a rule has to
            # step over.
            if value is None:
                continue
            rel = self._rel(field_name)
            if isinstance(value, list):
                self.w.attach(n, field_component(rel)(self._seq(value)))
            elif isinstance(value, ast.AST):
                self.w.attach(n, field_component(rel)(self.node(value)))
            else:
                self.w.attach(n, field_component(rel)(
                    self._primitive(value, (kind, field_name) in _VALUED)))
        return n


class Detransliterate:
    """Components → AST. The inverse, and it is the only honest check on the pair.

    ⚠⚠ **STABILITY IS NOT FIDELITY** — `emit.py`'s recorded lesson, and it applies
    with more force here because nothing refuses any more. An emit-vs-emit fixpoint
    on a graph that silently lost a field is clean. Only comparing against the
    ORIGINAL SOURCE catches the loss, which is what
    `experiments/transliterate_reach.py` does and why it exists in the same commit.
    """

    def __init__(self, world) -> None:
        self.w = world

    def _decode(self, x: str) -> Any:
        """A leaf back to the Python value it stood for.

        ⭐ No table, and the module note says why: no word this deposits is
        `literal_eval`-able, so `literal_eval` succeeding IS the encoding's own
        answer about which of the two it was.
        """
        return ast.literal_eval(x) if reads_as_literal(x) else x

    def value(self, x: Any) -> Any:
        """`x` is either an entity id (a nested node or a `SeqNode`, always an
        `int` — `_primitive` never returns one) or an already-encoded
        primitive (always a `str`) — the type alone tells the two apart, so
        this checks it BEFORE asking `World` anything: `has()` tries to read
        a non-`Entity` argument as an id, and a decoded string like `"None"`
        is not one."""
        if isinstance(x, int):
            if self.w.has(x, SeqNode):
                # ⚠ By POSITION, never by attach order: a pass that
                # renumbered a list wrote the new order into the indices and
                # nowhere else.
                items = sorted(self.w.get_all(x, Item), key=lambda item: item.index)
                return [self.value(item.value) for item in items]
            if self.w.has(x, AstNode):
                return self.node(x)
        return self._decode(x)

    def node(self, n: int) -> ast.AST:
        syntax = self.w.get(n, Syntax)
        if syntax is None:
            raise ValueError(f"{self.w.show(n)} has no `Syntax` — not a transliterated node")
        cls = getattr(ast, syntax.kind, None)
        if cls is None:
            # ⚠ By NAME, never approximated: a graph naming a construct this
            # interpreter's `ast` does not have was written by a different Python,
            # and guessing a near neighbour is how a round trip silently changes
            # code.
            raise ValueError(f"`ast` here has no {syntax.kind} — the graph was built by another Python")
        built: Dict[str, Any] = {}
        for field_name in cls._fields:
            component = self.w.get(n, field_component(_RENAMED.get(field_name, field_name)))
            built[field_name] = None if component is None else self.value(component.value)
        return cls(**built)


def transliterate(source: str, world, origin: str) -> Transliterated:
    """Read Python text into `world`, entirely.

    ⚠ `origin` is a PARAMETER for `intake.py`'s reason: code may arrive as a tool
    call result and provenance is not recoverable from the text.
    """
    global _checked
    if not _checked:
        check_vocabulary()
        _checked = True
    walker = Transliterate(world, origin)
    module = walker.node(ast.parse(source))
    return Transliterated(module=module, origin=origin,
                          census=walker.census, world=world)


def detransliterate(world, node: int) -> ast.AST:
    """The graph back to an AST. `ast.fix_missing_locations` is the caller's."""
    return Detransliterate(world).node(node)


def render(world, node: int) -> str:
    """The graph back to Python source, via `ast.unparse`.

    ⭐ Valid Python by construction, `emit.py`'s reason: rendering is `unparse`'s
    job and this module's only work is the vocabulary.
    """
    return ast.unparse(ast.fix_missing_locations(detransliterate(world, node)))
