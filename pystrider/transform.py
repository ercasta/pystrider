"""Transformation operators — materialize an edit as real source (the missing half of §3).

The analysis says *what is wrong* (an AttributeError on a None deref of `var` at `line`); a
transformation operator produces the *edited code* that removes it. This is means-ends's
"apply the operator" step made concrete: it rewrites the AST and unparses back to Python, so
the output is source a human can read and apply — not just a semantic effect.

`insert_none_guard` is the one operator the spike ships: wrap the statement that performs the
deref in `if VAR is not None:`. The design's "verify by re-execution" then re-intakes this
output and re-runs the analysis (see `analysis.repair`) — the edit is trusted only because the
outcome clears on the actual transformed code, not because the operator claims it will.
"""
from __future__ import annotations

import ast


def _covering_stmt(func: ast.FunctionDef, line: int) -> tuple[list[ast.stmt], int]:
    """The `(body_list, index)` of the top-level function statement whose span covers `line`.
    Operates on the function's own body only (branch/nesting recursion is a later slice)."""
    for i, stmt in enumerate(func.body):
        end = getattr(stmt, "end_lineno", stmt.lineno)
        if stmt.lineno <= line <= end:
            return func.body, i
    raise ValueError(f"no top-level statement covers line {line}")


def insert_none_guard(src: str, var: str, line: int) -> str:
    """Return `src` with the statement covering `line` wrapped in `if {var} is not None:`.

    The edit is minimal and local: only the covering statement is guarded; everything else is
    byte-for-byte re-emitted by `ast.unparse`.
    """
    tree = ast.parse(src)
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    body, idx = _covering_stmt(func, line)
    target = body[idx]
    guard = ast.If(
        test=ast.Compare(left=ast.Name(id=var, ctx=ast.Load()),
                         ops=[ast.IsNot()],
                         comparators=[ast.Constant(value=None)]),
        body=[target],
        orelse=[],
    )
    body[idx] = guard
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _guard_if(var: str, body: list[ast.stmt]) -> ast.If:
    return ast.If(
        test=ast.Compare(left=ast.Name(id=var, ctx=ast.Load()),
                         ops=[ast.IsNot()], comparators=[ast.Constant(value=None)]),
        body=body, orelse=[])


def insert_none_guard_range(src: str, var: str, from_line: int, to_line: int) -> str:
    """Wrap the contiguous run of top-level statements spanning `from_line..to_line` in a single
    `if {var} is not None:`. A wider (larger) edit than `insert_none_guard` — used to give CHOOSE
    a real size gradient among candidate repairs."""
    tree = ast.parse(src)
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    lo = hi = None
    for i, stmt in enumerate(func.body):
        end = getattr(stmt, "end_lineno", stmt.lineno)
        if stmt.lineno <= to_line and end >= from_line:          # overlaps the range
            lo = i if lo is None else lo
            hi = i
    if lo is None:
        raise ValueError(f"no statements span lines {from_line}..{to_line}")
    guarded = func.body[lo:hi + 1]
    func.body[lo:hi + 1] = [_guard_if(var, guarded)]
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)
