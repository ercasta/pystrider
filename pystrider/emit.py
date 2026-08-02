"""EMIT — graph data becomes real Python text.

The inverse of `pystrider.intake`, over the same Python-shaped vocabulary. Together they close the loop the
whole bet rests on:

    construct a description  ->  lower it to Python shape  ->  EMIT text
                                                                  |
    recognize it  <-  lift  <-  intake that text  <----------------+

**⭐ Why the round trip must go through TEXT, and not through the graph.** A consumer that writes
structure and reads it back on the same graph is checking its own intention: the edges it is looking for
are the edges it just wrote. Going out to source and back in means what gets recognized is an artifact
that was *parsed*, carrying `from_code` because `intake` stamped it — a strictly stronger claim than "we
meant to emit this". This is the same discipline that made the old `ITERATION_FROM_INTAKE` stamp
`from_code`, and it is why emit is worth having even when nobody needs the text for its own sake.

**Rendering goes through `ast.unparse`.** Emit's real work is the mapping from our vocabulary to Python's
AST node types; formatting and operator precedence are a solved problem and hand-rolling a pretty-printer
would only add a second place for `a + b * c` to come out wrong. The output is valid Python by
construction rather than by inspection.

**⚠ Two refusals, and they are the same refusal `recognize` makes.**

* A node we cannot render is refused **by name**, with what we can render — the reach membrane again,
  pointing the other way.
* A `partial` node is refused outright. We did not read all of it, so we cannot write all of it, and
  emitting the part we understood would produce code that is confidently wrong — a loop missing the
  statement we could not model. An incomplete description must not be *rendered* either.
"""
from __future__ import annotations

import ast

from .library import Library

_BOOL = {"and": ast.And, "or": ast.Or}
_UNARY = {"not": ast.Not, "neg": ast.USub, "pos": ast.UAdd, "invert": ast.Invert}

_CMP = {"eq": ast.Eq, "ne": ast.NotEq, "lt": ast.Lt, "le": ast.LtE, "gt": ast.Gt, "ge": ast.GtE,
        "is": ast.Is, "is_not": ast.IsNot, "in": ast.In, "not_in": ast.NotIn}
_BIN = {"add": ast.Add, "sub": ast.Sub, "mul": ast.Mult, "div": ast.Div,
        "floordiv": ast.FloorDiv, "mod": ast.Mod, "pow": ast.Pow,
        "bitor": ast.BitOr, "bitand": ast.BitAnd, "bitxor": ast.BitXor,
        "lshift": ast.LShift, "rshift": ast.RShift, "matmul": ast.MatMult}

#: What emit can render. The mirror of `intake.MODELLED`, and deliberately a separate list: reading a
#: construct and writing one are different capabilities, and pretending one implies the other is how a
#: gap goes unnoticed until it produces wrong code.
RENDERABLE = ("module", "function_def", "class_def", "block", "for_stmt", "if_stmt", "call",
              "return_stmt", "assign", "aug_assign", "ann_assign", "assert_stmt",
              "import_stmt", "import_from", "alias", "compare", "binop", "bool_op", "unary_op",
              "if_expr", "subscript", "slice", "starred", "tuple", "list", "set", "dict", "pair",
              "keyword_arg", "fstring", "interpolation", "yield_expr",
              "name", "constant", "attribute", "pass_stmt")


class CannotEmit(Exception):
    """Refused: this node cannot be rendered faithfully, and a guess would be worse than a refusal."""


