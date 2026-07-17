"""Climbing the cliff — a SEMANTIC idiom rule recognizes a summing loop, generalizing across spellings.

`understand_robustness` found a CLIFF: a hand-rolled accumulator loop (`s = 0; for e in xs: s += e`) was
not recognized, because the recognizer there is purely SYNTACTIC (AST templates + spelling rewrites), and
a loop is a different shape. But the cliff is not a wall — it is the top of the SYNTACTIC rule tier. The
loop is reachable by a SEMANTIC rule that reasons about what the code DOES (dataflow), not how it looks:

    an accumulator `acc`, initialized to the operator's IDENTITY before a `for tgt in iter:` whose body
    accumulates `acc <op>= f(tgt)`, computes  reduce(<op>, f(tgt) for tgt in iter)  — i.e. `sum` when op
    is + and init is 0, `prod` when op is * and init is 1.

That is ONE rule, and it generalizes across the spellings that made the syntactic tier whack-a-mole: the
accumulator's name, `acc += x` vs `acc = acc + x`, a transformed summand `acc += f(e)`. It also stays
HONEST: it checks the init matches the operator's identity (so `s = 1; s += e` is NOT a clean sum), it
distinguishes + from * (a product is not a sum), and it abstains on a body that isn't a clean fold
(control flow inside the loop) — the NEXT cliff, one tier up.

So the answer to "why can't semantic idioms be reached?": they CAN — with rules ABOUT BEHAVIOR rather than
syntax. The cliff moves up a tier; it does not disappear, and abstention still holds the floor beyond the
top rule. This probe adds the loop→fold rule on top of `understand_robustness`'s normalizer and re-measures.

Run it: `python -m experiments.understand_semantic`
"""
from __future__ import annotations

import ast
import copy
import textwrap
from dataclasses import dataclass

from experiments.pattern_compose import REPERTOIRE
from experiments.understand_robustness import _inline, _dealias, _match, _shape, _verdict


# --- the SEMANTIC idiom rule: recognize an accumulator loop as a fold (sum / prod) ------------------

_IDENTITY = {ast.Add: (0, "sum"), ast.Mult: (1, "prod")}


def recognize_fold(for_stmt: ast.For, init_binds: dict) -> "tuple[str, str, str, ast.AST, ast.AST] | None":
    """Recognize `for tgt in iter: acc <op>= f(tgt)` (init'd to op's identity) as a fold. Returns
    (acc, reducer, tgt, iter, summand) or None. This is dataflow, not shape: it reads the accumulation
    operator and the initial value, and it REFUSES a loop whose init isn't the operator's identity, whose
    body isn't a single clean accumulation, or whose operator has no known identity — honest, not a guess."""
    if not isinstance(for_stmt.target, ast.Name) or len(for_stmt.body) != 1:
        return None                                     # control flow / multiple statements -> next cliff
    tgt = for_stmt.target.id
    stmt = for_stmt.body[0]
    if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
        acc, op, rhs = stmt.target.id, stmt.op, stmt.value
    elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        acc, v = stmt.targets[0].id, stmt.value          # `acc = acc <op> rhs`  (either operand order)
        if isinstance(v, ast.BinOp) and isinstance(v.left, ast.Name) and v.left.id == acc:
            op, rhs = v.op, v.right
        elif isinstance(v, ast.BinOp) and isinstance(v.right, ast.Name) and v.right.id == acc:
            op, rhs = v.op, v.left
        else:
            return None
    else:
        return None
    spec = _IDENTITY.get(type(op))
    if spec is None:
        return None                                     # an operator we have no fold rule for
    identity, reducer = spec
    init = init_binds.get(acc)
    if not isinstance(init, ast.Constant) or init.value != identity:
        return None                                     # init isn't the operator's identity -> not a clean fold
    return acc, reducer, tgt, for_stmt.iter, rhs


def _fold_expr(reducer: str, tgt: str, it: ast.AST, summand: ast.AST) -> ast.AST:
    """Build the fold as an expression: `reducer(iter)` when the summand IS the loop element, else
    `reducer(summand for tgt in iter)`."""
    if isinstance(summand, ast.Name) and summand.id == tgt:
        arg: ast.AST = copy.deepcopy(it)
    else:
        gen = ast.comprehension(target=ast.Name(tgt, ast.Store()), iter=copy.deepcopy(it), ifs=[], is_async=0)
        arg = ast.GeneratorExp(elt=copy.deepcopy(summand), generators=[gen])
    return ast.Call(func=ast.Name(reducer, ast.Load()), args=[arg], keywords=[])


# --- normalize WITH the semantic rule, then match (extends understand_robustness) --------------------

