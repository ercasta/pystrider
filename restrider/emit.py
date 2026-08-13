"""Propositions → Python, via `ast.unparse`.

The mirror of `intake`, and deliberately the smaller half: rendering goes through
`ast.unparse`, so the output is **valid Python by construction** and emit's real
work is only the vocabulary → AST-node mapping.

WHAT IS KEPT FROM THE OLD GENERATION:

* **⚠ `RENDERABLE` is a SEPARATE list from what intake models.** Reading a
  construct and writing one are different capabilities, and collapsing the two
  lists is how a gap in one silently becomes a claim about the other.
* **Emit refuses a `partial` node** — we did not read all of it, so we cannot
  write all of it. ⚠ It reads the BLUNT bit (`partial`) and not the refined
  `unknown_part`, on purpose: a hole cannot be rendered whichever part it is in.
* **⚠ An empty else renders as NO else**, never `else: pass`, or the round trip
  grows one every pass — divergence that compounds. Pinned by round-tripping
  TWICE, because stability is a separate claim from equivalence.

**⚠⚠ AND THE ONE THAT COST A REACH MEASUREMENT: STABILITY IS NOT FIDELITY.** An
emit-vs-emit round trip is a clean fixpoint on code that has ALREADY lost
something — the second pass has nothing left to drop. Only comparing against the
ORIGINAL SOURCE catches a silent deletion. Any sweep built on this module must
compare against the source.
"""
from __future__ import annotations

import ast
from typing import Any, List, Optional

from .facts import Facts
from .intake import _BIN, _CMP

_CMP_BACK = {v: k for k, v in _CMP.items()}
_BIN_BACK = {v: k for k, v in _BIN.items()}

#: What emit can WRITE. Separate from what intake can read, on purpose.
RENDERABLE = (
    "module", "block", "function", "param", "for_stmt", "if_stmt", "call",
    "return_stmt", "assign", "comparison", "arithmetic", "name", "constant",
    "attribute", "no_op",
)


class Unrenderable(Exception):
    """Refused BY NAME. Never approximated, never silently skipped."""


class Emit:
    def __init__(self, facts: Facts) -> None:
        self.f = facts

    def kind_of(self, n: int) -> Optional[str]:
        """Which construct this node is.

        Asked by trying the renderable vocabulary rather than by keeping a Python
        map beside the graph — a side map is state the rules cannot see, which is
        the thing this substrate exists to stop.
        """
        for kind in RENDERABLE:
            if self.f.has(kind, n):
                return kind
        return None

    def node(self, n: int) -> ast.AST:
        if self.f.has("partial", n):
            raise Unrenderable(
                f"{self.f.show(n)} is partial — something below it was never read, "
                f"so writing it would be inventing that part"
            )
        kind = self.kind_of(n)
        if kind is None:
            raise Unrenderable(f"{self.f.show(n)} has no renderable kind")
        return getattr(self, f"_{kind}")(n)

    def body(self, n: int) -> List[ast.stmt]:
        """A block back into a statement list, in deposit order."""
        out: List[ast.stmt] = []
        for (child,) in self.f.of("stmt", n):
            rendered = self.node(child)
            out.append(rendered if isinstance(rendered, ast.stmt)
                       else ast.Expr(value=rendered))
        return out

    # --- the vocabulary ---------------------------------------------------

    def _module(self, n: int) -> ast.Module:
        return ast.Module(body=self.body(self.f.one("body", n)), type_ignores=[])

    def _block(self, n: int) -> ast.AST:
        raise Unrenderable("a block is rendered by its container, never alone")

    def _function(self, n: int) -> ast.FunctionDef:
        params = [ast.arg(arg=self.f.text("name", p)) for (p,) in self.f.of("param", n)]
        return ast.FunctionDef(
            name=self.f.text("name", n),
            args=ast.arguments(posonlyargs=[], args=params, kwonlyargs=[],
                               kw_defaults=[], defaults=[]),
            body=self.body(self.f.one("body", n)),
            decorator_list=[], returns=None, type_params=[],
        )

    def _param(self, n: int) -> ast.arg:
        return ast.arg(arg=self.f.text("name", n))

    def _for_stmt(self, n: int) -> ast.For:
        otherwise = self.f.one("otherwise", n)
        return ast.For(
            target=self.node(self.f.one("target", n)),
            iter=self.node(self.f.one("iterated", n)),
            body=self.body(self.f.one("body", n)),
            # ⚠ empty, not `[ast.Pass()]` — see the module note
            orelse=self.body(otherwise) if otherwise is not None else [],
        )

    def _if_stmt(self, n: int) -> ast.If:
        otherwise = self.f.one("otherwise", n)
        return ast.If(
            test=self.node(self.f.one("condition", n)),
            body=self.body(self.f.one("then", n)),
            orelse=self.body(otherwise) if otherwise is not None else [],
        )

    def _call(self, n: int) -> ast.Call:
        return ast.Call(
            func=self.node(self.f.one("callee", n)),
            args=[self.node(a) for (a,) in self.f.of("arg", n)],
            keywords=[],
        )

    def _return_stmt(self, n: int) -> ast.Return:
        returned = self.f.one("returned", n)
        return ast.Return(value=None if returned is None else self.node(returned))

    def _assign(self, n: int) -> ast.Assign:
        return ast.Assign(
            targets=[self.node(t) for (t,) in self.f.of("assigned", n)],
            value=self.node(self.f.one("value", n)),
        )

    def _comparison(self, n: int) -> ast.Compare:
        op = _CMP_BACK[self.f.text("operator", n)]
        return ast.Compare(
            left=self.node(self.f.one("left", n)),
            ops=[op()],
            comparators=[self.node(self.f.one("right", n))],
        )

    def _arithmetic(self, n: int) -> ast.BinOp:
        op = _BIN_BACK[self.f.text("operator", n)]
        return ast.BinOp(left=self.node(self.f.one("left", n)), op=op(),
                         right=self.node(self.f.one("right", n)))

    def _name(self, n: int) -> ast.Name:
        return ast.Name(id=self.f.text("id", n))

    def _constant(self, n: int) -> ast.Constant:
        return ast.Constant(value=self.f.payload(self.f.one("literal", n)))

    def _attribute(self, n: int) -> ast.Attribute:
        return ast.Attribute(value=self.node(self.f.one("of", n)),
                             attr=self.f.text("attr", n))

    def _no_op(self, n: int) -> ast.Pass:
        return ast.Pass()


def emit(facts: Facts, node: int) -> str:
    """Render one node back to Python text."""
    tree = Emit(facts).node(node)
    return ast.unparse(ast.fix_missing_locations(tree))