class Emit:
    """Builds a Python AST from graph structure. Dispatch is an explicit table, so an unrenderable kind
    is a lookup miss that must be answered rather than a silently generic fallthrough."""

    def __init__(self, lib: Library):
        self.g = lib.graph

    def node(self, n):
        g = self.g
        if n is None:
            raise CannotEmit("nothing to emit")
        if g.attr(n, "partial"):
            raise CannotEmit(
                f"{g.kind(n)} at line {g.attr(n, 'source_line')} is partial — it contains a construct "
                "intake could not model, so emitting it would produce code missing that construct")
        handler = getattr(self, f"_{g.kind(n)}", None)
        if handler is None:
            raise CannotEmit(f"cannot render a {g.kind(n)!r}; renderable: {', '.join(RENDERABLE)}")
        return handler(n)

    def stmts(self, block) -> list:
        """A `block` becomes a statement list. An empty block becomes `pass`, because Python has no way
        to write nothing and a bare `if:` is a syntax error rather than an empty branch."""
        out = [self.as_stmt(s) for s in self.g.targets(block, "stmt")]
        return out or [ast.Pass()]

    def as_stmt(self, n):
        """An expression standing where a statement belongs is wrapped, the inverse of intake's `Expr`."""
        built = self.node(n)
        return built if isinstance(built, ast.stmt) else ast.Expr(value=built)

    # --- the renderable kinds --------------------------------------------------------------------------

    def _module(self, n):
        return ast.Module(body=[self.as_stmt(d) for d in self.g.targets(n, "defines")], type_ignores=[])

    def _function_def(self, n):
        returns = self.g.target(n, "returns")
        return ast.FunctionDef(
            name=self.g.attr(n, "name"),
            args=self.signature(n, [self.arg(p) for p in self.g.targets(n, "param")]),
            body=self.stmts(self.g.target(n, "does")),
            decorator_list=[self.node(d) for d in self.g.targets(n, "decorator")],
            returns=self.node(returns) if returns else None)

    def arg(self, p):
        """One parameter, with its annotation. ⚠ ONE helper for EVERY kind, mirroring `intake.param`.

        The write half of the same bug: `signature` built keyword-only, positional-only, `*a` and `**k`
        arguments as `ast.arg(arg=name)`, dropping any annotation. Read and write are tracked as separate
        capabilities here precisely so a gap in one is not assumed absent from the other — and this one was
        in both, which is exactly why fixing only the side you noticed would have left it silent."""
        annotation = self.g.target(p, "annotation")
        return ast.arg(arg=self.g.attr(p, "name"),
                       annotation=self.node(annotation) if annotation else None)

    def signature(self, n, params):
        """Rebuild the full signature. `no_default` is a real node rather than `None` because a keyword-only
        argument without a default is positionally significant in `kw_defaults`."""
        def named(label):
            return [self.arg(p) for p in self.g.targets(n, label)]

        def defaults(label):
            return [None if self.g.kind(d) == "no_default" else self.node(d)
                    for d in self.g.targets(n, label)]

        vararg, kwarg = self.g.target(n, "vararg"), self.g.target(n, "kwarg")
        return ast.arguments(
            posonlyargs=named("posonly"), args=params, kwonlyargs=named("kwonly"),
            kw_defaults=defaults("kw_default"), defaults=defaults("default"),
            vararg=self.arg(vararg) if vararg else None,
            kwarg=self.arg(kwarg) if kwarg else None)

    def _block(self, n):
        raise CannotEmit("a block is a statement list, not an expression — emit its container")

    def _for_stmt(self, n):
        return ast.For(target=self.store(self.node(self.g.target(n, "binds"))),
                       iter=self.node(self.g.target(n, "over")),
                       body=self.stmts(self.g.target(n, "body")), orelse=[])

    def _if_stmt(self, n):
        otherwise = self.g.target(n, "otherwise")
        body = self.stmts(otherwise) if otherwise else []
        # ⚠ An empty else becomes NO else, not `else: pass`. Intake models an absent else as an empty
        # block, so rendering that block literally would grow an `else: pass` on every round trip —
        # structurally equivalent but textually divergent, and divergence that compounds is a bug.
        if otherwise is not None and not self.g.targets(otherwise, "stmt"):
            body = []
        return ast.If(test=self.node(self.g.target(n, "condition")),
                      body=self.stmts(self.g.target(n, "then")), orelse=body)

    def _call(self, n):
        return ast.Call(func=self.node(self.g.target(n, "callee")),
                        args=[self.node(a) for a in self.g.targets(n, "arg")],
                        keywords=[self.node(k) for k in self.g.targets(n, "kwarg")])

    def _return_stmt(self, n):
        value = self.g.target(n, "value")
        return ast.Return(value=self.node(value) if value else None)

    def _assign(self, n):
        return ast.Assign(targets=[self.store(self.node(t)) for t in self.g.targets(n, "target")],
                          value=self.node(self.g.target(n, "value")))

    def _compare(self, n):
        return ast.Compare(left=self.node(self.g.target(n, "left")),
                           ops=[_CMP[self.g.attr(n, "op")]()],
                           comparators=[self.node(self.g.target(n, "right"))])

    def _binop(self, n):
        return ast.BinOp(left=self.node(self.g.target(n, "left")),
                         op=_BIN[self.g.attr(n, "op")](),
                         right=self.node(self.g.target(n, "right")))

    def _pass_stmt(self, n):
        return ast.Pass()

    def _class_def(self, n):
        return ast.ClassDef(
            name=self.g.attr(n, "name"),
            bases=[self.node(b) for b in self.g.targets(n, "base")],
            keywords=[],
            body=self.stmts(self.g.target(n, "does")),
            decorator_list=[self.node(d) for d in self.g.targets(n, "decorator")])

    def _assert_stmt(self, n):
        msg = self.g.target(n, "message")
        return ast.Assert(test=self.node(self.g.target(n, "test")),
                          msg=self.node(msg) if msg else None)

    def _aug_assign(self, n):
        return ast.AugAssign(target=self.store(self.node(self.g.target(n, "target"))),
                             op=_BIN[self.g.attr(n, "op")](),
                             value=self.node(self.g.target(n, "value")))

    def _ann_assign(self, n):
        value = self.g.target(n, "value")
        return ast.AnnAssign(target=self.store(self.node(self.g.target(n, "target"))),
                             annotation=self.node(self.g.target(n, "annotation")),
                             value=self.node(value) if value else None,
                             simple=int(bool(self.g.attr(n, "simple"))))

    def _import_stmt(self, n):
        return ast.Import(names=[self.node(a) for a in self.g.targets(n, "alias")])

    def _import_from(self, n):
        return ast.ImportFrom(module=self.g.attr(n, "module"),
                              names=[self.node(a) for a in self.g.targets(n, "alias")],
                              level=self.g.attr(n, "level") or 0)

    def _alias(self, n):
        return ast.alias(name=self.g.attr(n, "name"), asname=self.g.attr(n, "asname"))

    def _bool_op(self, n):
        return ast.BoolOp(op=_BOOL[self.g.attr(n, "op")](),
                          values=[self.node(v) for v in self.g.targets(n, "operand")])

    def _unary_op(self, n):
        return ast.UnaryOp(op=_UNARY[self.g.attr(n, "op")](),
                           operand=self.node(self.g.target(n, "operand")))

    def _if_expr(self, n):
        return ast.IfExp(test=self.node(self.g.target(n, "condition")),
                         body=self.node(self.g.target(n, "then_value")),
                         orelse=self.node(self.g.target(n, "else_value")))

    def _subscript(self, n):
        return ast.Subscript(value=self.node(self.g.target(n, "of")),
                             slice=self.node(self.g.target(n, "index")), ctx=ast.Load())

    def _slice(self, n):
        def part(label):
            target = self.g.target(n, label)
            return self.node(target) if target else None
        return ast.Slice(lower=part("lower"), upper=part("upper"), step=part("step"))

    def _starred(self, n):
        return ast.Starred(value=self.node(self.g.target(n, "of")), ctx=ast.Load())

    def _tuple(self, n):
        return ast.Tuple(elts=self.items(n), ctx=ast.Load())

    def _list(self, n):
        return ast.List(elts=self.items(n), ctx=ast.Load())

    def _set(self, n):
        return ast.Set(elts=self.items(n))

    def items(self, n):
        return [self.node(e) for e in self.g.targets(n, "item")]

    def _dict(self, n):
        pairs = self.g.targets(n, "pair")
        return ast.Dict(keys=[self.node(self.g.target(p, "key")) for p in pairs],
                        values=[self.node(self.g.target(p, "value")) for p in pairs])

    def _pair(self, n):
        raise CannotEmit("a dict pair is not an expression — emit its dict")

    def _keyword_arg(self, n):
        return ast.keyword(arg=self.g.attr(n, "name"), value=self.node(self.g.target(n, "value")))

    def _fstring(self, n):
        return ast.JoinedStr(values=[self.node(p) for p in self.g.targets(n, "part")])

    def _interpolation(self, n):
        spec = self.g.target(n, "format")
        return ast.FormattedValue(value=self.node(self.g.target(n, "value")),
                                  conversion=self.g.attr(n, "conversion"),
                                  format_spec=self.node(spec) if spec else None)

    def _yield_expr(self, n):
        value = self.g.target(n, "value")
        return ast.Yield(value=self.node(value) if value else None)

    def _name(self, n):
        return ast.Name(id=self.g.attr(n, "id"), ctx=ast.Load())

    def _constant(self, n):
        return ast.Constant(value=self.g.attr(n, "value"))

    def _attribute(self, n):
        return ast.Attribute(value=self.node(self.g.target(n, "of")),
                             attr=self.g.attr(n, "attr"), ctx=ast.Load())

    @staticmethod
    def store(built):
        """A name being assigned to is the same node in a different context — Python's distinction, not
        ours, so it is applied here at the boundary rather than modelled in the graph."""
        built.ctx = ast.Store()
        return built


def emit(lib: Library, node: str) -> str:
    """Render `node` as Python source. Raises `CannotEmit` rather than guessing."""
    tree = ast.fix_missing_locations(Emit(lib).node(node))
    if not isinstance(tree, (ast.Module, ast.stmt, ast.expr)):
        raise CannotEmit(f"{node} did not render to something unparseable")
    return ast.unparse(tree)


__all__ = ["emit", "Emit", "CannotEmit", "RENDERABLE"]