def _canonical_expr_semantic(code: str) -> "ast.AST | None":
    """Like `understand_robustness._canonical_expr`, but a `for` loop is given to the semantic fold rule
    instead of being an automatic cliff: a recognized fold binds its accumulator to the fold expression."""
    mod = ast.parse(textwrap.dedent(code))
    binds: dict = {}
    final: "ast.AST | None" = None
    for stmt in mod.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            binds[stmt.targets[0].id] = _inline(stmt.value, binds)
        elif isinstance(stmt, ast.For):
            fold = recognize_fold(stmt, binds)
            if fold is None:
                return None                              # the NEXT cliff (still honest)
            acc, reducer, tgt, it, rhs = fold
            binds[acc] = _fold_expr(reducer, tgt, _inline(it, binds), rhs)
        elif isinstance(stmt, ast.Expr):
            final = _inline(stmt.value, binds)
        else:
            return None
    return _dealias(final) if final is not None else None


def semantic_recognize(code: str) -> "tuple[str, str] | str | None":
    """Normalize (now with the loop→fold rule), then match with hole-consistency. `"CLIFF"` = the code
    still can't be normalized (the next tier); None = normalized but no repertoire pattern matched."""
    expr = _canonical_expr_semantic(code)
    if expr is None:
        return "CLIFF"
    for intent, pats in REPERTOIRE.items():
        for p in pats:
            if _match(_shape(p, distinct=True), expr, {}, consistent=True):
                return (intent, p.name)
    return None


def fold_readout(code: str) -> str:
    """A human readout of what the semantic rule saw in a loop (for the walkthrough)."""
    for stmt in ast.parse(textwrap.dedent(code)).body:
        if isinstance(stmt, ast.For):
            binds = {s.targets[0].id: s.value for s in ast.parse(textwrap.dedent(code)).body
                     if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name)}
            f = recognize_fold(stmt, binds)
            if f:
                _, reducer, tgt, it, rhs = f
                over = ast.unparse(it) if isinstance(rhs, ast.Name) and rhs.id == tgt else f"{ast.unparse(rhs)} for {tgt} in {ast.unparse(it)}"
                return f"{reducer}({over})"
            return "not-a-clean-fold"
    return "no-loop"


# --- the cases: spellings of a summing loop, plus the honesty checks --------------------------------

@dataclass(frozen=True)
class Case:
    label: str
    code: str
    truth: "tuple[str, str] | None"
    note: str


MEAN = ("average_of", "mean")
CASES: tuple[Case, ...] = (
    Case("loop_sum", "s = 0\nfor e in xs:\n    s += e\ns / len(xs)", MEAN, "the accumulator loop that WAS the cliff"),
    Case("loop_assign_form", "s = 0\nfor e in xs:\n    s = s + e\ns / len(xs)", MEAN, "same idiom, `s = s + e`"),
    Case("loop_renamed", "total = 0\nfor x in items:\n    total += x\ntotal / len(items)", MEAN, "different names"),
    Case("loop_product", "p = 1\nfor e in xs:\n    p *= e\np / len(xs)", None, "a PRODUCT, not a sum — must not be a mean"),
    Case("loop_bad_init", "s = 1\nfor e in xs:\n    s += e\ns / len(xs)", None, "init 1 with + : sum+1, not clean -> abstain"),
    Case("loop_conditional", "s = 0\nfor e in xs:\n    s += e\n    if e > 10:\n        s += 1\ns / len(xs)", None,
         "control flow inside the loop — not a clean fold: the NEXT cliff"),
)


def main() -> None:
    print("UNDERSTAND SEMANTIC — a dataflow rule recognizes a summing loop; does it climb the cliff, honestly?\n")
    print(f"  {'case':18} {'truth':22} {'fold seen':22} {'recognized':22} verdict")
    print(f"  {'-'*18} {'-'*22} {'-'*22} {'-'*22} {'-'*8}")
    reclaimed, cliffs, wrong = [], [], []
    for c in CASES:
        r = semantic_recognize(c.code)
        v = _verdict(r, c.truth)
        if v == "WRONG":
            wrong.append(c.label)
        if v == "CORRECT" and c.truth == MEAN:
            reclaimed.append(c.label)
        if r == "CLIFF":
            cliffs.append(c.label)
        print(f"  {c.label:18} {str(c.truth):22} {fold_readout(c.code):22} {str(r):22} {v}")

    print(f"\n  {len(wrong)} mis-identified: {wrong or '[]'};  {len(reclaimed)} summing-loop spellings RECLAIMED "
          f"as mean: {reclaimed};")
    print(f"  honest abstentions (product / bad-init / control-flow): "
          f"{[c.label for c in CASES if c.truth is None and _verdict(semantic_recognize(c.code), c.truth) == 'CORRECT']}\n")

    print("So semantic idioms ARE reachable by rules — ONE dataflow rule (init = operator identity, then")
    print("accumulate) recognizes the summing loop across names, `+=` vs `= +`, and transformed summands,")
    print("and stays honest: a product is not a sum, a non-identity init is not a clean sum, and a loop with")
    print("control flow inside is the NEXT cliff (abstained, not guessed). The cliff moved up a tier; it did")
    print("not vanish — understanding grows one idiom-rule at a time, with abstention still holding the floor.")


if __name__ == "__main__":
    main()
