"""Components → Python, via `ast.unparse`.

The mirror of `intake`, and deliberately the smaller half: rendering goes through
`ast.unparse`, so the output is **valid Python by construction** and emit's real
work is only the vocabulary → AST-node mapping.

WHAT IS KEPT FROM THE OLD GENERATION:

* **⚠ `_RENDERABLE` is a SEPARATE list from what intake models.** Reading a
  construct and writing one are different capabilities, and collapsing the two
  lists is how a gap in one silently becomes a claim about the other.
* **Emit refuses a `Partial` node** — we did not read all of it, so we cannot
  write all of it. ⚠ It reads the BLUNT tag (`Partial`) and not the refined
  `UnknownPart`, on purpose: a hole cannot be rendered whichever part it is in.
* **⚠ An empty else renders as NO else**, never `else: pass`, or the round trip
  grows one every pass — divergence that compounds. Pinned by round-tripping
  TWICE, because stability is a separate claim from equivalence.

**⚠⚠ AND THE ONE THAT COST A REACH MEASUREMENT: STABILITY IS NOT FIDELITY.** An
emit-vs-emit round trip is a clean fixpoint on code that has ALREADY lost
something — the second pass has nothing left to drop. Only comparing against the
ORIGINAL SOURCE catches a silent deletion. Any sweep built on this module must
compare against the source.

⚠⚠ 2026-08-29: reads `World` components directly now, not `Facts`. `kind_of()`
still probes a fixed list in order rather than keeping a side map — a side map
is state a rule cannot see, which is the thing this substrate exists to stop —
it just probes component TYPES (`World.has(n, ForStmt)`) instead of relation
NAMES (`Facts.has("for_stmt", n)`).
"""
from __future__ import annotations

import ast
from typing import List, Optional

from .intake import (_BIN, _CMP, Arg, Arithmetic, Assign, Assigned, Attribute,
                      Block, Body, Call, Callee, Comparison, Condition,
                      Constant, ForStmt, Function, HasParam, IfStmt, Iterated,
                      Left, Module, Name, NoOp, Of, Otherwise, Param, Partial,
                      Returned, ReturnStmt, Right, Stmt, Target, Then, Value,
                      decode_literal)

_CMP_BACK = {v: k for k, v in _CMP.items()}
_BIN_BACK = {v: k for k, v in _BIN.items()}

#: What emit can WRITE (the component, and the method name it dispatches to).
#: Separate from what intake can read, on purpose — probed IN ORDER, same as
#: the old relation-name list, just typed.
_RENDERABLE = (
    (Module, "module"), (Block, "block"), (Function, "function"),
    (Param, "param"), (ForStmt, "for_stmt"), (IfStmt, "if_stmt"),
    (Call, "call"), (ReturnStmt, "return_stmt"), (Assign, "assign"),
    (Comparison, "comparison"), (Arithmetic, "arithmetic"), (Name, "name"),
    (Constant, "constant"), (Attribute, "attribute"), (NoOp, "no_op"),
)


class Unrenderable(Exception):
    """Refused BY NAME. Never approximated, never silently skipped."""


