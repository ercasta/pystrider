"""Python → propositions, with provenance, and gaps NAMED rather than dropped.

A port of `pystrider/intake.py`, and the port is smaller than survey §2 predicted
for a reason worth stating up front: **every substrate touch in that file goes
through five helpers**, and the ~40 AST handlers are pure walking. So what had to
be re-derived is the five (`node` / `part` / `placeholder` / `gap` / `unconsumed`)
against `facts.Facts`. The handlers came across as they were.

WHAT IS KEPT FROM THE OLD GENERATION, AND WHY EACH ONE IS NOT OPTIONAL — these are
lessons that cost measurements, and a port that quietly dropped them would look
identical until the same bug came back:

* **⭐ THE LOAD-BEARING RULE: an unmodelled construct makes its CONTAINER partial,
  and a partial node is refused.** Refusing a whole file over one comprehension is
  useless; dropping the comprehension silently is far worse — a loop understood
  two-thirds and presented as a complete iteration. The gap costs exactly the
  constructs containing it.
* **⚠⚠ `unconsumed` — the guard that found silent field dropping.** `def f(x: int)
  -> bool` was once intaken with an empty gap list, reported COMPLETE, and emitted
  as `def f(x)`. Annotations, decorators, defaults and `*args` were all read past
  in silence. The fix is structural: each handler declares what it CONSUMES and
  everything else non-empty is refused, so a new Python field, or a handler that
  stops reading one, becomes an honest gap rather than a silent loss. ⚠ And
  declaring a field consumed switches the guard OFF for it — `_CONSUMES["ClassDef"]`
  once listed `keywords` while the handler never visited them, so
  `class A(metaclass=M)` lost its metaclass. **Only list a field beside the code
  that reads it.**
* **⚠⚠ A PLACEHOLDER, because POSITION IS MEANING.** Recording a gap and linking
  nothing renumbers the readable parts: `f([c for c in xs], x)` kept one `arg` and
  was described as *"applies f to x"* — a confidently WRONG description, not a
  missed one. Ignorance gets a node, which is the thing a graph can point at.
* **A body is ONE `block` node with ordered `stmt` parts**, never N parts on the
  container — otherwise a description can only point at the first statement, and
  a three-line loop gets described by its first line.
* **⚠ Intake must not reuse a pattern's word.** Intake says `condition`, the
  pattern says `tests`; intake says `for_stmt`, the pattern says `iteration`. If
  they coincided the bridge would do nothing for that part while looking like it
  worked, and the perturbation pin would not bite there.

⭐ WHAT THE NEW SUBSTRATE CHANGED, AND IT IS AN IMPROVEMENT: engine 2 had three
mechanisms — a node's KIND, its ATTRIBUTES and its EDGES. Here all three are
propositions, so `partial` and `unknown_parts` stop being attribute slots that
only Python could read and become ordinary facts **an authored rule can reason
about**. The gap vocabulary is now in the same language as the patterns.

⚠ Intaking CODE is not the border ugm's own intake guards. Theirs guards an
authored claim a model could fabricate; code is an artifact that already parses.
So the refusal needed is not *malformed* but **not modelled** — a reach membrane,
not a trust boundary. `origin` stays a PARAMETER because provenance is not
derivable from text.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from .facts import Facts


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

_CMP = {ast.Eq: "eq", ast.NotEq: "ne", ast.Lt: "lt", ast.LtE: "le", ast.Gt: "gt", ast.GtE: "ge",
        ast.Is: "is", ast.IsNot: "is_not", ast.In: "in", ast.NotIn: "not_in"}
#: ⚠ The bitwise ops are here because leaving them out once refused `str | None`,
#: i.e. every modern union annotation. Nobody thinks of `|` as arithmetic; the
#: reach sweep found it, reading the table did not.
_BIN = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.Div: "div",
        ast.FloorDiv: "floordiv", ast.Mod: "mod", ast.Pow: "pow",
        ast.BitOr: "bitor", ast.BitAnd: "bitand", ast.BitXor: "bitxor",
        ast.LShift: "lshift", ast.RShift: "rshift", ast.MatMult: "matmul"}


@dataclass
class Intaken:
    """The module node, and an honest account of what could not be read.

    `unmodelled` is not an error list — it is the reach measurement, per file.
    """

    module: int
    unmodelled: Tuple[str, ...] = ()
    origin: str = "<unknown>"
    facts: Optional[Facts] = field(default=None, repr=False)

    @property
    def complete(self) -> bool:
        return not self.unmodelled


class Intake:
    """Reflects a Python AST into propositions. One node per construct.

    Not an `ast.NodeVisitor` subclass, on purpose: dispatch is an explicit table,
    so an unhandled node type is a **lookup miss that must be answered** rather
    than a silently inherited generic visit.
    """

    def __init__(self, facts: Facts, origin: str) -> None:
        self.f = facts
        self.origin = origin
        self.unmodelled: List[str] = []

    # --- the five primitives ---------------------------------------------

    def node(self, kind: str, tree: Any, **attrs: Any) -> int:
        """Mint a node for a construct, stamped with provenance and its line.

        ⚠ `source_line` is recorded HERE because attribution has to be an
        OBSERVED fact joined later, never derived — the lesson from getting loop
        attribution wrong the derived way.
        """
        n = self.f.node(f"{kind}@{getattr(tree, 'lineno', '?')}")
        self.f.fact(kind, n)
        # ⭐⭐ `readable` is what a description names to ABSTAIN — see `placeholder`,
        # which is the only thing that does not get it.
        self.f.fact("readable", n)
        # ⭐ `from_code` is what makes a later recognition a claim about the
        # ARTIFACT rather than about our own intention. Without it a round-trip
        # check verifies the graph we meant to build.
        self.f.fact("from_code", n)
        self.f.fact("origin", n, self.f.value(self.origin))
        line = getattr(tree, "lineno", None)
        if line is not None:
            self.f.fact("source_line", n, self.f.value(line))
        for label, payload in attrs.items():
            self.f.fact(label, n, self.f.value(payload))
        return n

    def part(self, parent: int, label: str, child: Any) -> None:
        """Attach a part. A gap in a child propagates UP, and **at its label**."""
        if child is None:
            return
        if child is UNREADABLE:
            child = self.placeholder(label)
        self.f.fact(label, parent, child)
        if self.f.has("partial", child):
            self.gap(parent, label)

    def placeholder(self, label: str) -> int:
        """⚠⚠ A node standing where an unreadable construct was — POSITION IS MEANING.

        ⭐⭐ **It is the one node intake does not call `readable`**, and that absence
        is what lets a DESCRIPTION abstain (`rules/patterns.ugm`). On engine 2 the
        same judgement lived in `patterns.py` as Python — which our own notes had
        flagged as the thing to move, *a judgement living where nothing can argue
        with it*. Here it is a member of the antecedent, so a description declares
        which of its parts it refuses to guess about, and another author can
        disagree by writing a different description.

        ⚠ It is asserted POSITIVELY, on the readable nodes, because a rule cannot
        say *nothing claims this*. §9's `-` means *an entry denies this*, never
        *for no entry* — so negation-as-failure is not available here and is not
        being faked.
        """
        n = self.f.node(f"unreadable@{label}")
        self.f.fact("unreadable", n)
        self.f.fact("from_code", n)
        self.f.fact("partial", n)
        return n

    def gap(self, parent: int, label: str) -> None:
        """Record that a part of `parent` could not be read, AT ITS LABEL.

        ⭐ The label is the refinement. `partial` alone is a single bit — *something
        below is unreadable* — with no way to ask *what*, so any hole darkened
        every description of the container, including ones that never named the
        part. `unknown_part(parent, <label>)` is the set-of-roles answer.

        ⚠ `partial` is still asserted and still propagates, because `emit` reads
        the blunt bit and must: a hole cannot be RENDERED whichever part it is in,
        but a hole in a part a description never names cannot make that
        description WRONG. Reading and writing have different obligations.
        """
        # ⚠ Idempotent per (parent, label). An unmodelled construct records its gap
        # twice otherwise — once where the handler is missing, once when `part`
        # sees the placeholder is partial — and `unknown_part` listed `iterated`
        # TWICE for one comprehension. Harmless to read and wrong to count.
        marker = self.f.rel(label)
        if marker not in [m for (m,) in self.f.of("unknown_part", parent)]:
            self.f.fact("unknown_part", parent, marker)
        if not self.f.has("partial", parent):
            self.f.fact("partial", parent)

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
        """⚠ A body is ONE node with ordered `stmt` parts, never N parts above it."""
        b = self.f.node("block")
        self.f.fact("block", b)
        self.f.fact("from_code", b)
        # ⚠ A block is minted here rather than through `node()` (it has no line of
        # its own), and the first version of the abstention therefore left it
        # WITHOUT `readable` — so every description binding a body went dark and
        # three pins went red. A node minted off the main path misses whatever the
        # main path stamps: the same shape as the `unconsumed` guard being bypassed
        # by never being called at a site.
        self.f.fact("readable", b)
        for s in statements:
            self.part(b, "stmt", self.visit(s, b, "stmt"))
        return b

    def param(self, a: ast.arg) -> int:
        """⚠ ONE shared helper, because a guard that must be remembered per site
        gets forgotten at one — which is exactly how annotations on keyword-only
        and `*args` parameters were dropped by both intake and emit while the
        round trip reported `complete`."""
        n = self.node("param", a, name=a.arg)
        self.unconsumed(a, n)
        return n

    # --- handlers ---------------------------------------------------------

    def _Module(self, t: ast.Module) -> int:
        n = self.f.node("module")
        self.f.fact("module", n)
        self.f.fact("from_code", n)
        self.f.fact("readable", n)
        self.f.fact("origin", n, self.f.value(self.origin))
        self.part(n, "body", self.block(t.body, n))
        self.unconsumed(t, n)
        return n

    def _FunctionDef(self, t: ast.FunctionDef) -> int:
        n = self.node("function", t, name=t.name)
        for a in t.args.args:
            self.part(n, "param", self.param(a))
        self.unconsumed(t.args, n)
        self.part(n, "body", self.block(t.body, n))
        self.unconsumed(t, n)
        return n

    def _For(self, t: ast.For) -> int:
        n = self.node("for_stmt", t)
        self.part(n, "target", self.visit(t.target, n, "target"))
        self.part(n, "iterated", self.visit(t.iter, n, "iterated"))
        self.part(n, "body", self.block(t.body, n))
        if t.orelse:
            self.part(n, "otherwise", self.block(t.orelse, n))
        self.unconsumed(t, n)
        return n

    def _If(self, t: ast.If) -> int:
        n = self.node("if_stmt", t)
        self.part(n, "condition", self.visit(t.test, n, "condition"))
        self.part(n, "then", self.block(t.body, n))
        # ⚠ An empty else is NO else, never `else: pass` — or the round trip grows
        # one every pass, which is divergence that compounds.
        if t.orelse:
            self.part(n, "otherwise", self.block(t.orelse, n))
        self.unconsumed(t, n)
        return n

    def _Call(self, t: ast.Call) -> int:
        n = self.node("call", t)
        self.part(n, "callee", self.visit(t.func, n, "callee"))
        for a in t.args:
            self.part(n, "arg", self.visit(a, n, "arg"))
        self.unconsumed(t, n)
        return n

    def _Return(self, t: ast.Return) -> int:
        n = self.node("return_stmt", t)
        self.part(n, "returned", self.visit(t.value, n, "returned") if t.value else None)
        self.unconsumed(t, n)
        return n

    def _Assign(self, t: ast.Assign) -> int:
        n = self.node("assign", t)
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
        n = self.node("comparison", t, operator=op)
        self.part(n, "left", self.visit(t.left, n, "left"))
        self.part(n, "right", self.visit(t.comparators[0], n, "right"))
        self.unconsumed(t, n)
        return n

    def _BinOp(self, t: ast.BinOp) -> Any:
        op = _BIN.get(type(t.op))
        if op is None:
            self.unmodelled.append(f"BinOp.{type(t.op).__name__}")
            return UNREADABLE
        n = self.node("arithmetic", t, operator=op)
        self.part(n, "left", self.visit(t.left, n, "left"))
        self.part(n, "right", self.visit(t.right, n, "right"))
        self.unconsumed(t, n)
        return n

    def _Name(self, t: ast.Name) -> int:
        n = self.node("name", t, id=t.id)
        self.unconsumed(t, n)
        return n

    def _Constant(self, t: ast.Constant) -> int:
        n = self.node("constant", t, literal=t.value)
        self.unconsumed(t, n)
        return n

    def _Attribute(self, t: ast.Attribute) -> int:
        n = self.node("attribute", t, attr=t.attr)
        self.part(n, "of", self.visit(t.value, n, "of"))
        self.unconsumed(t, n)
        return n

    def _Expr(self, t: ast.Expr) -> Any:
        # An expression statement is its expression; there is nothing else to say.
        return self.visit(t.value)

    def _Pass(self, t: ast.Pass) -> int:
        n = self.node("no_op", t)
        self.unconsumed(t, n)
        return n


def intake(source: str, facts: Facts, origin: str) -> Intaken:
    """Read Python text into `facts`.

    ⚠ `origin` is a PARAMETER, not something derived from the text, because code
    may arrive as a tool call result and provenance is not recoverable from it.
    """
    walker = Intake(facts, origin)
    module = walker._Module(ast.parse(source))
    return Intaken(module=module, unmodelled=tuple(walker.unmodelled),
                   origin=origin, facts=facts)
