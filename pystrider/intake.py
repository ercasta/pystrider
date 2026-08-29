"""Python -> components, with provenance, and gaps NAMED rather than dropped.

⚠⚠ **2026-08-29: THE SUBSTRATE'S GENERIC RELATION VOCABULARY IS GONE, AND THIS
FILE IS WHERE THAT LANDS HARDEST.** `loopingrules` (the engine carved out of
`harneskills`, née `ugm`) deleted `facts.py`/`arbitration.py` outright rather
than port them — a component is now whatever `dataclasses.is_dataclass` says
yes to, nothing more. Every relation this file used to deposit via
`Facts.fact(name, subject, *objects)` — `for_stmt(n)`, `target(n, item)`,
`operator(n, "gt")` — is now a real, explicitly-declared component, attached
straight onto the world through `World.attach`. **THE FIVE PRIMITIVES SURVIVE
THE MOVE**, because the port they were built for (survey §2, `ugm`'s restart
engine) already proved the AST-handler layer is pure walking that never
touches a substrate directly — what changes here is what the five primitives
DO underneath, not the ~40 call sites that use them.

WHAT IS KEPT, AND WHY EACH ONE IS NOT OPTIONAL — these are lessons that cost
measurements, and a port that quietly dropped them would look identical until
the same bug came back:

* **⭐ THE LOAD-BEARING RULE: an unmodelled construct makes its CONTAINER
  partial, and a partial node is refused.** Refusing a whole file over one
  comprehension is useless; dropping the comprehension silently is far worse.
* **⚠⚠ `unconsumed` — the guard that found silent field dropping.** Each
  handler declares what it CONSUMES; everything else non-empty is refused, so
  a new Python field becomes an honest gap rather than a silent loss.
* **⚠⚠ A PLACEHOLDER, because POSITION IS MEANING.** Ignorance gets a node,
  the thing a description can point at, rather than renumbering what's left.
* **A body is ONE `Block` entity with ordered `Stmt` parts.**
* **⚠ Intake must not reuse a pattern's word** — `condition`/`tests`,
  `for_stmt`/`iteration` — see `patterns.py`.

⭐ **WHAT `loopingrules` CHANGES, AND IT IS A FURTHER IMPROVEMENT ON TOP OF THE
`harneskills` ONE**: interning a Python string as an entity (`f.word(op)`) so
two `"gt"`s would compare equal existed because an older graph engine could
only compare entity IDENTITY. A component field compares by ordinary Python
`==` — `Comparison(operator="gt") == Comparison(operator="gt")` is already
true — so there is nothing left to intern for vocabulary a Python handler
authors itself (an operator, an attribute name). `Constant.literal` is the one
field that still needs a codec rather than a bare field: an AST constant can
be a `bytes`/`complex`/`Ellipsis` payload `loopingrules.world`'s primitives
list (`None`/`bool`/`int`/`float`/`str`) cannot hold directly, so it is stored
`repr`-encoded (`encode_literal`/`decode_literal`, below) — a value CODEC, not
an identity table; nothing about decoding it needs the world at all.

⚠ Intaking CODE is not the border an authored-claim intake would guard. Code
is an artifact that already parses, so the refusal needed is not *malformed*
but **not modelled** — a reach membrane, not a trust boundary. `origin` stays
a PARAMETER because provenance is not derivable from text.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from loopingrules.world import World

# -- the common stamp every intaken node carries ---------------------------


@dataclass(frozen=True)
class Readable:
    """What a description names to ABSTAIN from a part that lacks it — see
    `placeholder`, the only thing `node()` does not attach this to."""


@dataclass(frozen=True)
class FromCode:
    """Makes a later recognition a claim about the ARTIFACT, not our own
    intention — without it, a round-trip check verifies the graph we meant
    to build rather than the one we read."""


@dataclass(frozen=True)
class Origin:
    value: str


@dataclass(frozen=True)
class SourceLine:
    """Recorded here, at intake, because attribution has to be an OBSERVED
    fact joined later, never derived."""

    value: int


@dataclass(frozen=True)
class Partial:
    """Something under this node could not be read."""


@dataclass(frozen=True)
class UnknownPart:
    """`UnknownPart("iterated")` on a node -- one of ITS OWN parts is the gap,
    named by label so a hole in a part a description never reads cannot make
    that description wrong. Several may coexist on one entity (`World`
    already dedupes and orders them by attach)."""

    label: str


# -- the AST-construct kinds ------------------------------------------------
# ⚠ `Param`, the kind (a function parameter, on its own entity), is not
# `HasParam` below (the EDGE from a function to one of its params) -- the one
# place a kind's name would collide with a part's if both were left bare.

@dataclass(frozen=True)
class Module:
    pass


@dataclass(frozen=True)
class Function:
    name: str


@dataclass(frozen=True)
class Param:
    name: str


@dataclass(frozen=True)
class ForStmt:
    pass


@dataclass(frozen=True)
class IfStmt:
    pass


@dataclass(frozen=True)
class Call:
    pass


@dataclass(frozen=True)
class ReturnStmt:
    pass


@dataclass(frozen=True)
class Assign:
    pass


@dataclass(frozen=True)
class Comparison:
    operator: str


@dataclass(frozen=True)
class Arithmetic:
    operator: str


@dataclass(frozen=True)
class Name:
    id: str


@dataclass(frozen=True)
class Constant:
    """`literal` is `repr`-encoded -- see `encode_literal`/`decode_literal`."""

    literal: str


@dataclass(frozen=True)
class Attribute:
    attr: str


@dataclass(frozen=True)
class NoOp:
    pass


@dataclass(frozen=True)
class Block:
    """⚠ Minted directly by `block()`, not through `node()` -- it has no line
    of its own, so it carries `FromCode`/`Readable` but no `Origin`/
    `SourceLine`. See the module note on the bug that shipped once before
    this was `readable`."""


@dataclass(frozen=True)
class Unreadable:
    """⚠⚠ The one kind `node()` never makes `Readable` -- see `placeholder`."""


# -- the parts: an edge from a parent to one of its children ----------------
# ⚠ One shared type per label, spanning every parent kind that uses it
# (`Body` names a `FunctionDef`'s block AND a `For`'s) -- the label is the
# vocabulary, not the container.

@dataclass(frozen=True)
class Target:
    entity: int


@dataclass(frozen=True)
class Iterated:
    entity: int


@dataclass(frozen=True)
class Body:
    entity: int


@dataclass(frozen=True)
class Otherwise:
    entity: int


@dataclass(frozen=True)
class Condition:
    entity: int


@dataclass(frozen=True)
class Then:
    entity: int


@dataclass(frozen=True)
class Callee:
    entity: int


@dataclass(frozen=True)
class Arg:
    """Multi-valued and ordered -- `World.get_all`/`each` give attach order,
    which is what makes describing a call by its first argument alone the
    bug it always was."""

    entity: int


@dataclass(frozen=True)
class Returned:
    entity: int


@dataclass(frozen=True)
class Assigned:
    """Multi-valued: `a = b = value` targets more than one entity."""

    entity: int


@dataclass(frozen=True)
class Value:
    entity: int


@dataclass(frozen=True)
class Left:
    entity: int


@dataclass(frozen=True)
class Right:
    entity: int


@dataclass(frozen=True)
class Of:
    entity: int


@dataclass(frozen=True)
class Stmt:
    """Multi-valued and ordered -- a body is an ordered thing; describing a
    three-line loop by its first statement is the bug this exists to
    prevent."""

    entity: int


@dataclass(frozen=True)
class HasParam:
    entity: int


#: label (as every `part()` call site already spells it) -> the component
#: class standing for that edge. ⚠ Kept as ONE table, beside the classes
#: above, so a new part is one dict entry rather than a new `if` branch.
_PARTS = {
    "target": Target, "iterated": Iterated, "body": Body, "otherwise": Otherwise,
    "condition": Condition, "then": Then, "callee": Callee, "arg": Arg,
    "returned": Returned, "assigned": Assigned, "value": Value, "left": Left,
    "right": Right, "of": Of, "stmt": Stmt, "param": HasParam,
}


class _Unreadable:
    """The sentinel a handler returns for a construct we do not model.

    ⚠ It is not a node. What it means is *put a placeholder here and record the
    gap at this label* — decided by `part`, which is the only thing that knows
    which label it was going to be attached at.
    """

    lineno = None


UNREADABLE = _Unreadable()

#: What each handler consumes. Everything else non-empty on a node is refused.
#: ⚠ ONLY add a field here beside the code that reads it — see the module note.
_CONSUMES = {
    "Module": {"body"},
    "FunctionDef": {"name", "args", "body"},   # `returns`/`decorator_list` NOT yet read
    "arguments": {"args"},                     # posonly/vararg/kwonly/kwarg/defaults NOT yet read
    "arg": {"arg"},                            # `annotation` NOT yet read
    "For": {"target", "iter", "body", "orelse"},
    "If": {"test", "body", "orelse"},
    "Call": {"func", "args"},                  # `keywords` NOT yet read
    "Return": {"value"},
    "Assign": {"targets", "value"},
    "Compare": {"left", "ops", "comparators"},
    "BinOp": {"left", "op", "right"},
    "Name": {"id", "ctx"},
    "Constant": {"value", "kind"},
    "Attribute": {"value", "attr", "ctx"},
    "Expr": {"value"},
    "Pass": set(),
}

#: Every constant Python's grammar can express `repr`-round-trips exactly,
#: `Ellipsis` aside (`repr(...)` is `'Ellipsis'`, not valid syntax back).
_ELLIPSIS = "..."

_CMP = {ast.Eq: "eq", ast.NotEq: "ne", ast.Lt: "lt", ast.LtE: "le", ast.Gt: "gt", ast.GtE: "ge",
        ast.Is: "is", ast.IsNot: "is_not", ast.In: "in", ast.NotIn: "not_in"}
#: ⚠ The bitwise ops are here because leaving them out once refused `str | None`,
#: i.e. every modern union annotation. Nobody thinks of `|` as arithmetic; the
#: reach sweep found it, reading the table did not.
_BIN = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.Div: "div",
        ast.FloorDiv: "floordiv", ast.Mod: "mod", ast.Pow: "pow",
        ast.BitOr: "bitor", ast.BitAnd: "bitand", ast.BitXor: "bitxor",
        ast.LShift: "lshift", ast.RShift: "rshift", ast.MatMult: "matmul"}


def encode_literal(payload: Any) -> str:
    """A `Constant.literal` field's stored form -- the inverse of `decode_literal`."""
    return _ELLIPSIS if payload is Ellipsis else repr(payload)