class Emit:
    def __init__(self, world) -> None:
        self.w = world

    def kind_of(self, n: int) -> Optional[str]:
        """Which construct this node is, and the method name to render it.

        Asked by trying the renderable vocabulary rather than by keeping a Python
        map beside the graph — a side map is state the rules cannot see, which is
        the thing this substrate exists to stop.
        """
        for kind, name in _RENDERABLE:
            if self.w.has(n, kind):
                return name
        return None

    def node(self, n: int) -> ast.AST:
        if self.w.has(n, Partial):
            raise Unrenderable(
                f"{self.w.show(n)} is partial — something below it was never read, "
                f"so writing it would be inventing that part"
            )
        kind = self.kind_of(n)
        if kind is None:
            raise Unrenderable(f"{self.w.show(n)} has no renderable kind")
        return getattr(self, f"_{kind}")(n)

    def body(self, n: int) -> List[ast.stmt]:
        """A block back into a statement list, in attach order."""
        out: List[ast.stmt] = []
        for stmt in self.w.get_all(n, Stmt):
            rendered = self.node(stmt.entity)
            out.append(rendered if isinstance(rendered, ast.stmt)
                       else ast.Expr(value=rendered))
        return out

    # --- the vocabulary ---------------------------------------------------

    def _module(self, n: int) -> ast.Module:
        return ast.Module(body=self.body(self.w.get(n, Body).entity), type_ignores=[])

    def _block(self, n: int) -> ast.AST:
        raise Unrenderable("a block is rendered by its container, never alone")

    def _function(self, n: int) -> ast.FunctionDef:
        params = [ast.arg(arg=self.w.get(p.entity, Param).name)
                  for p in self.w.get_all(n, HasParam)]
        return ast.FunctionDef(
            name=self.w.get(n, Function).name,
            args=ast.arguments(posonlyargs=[], args=params, kwonlyargs=[],
                               kw_defaults=[], defaults=[]),
            body=self.body(self.w.get(n, Body).entity),
            decorator_list=[], returns=None, type_params=[],
        )

    def _param(self, n: int) -> ast.arg:
        return ast.arg(arg=self.w.get(n, Param).name)

    def _for_stmt(self, n: int) -> ast.For:
        otherwise = self.w.get(n, Otherwise)
        return ast.For(
            target=self.node(self.w.get(n, Target).entity),
            iter=self.node(self.w.get(n, Iterated).entity),
            body=self.body(self.w.get(n, Body).entity),
            # ⚠ empty, not `[ast.Pass()]` — see the module note
            orelse=self.body(otherwise.entity) if otherwise is not None else [],
        )

    def _if_stmt(self, n: int) -> ast.If:
        otherwise = self.w.get(n, Otherwise)
        return ast.If(
            test=self.node(self.w.get(n, Condition).entity),
            body=self.body(self.w.get(n, Then).entity),
            orelse=self.body(otherwise.entity) if otherwise is not None else [],
        )

    def _call(self, n: int) -> ast.Call:
        return ast.Call(
            func=self.node(self.w.get(n, Callee).entity),
            args=[self.node(a.entity) for a in self.w.get_all(n, Arg)],
            keywords=[],
        )

    def _return_stmt(self, n: int) -> ast.Return:
        returned = self.w.get(n, Returned)
        return ast.Return(value=None if returned is None else self.node(returned.entity))

    def _assign(self, n: int) -> ast.Assign:
        return ast.Assign(
            targets=[self.node(a.entity) for a in self.w.get_all(n, Assigned)],
            value=self.node(self.w.get(n, Value).entity),
        )

    def _comparison(self, n: int) -> ast.Compare:
        op = _CMP_BACK[self.w.get(n, Comparison).operator]
        return ast.Compare(
            left=self.node(self.w.get(n, Left).entity),
            ops=[op()],
            comparators=[self.node(self.w.get(n, Right).entity)],
        )

    def _arithmetic(self, n: int) -> ast.BinOp:
        op = _BIN_BACK[self.w.get(n, Arithmetic).operator]
        return ast.BinOp(left=self.node(self.w.get(n, Left).entity), op=op(),
                         right=self.node(self.w.get(n, Right).entity))

    def _name(self, n: int) -> ast.Name:
        return ast.Name(id=self.w.get(n, Name).id)

    def _constant(self, n: int) -> ast.Constant:
        return ast.Constant(value=decode_literal(self.w.get(n, Constant).literal))

    def _attribute(self, n: int) -> ast.Attribute:
        return ast.Attribute(value=self.node(self.w.get(n, Of).entity),
                             attr=self.w.get(n, Attribute).attr)

    def _no_op(self, n: int) -> ast.Pass:
        return ast.Pass()


def emit(world, node: int) -> str:
    """Render one node back to Python text."""
    tree = Emit(world).node(node)
    return ast.unparse(ast.fix_missing_locations(tree))
