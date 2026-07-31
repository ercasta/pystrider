"""INTAKE — real Python becomes graph data, with its gaps named rather than hidden.

**⚠ This is NOT the same kind of border as ugm's `intake.py`, and conflating them would import the wrong
discipline.** Theirs is a *goal* border: a language model writes text, and the parser accepts or refuses it
deterministically so nothing can reach past the surface and write graph structure directly. The thing being
guarded against is an authored claim that could say anything.

Code is not an authored claim. It is an **artifact** — it already parses, it means what it means, and
there is no question of it lying about its own syntax. So the refusal this module needs is a different
one: not "malformed", but **not modelled**. Python has far more syntax than we describe, and the honest
answer for the rest is to say so by name. That is the reach membrane, not a trust boundary.

**⭐ THE LOAD-BEARING DECISION: an unmodelled construct makes its CONTAINER partial, and a partial
container is refused by the pattern layer.** Refusing a whole file over one comprehension would be
useless; silently dropping the comprehension would be far worse — a `for` loop whose body we only half
understood would be recognized as a complete iteration and a consumer would act on a description that is
missing something. Neither. The gap is recorded, the containing node is marked `partial`, and
`strider.patterns` declines to recognize a partial node. The construct we could not read costs us exactly
the constructs that contain it, and nothing else.

**Provenance is recorded, never inferred.** Code may be the result of a tool call — a file read, a
generator's output, another agent's edit — and that has two consequences this module honours:

* `origin` is a parameter. Where source came from is not derivable from the source.
* `from_code` is stamped on everything intaken. This is not decoration: a consumer that both WRITES
  structure and READS it back holds facts of both origins on one graph, so "is there an iteration over
  `?s`" would be satisfied by the loop the writer just minted, and the check would verify its own
  intention instead of the artifact. `from_code` is what lets a requirement say *the code contains this*.

**⚠ Getting the source is a DISPATCH; parsing it is not.** Reading a file or calling a tool is an effect
leaving the graph and belongs at `dispatch.service`, which is also where the imagined-target refusal lives.
`intake` takes text and is pure, deterministic and testable. Keeping the two apart is the same discipline
as ugm's "substitution and safety are two mechanisms and must stay apart" — and it means an expectation
about intaken code must be **qualitative** (§5f): *some* functions appeared, never *two*, because a file
re-read after an edit yields a different count and that is noise, not divergence.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

from .library import Library

#: The modelled constructs. Everything else is named in `unmodelled` rather than silently dropped.
#: `Compare` and `BinOp` are here deliberately: the old intake never modelled them, which is why
#: `experiments/first_principles_repair.py` had to reify comparisons through a separate probe path.
MODELLED = ("Module", "FunctionDef", "arguments", "arg", "For", "If", "Call", "Return", "Assign",
            "Compare", "BinOp", "Name", "Constant", "Expr", "Attribute", "Pass")

class _Nowhere:
    """A stand-in for an empty block, which has no statement to take a line number from."""
    lineno = None


_NOWHERE = _Nowhere()

#: What each handler consumes. Everything else on a node is refused by `unconsumed`.
_CONSUMES = {
    "Module": {"body"},
    "FunctionDef": {"name", "args", "body", "returns"},   # decorators deliberately NOT here
    "arguments": {"args"},
    "arg": {"arg", "annotation"},
    "For": {"target", "iter", "body", "orelse"},
    "If": {"test", "body", "orelse"},
    "Call": {"func", "args", "keywords"},
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

_CMP = {ast.Eq: "eq", ast.NotEq: "ne", ast.Lt: "lt", ast.LtE: "le", ast.Gt: "gt", ast.GtE: "ge"}
_BIN = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.Div: "div",
        ast.FloorDiv: "floordiv", ast.Mod: "mod", ast.Pow: "pow"}


@dataclass
class Intaken:
    """The result: the module node, and an honest account of what we could not read.

    `unmodelled` is not an error list — it is the reach measurement, per file. A consumer that wants to
    know whether a description is complete asks `partial`, not this."""
    module: str
    unmodelled: tuple = ()
    origin: str = "<unknown>"
    _graph: object = field(default=None, repr=False)

    @property
    def complete(self) -> bool:
        return not self.unmodelled


class Intake:
    """Reflects a Python AST into the graph. One node per construct, parts as named edges.

    Not a visitor subclass on purpose: dispatch is an explicit table, so an unhandled node type is a
    *lookup miss* that must be answered, rather than a silently-inherited generic visit."""

    def __init__(self, lib: Library, origin: str):
        self.g = lib.graph
        self.origin = origin
        self.unmodelled: list = []

    # --- the graph-writing primitives ------------------------------------------------------------------

    def node(self, kind: str, tree, **attrs) -> str:
        """Mint a node for a construct, stamped with provenance and its source line.

        `source_line` is recorded here because attribution has to be an OBSERVED fact joined later, never
        derived — the lesson from getting loop attribution wrong the derived way."""
        n = self.g.mint(kind, from_code=True, origin=self.origin, **attrs)
        line = getattr(tree, "lineno", None)
        if line is not None:
            self.g.put(n, source_line=line)
        return n

    def part(self, parent: str, label: str, child) -> None:
        """Attach a part. A child we could not read propagates `partial` UP, which is the whole point."""
        if child is None:
            return
        self.g.link(parent, label, child)
        if self.g.attr(child, "partial"):
            self.g.put(parent, partial=True)

    def refuse(self, tree, parent: str | None) -> None:
        """Record an unmodelled construct and mark whatever contains it as partial."""
        self.unmodelled.append((type(tree).__name__, getattr(tree, "lineno", None)))
        if parent is not None:
            self.g.put(parent, partial=True)

    def unconsumed(self, tree, parent) -> None:
        """⚠ Refuse any AST field this handler did not consume — the guard against SILENT DROPPING.

        Found by a round-trip sweep, not by inspection: `def f(x: int) -> bool` was intaken with an empty
        `unmodelled` list, reported COMPLETE, and emitted as `def f(x, y)`. Annotations, decorators and
        defaults were all being read past without a word, which is precisely the confidently-wrong answer
        the rest of this design exists to prevent.

        Enumerating the fields to reject by hand would have fixed those three and left the next one to be
        discovered the same way. Declaring what a handler CONSUMES and refusing everything else inverts
        the default: a Python version that adds a field, or a handler that stops reading one, becomes an
        honest gap rather than a silent omission."""
        for field, value in ast.iter_fields(tree):
            if field in _CONSUMES.get(type(tree).__name__, ()):
                continue
            if value is None or value == [] or field == "type_comment":
                continue
            self.unmodelled.append((f"{type(tree).__name__}.{field}", getattr(tree, "lineno", None)))
            self.g.put(parent, partial=True)

    # --- the dispatch ----------------------------------------------------------------------------------

    def visit(self, tree, parent: str | None = None):
        handler = getattr(self, f"_{type(tree).__name__}", None)
        if handler is None:
            self.refuse(tree, parent)
            return None
        built = handler(tree)
        if built is not None:
            self.unconsumed(tree, built)
        return built

    def block(self, statements, parent: str | None = None) -> str:
        """A statement list becomes ONE `block` node with ordered `stmt` edges.

        ⚠ Not N sibling edges on the container. A pattern binds a body as a single thing (`?x each_does
        ?body`), so a body spread across the parent as repeated edges would give the bridge nothing to
        point at but the first statement — quietly describing a three-line loop by its first line.
        Ordering inside the block is native, so nothing stamps a counter."""
        b = self.node("block", statements[0] if statements else _NOWHERE)
        for stmt in statements:
            self.part(b, "stmt", self.visit(stmt, b))
        if parent is not None and self.g.attr(b, "partial"):
            self.g.put(parent, partial=True)
        return b

    # --- the modelled constructs -----------------------------------------------------------------------

    def _Module(self, t):
        n = self.node("module", t)
        for stmt in t.body:                # a module is a list of definitions, not a pattern body
            self.part(n, "defines", self.visit(stmt, n))
        return n

    def _FunctionDef(self, t):
        n = self.node("function_def", t, name=t.name)
        for a in t.args.args:
            param = self.node("param", a, name=a.arg)
            if a.annotation is not None:
                self.part(param, "annotation", self.visit(a.annotation, param))
            self.unconsumed(a, param)
            self.part(n, "param", param)
        self.unconsumed(t.args, n)          # *args, **kwargs, defaults, kw-only — none of them modelled
        if t.returns is not None:
            self.part(n, "returns", self.visit(t.returns, n))
        self.part(n, "does", self.block(t.body, n))
        return n

    def _For(self, t):
        n = self.node("for_stmt", t)
        self.part(n, "over", self.visit(t.iter, n))
        self.part(n, "binds", self.visit(t.target, n))
        self.part(n, "body", self.block(t.body, n))
        if t.orelse:                       # `for ... else` is real Python and we do not model it
            self.refuse(t.orelse[0], n)
        return n

    def _If(self, t):
        n = self.node("if_stmt", t)
        self.part(n, "condition", self.visit(t.test, n))
        self.part(n, "then", self.block(t.body, n))
        self.part(n, "otherwise", self.block(t.orelse, n))
        return n

    def _Call(self, t):
        n = self.node("call", t)
        self.part(n, "callee", self.visit(t.func, n))
        for a in t.args:
            self.part(n, "arg", self.visit(a, n))
        for kw in t.keywords:              # keyword arguments are not modelled; the call becomes partial
            self.refuse(kw, n)
        return n

    def _Return(self, t):
        n = self.node("return_stmt", t)
        self.part(n, "value", self.visit(t.value, n) if t.value is not None else None)
        return n

    def _Assign(self, t):
        n = self.node("assign", t)
        for target in t.targets:
            self.part(n, "target", self.visit(target, n))
        self.part(n, "value", self.visit(t.value, n))
        return n

    def _Compare(self, t):
        """⭐ The gap the old intake never closed. A chained comparison (`a < b < c`) is a DIFFERENT
        construct with different semantics, so it is refused rather than approximated by its first pair."""
        if len(t.ops) != 1:
            self.refuse(t, None)
            n = self.node("compare", t, partial=True)
            return n
        op = _CMP.get(type(t.ops[0]))
        if op is None:
            self.refuse(t.ops[0], None)
            return self.node("compare", t, partial=True)
        n = self.node("compare", t, op=op)
        self.part(n, "left", self.visit(t.left, n))
        self.part(n, "right", self.visit(t.comparators[0], n))
        return n

    def _BinOp(self, t):
        op = _BIN.get(type(t.op))
        if op is None:
            self.refuse(t.op, None)
            return self.node("binop", t, partial=True)
        n = self.node("binop", t, op=op)
        self.part(n, "left", self.visit(t.left, n))
        self.part(n, "right", self.visit(t.right, n))
        return n

    def _Pass(self, t):
        """⚠ Modelled because EMIT WRITES ONE. An empty block renders as `pass`, so an intake that could
        not read `pass` would break the round trip on its own output — caught by a round-trip pin, not by
        inspection. Read and write capabilities are tracked separately, and this is the case that shows
        why they must still be checked against each other."""
        return self.node("pass_stmt", t)

    def _Name(self, t):
        return self.node("name", t, id=t.id)

    def _Constant(self, t):
        return self.node("constant", t, value=t.value)

    def _Attribute(self, t):
        n = self.node("attribute", t, attr=t.attr)
        self.part(n, "of", self.visit(t.value, n))
        return n

    def _Expr(self, t):
        return self.visit(t.value)


def intake(lib: Library, source: str, *, origin: str = "<unknown>") -> Intaken:
    """Reflect Python source into `lib`'s graph. Returns the module node and what could not be read.

    `origin` says where the source came from — a path, a tool call, a generator. It is a parameter because
    provenance is not derivable from the text, and because code that arrived from a tool call can differ
    on the next run.

    A `SyntaxError` propagates: source that does not parse is not partial understanding, it is not Python,
    and there is nothing honest to record about it."""
    walker = Intake(lib, origin)
    module = walker.visit(ast.parse(source))
    return Intaken(module=module, unmodelled=tuple(walker.unmodelled), origin=origin, _graph=lib.graph)


__all__ = ["intake", "Intake", "Intaken", "MODELLED"]