def decode_literal(text: str) -> Any:
    """The Python value a `Constant.literal` field encodes."""
    return Ellipsis if text == _ELLIPSIS else ast.literal_eval(text)


@dataclass
class Intaken:
    """The module node, and an honest account of what could not be read.

    `unmodelled` is not an error list — it is the reach measurement, per file.
    """

    module: int
    unmodelled: Tuple[str, ...] = ()
    origin: str = "<unknown>"
    world: Optional[World] = field(default=None, repr=False)

    @property
    def complete(self) -> bool:
        return not self.unmodelled


class Intake:
    """Reflects a Python AST into components. One entity per construct.

    Not an `ast.NodeVisitor` subclass, on purpose: dispatch is an explicit table,
    so an unhandled node type is a **lookup miss that must be answered** rather
    than a silently inherited generic visit.
    """

    def __init__(self, world: World, origin: str) -> None:
        self.w = world
        self.origin = origin
        self.unmodelled: List[str] = []

    # --- the five primitives ---------------------------------------------

    def node(self, kind_cls: type, tree: Any, **attrs: Any) -> int:
        """Mint an entity for a construct, stamped with provenance and its line.

        `kind_cls(**attrs)` names its own component, so a typo in a
        construct's name is a Python `NameError` at import time — where a
        typo in a relation string was a silent no-op nobody read.
        """
        n = self.w.spawn(kind_cls(**attrs), Readable(), FromCode(),
                          Origin(self.origin))
        line = getattr(tree, "lineno", None)
        if line is not None:
            self.w.attach(n, SourceLine(line))
        return n

    def part(self, parent: int, label: str, child: Any) -> None:
        """Attach a part. A gap in a child propagates UP, and **at its label**."""
        if child is None:
            return
        if child is UNREADABLE:
            child = self.placeholder(label)
        self.w.attach(parent, _PARTS[label](child))
        if self.w.has(child, Partial):
            self.gap(parent, label)

    def placeholder(self, label: str) -> int:
        """⚠⚠ A node standing where an unreadable construct was — POSITION IS MEANING.

        ⭐⭐ **It is the one node intake does not call `readable`**, and that absence
        is what lets a DESCRIPTION abstain. Here it is a member of the antecedent, so
        a description declares which of its parts it refuses to guess about, and
        another author can disagree by writing a different description.

        ⚠ It is asserted POSITIVELY, on the readable nodes, because a rule cannot
        say *nothing claims this*.
        """
        return self.w.spawn(Unreadable(), FromCode(), Partial())

    def gap(self, parent: int, label: str) -> None:
        """Record that a part of `parent` could not be read, AT ITS LABEL.

        ⭐ The label is the refinement. `Partial` alone is a single bit — *something
        below is unreadable* — with no way to ask *what*, so any hole darkened
        every description of the container, including ones that never named the
        part. `UnknownPart(parent, <label>)` is the set-of-roles answer.

        ⚠ `attach` already dedupes by value, so attaching an equal `UnknownPart`
        or `Partial` twice is a no-op the world itself refuses to count as a
        change — nothing here needs to check first.
        """
        self.w.attach(parent, UnknownPart(label))
        self.w.attach(parent, Partial())

    def refuse(self, tree: Any, parent: Optional[int], label: Optional[str] = None) -> None:
        """Name an unmodelled construct, and cost its container exactly one part."""
        self.unmodelled.append(type(tree).__name__)
        if parent is not None and label is not None:
            self.gap(parent, label)

    def unconsumed(self, tree: Any, parent: int) -> None:
        """⚠⚠ Refuse every non-empty AST field the handler did not declare.

        The guard that turns a silent field drop into an honest gap. It must be
        CALLED at every site — the two bugs it missed were both cases of a handler
        never calling it, which is why `param` exists as one shared helper below
        rather than as four call sites that each had to remember.
        """
        name = type(tree).__name__
        consumed = _CONSUMES.get(name, ())
        for field_name, value in ast.iter_fields(tree):
            if field_name in consumed:
                continue
            if value is None or value == [] or isinstance(value, ast.Load):
                continue
            if isinstance(value, (ast.Store, ast.Del)):
                continue
            self.unmodelled.append(f"{name}.{field_name}")
            self.gap(parent, field_name)

    # --- the walk ---------------------------------------------------------

    def visit(self, tree: Any, parent: Optional[int] = None, label: Optional[str] = None) -> Any:
        handler = getattr(self, f"_{type(tree).__name__}", None)
        if handler is None:
            self.refuse(tree, parent, label)
            return UNREADABLE
        return handler(tree)

    def block(self, statements: List[Any], parent: Optional[int] = None) -> int:
        """⚠ A body is ONE node with ordered `Stmt` parts, never N parts above it."""
        b = self.w.spawn(Block(), FromCode(), Readable())
        for s in statements:
            self.part(b, "stmt", self.visit(s, b, "stmt"))
        return b

    def param(self, a: ast.arg) -> int:
        """⚠ ONE shared helper, because a guard that must be remembered per site
        gets forgotten at one — which is exactly how annotations on keyword-only
        and `*args` parameters were dropped by both intake and emit while the
        round trip reported `complete`."""
        n = self.node(Param, a, name=a.arg)
        self.unconsumed(a, n)
        return n

    # --- handlers ---------------------------------------------------------

    def _Module(self, t: ast.Module) -> int:
        n = self.w.spawn(Module(), FromCode(), Readable(), Origin(self.origin))
        self.part(n, "body", self.block(t.body, n))
        self.unconsumed(t, n)
        return n

    def _FunctionDef(self, t: ast.FunctionDef) -> int:
        n = self.node(Function, t, name=t.name)
        for a in t.args.args:
            self.part(n, "param", self.param(a))
        self.unconsumed(t.args, n)
        self.part(n, "body", self.block(t.body, n))
        self.unconsumed(t, n)
        return n

    def _For(self, t: ast.For) -> int:
        n = self.node(ForStmt, t)
        self.part(n, "target", self.visit(t.target, n, "target"))
        self.part(n, "iterated", self.visit(t.iter, n, "iterated"))
        self.part(n, "body", self.block(t.body, n))
        if t.orelse:
            self.part(n, "otherwise", self.block(t.orelse, n))
        self.unconsumed(t, n)
        return n

    def _If(self, t: ast.If) -> int:
        n = self.node(IfStmt, t)
        self.part(n, "condition", self.visit(t.test, n, "condition"))
        self.part(n, "then", self.block(t.body, n))
        # ⚠ An empty else is NO else, never `else: pass` — or the round trip grows
        # one every pass, which is divergence that compounds.
        if t.orelse:
            self.part(n, "otherwise", self.block(t.orelse, n))
        self.unconsumed(t, n)
        return n

    def _Call(self, t: ast.Call) -> int:
        n = self.node(Call, t)
        self.part(n, "callee", self.visit(t.func, n, "callee"))
        for a in t.args:
            self.part(n, "arg", self.visit(a, n, "arg"))
        self.unconsumed(t, n)
        return n

    def _Return(self, t: ast.Return) -> int:
        n = self.node(ReturnStmt, t)
        self.part(n, "returned", self.visit(t.value, n, "returned") if t.value else None)
        self.unconsumed(t, n)
        return n

    def _Assign(self, t: ast.Assign) -> int:
        n = self.node(Assign, t)
        for target in t.targets:
            self.part(n, "assigned", self.visit(target, n, "assigned"))
        self.part(n, "value", self.visit(t.value, n, "value"))
        self.unconsumed(t, n)
        return n

    def _Compare(self, t: ast.Compare) -> Any:
        # ⚠ A chained comparison is REFUSED, never approximated by its first pair.
        if len(t.ops) != 1:
            self.unmodelled.append("Compare.chained")
            return UNREADABLE
        op = _CMP.get(type(t.ops[0]))
        if op is None:
            self.unmodelled.append(f"Compare.{type(t.ops[0]).__name__}")
            return UNREADABLE
        n = self.node(Comparison, t, operator=op)
        self.part(n, "left", self.visit(t.left, n, "left"))
        self.part(n, "right", self.visit(t.comparators[0], n, "right"))
        self.unconsumed(t, n)
        return n

    def _BinOp(self, t: ast.BinOp) -> Any:
        op = _BIN.get(type(t.op))
        if op is None:
            self.unmodelled.append(f"BinOp.{type(t.op).__name__}")
            return UNREADABLE
        n = self.node(Arithmetic, t, operator=op)
        self.part(n, "left", self.visit(t.left, n, "left"))
        self.part(n, "right", self.visit(t.right, n, "right"))
        self.unconsumed(t, n)
        return n

    def _Name(self, t: ast.Name) -> int:
        n = self.node(Name, t, id=t.id)
        self.unconsumed(t, n)
        return n

    def _Constant(self, t: ast.Constant) -> int:
        n = self.node(Constant, t, literal=encode_literal(t.value))
        self.unconsumed(t, n)
        return n

    def _Attribute(self, t: ast.Attribute) -> int:
        n = self.node(Attribute, t, attr=t.attr)
        self.part(n, "of", self.visit(t.value, n, "of"))
        self.unconsumed(t, n)
        return n

    def _Expr(self, t: ast.Expr) -> Any:
        # An expression statement is its expression; there is nothing else to say.
        return self.visit(t.value)

    def _Pass(self, t: ast.Pass) -> int:
        n = self.node(NoOp, t)
        self.unconsumed(t, n)
        return n


def intake(source: str, world: World, origin: str) -> Intaken:
    """Read Python text into `world`.

    ⚠ `origin` is a PARAMETER, not something derived from the text, because code
    may arrive as a tool call result and provenance is not recoverable from it.
    """
    walker = Intake(world, origin)
    module = walker._Module(ast.parse(source))
    return Intaken(module=module, unmodelled=tuple(walker.unmodelled),
                   origin=origin, world=world)
