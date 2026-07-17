"""Understand-half scalability probe — how much spelling variation survives pattern RECOGNITION?

`pattern_compose.recognize` closes the round-trip only because the code was GENERATED from the exact
templates. Real understanding means recognizing code SOMEONE ELSE wrote, spelled however they chose —
the "normalization tax" (`docs/codegen_understand.md`). This sweep measures it the way the footprint
scalability sweep measured soundness: take ONE intent (`average_of` → mean) written many human ways, and
classify each recognition attempt. It probes BOTH failure directions, which are the recognition analogs
of the footprint findings:

  * UNDER-recognition (a real instance not matched) — the normalization tax: an intermediate variable, a
    library call, an accumulator loop. Fixable by NORMALIZING to a canonical form before matching — up to
    a CLIFF where syntactic normalization can't reach (a loop that means `sum`) and honesty demands an
    UNKNOWN (the membrane), never a guess.
  * OVER-recognition (matching something that is NOT the pattern) — the recognition analog of silent
    unsoundness. Naive wildcard matching accepts `sum(xs) / len(ys)` as a mean, because its two holes are
    independent. The fix is HOLE-CONSISTENCY: a repeated hole must bind the SAME sub-expression.

PART 1 runs the naive matcher (independent wildcards, exact spelling) and finds both a silent MIS-ID and
several misses. PART 2 adds the two fixes — hole-consistency + a little normalization (inline a temp,
de-alias a library call) — and measures what they RECLAIM and what stays an honest CLIFF. The headline is
the same shape as the scalability sweep: how much of real-code variation is finite-rule-payable, and where
does it hand off to the membrane.

Run it: `python -m experiments.understand_robustness`
"""
from __future__ import annotations

import ast
import copy
import textwrap
from dataclasses import dataclass

from experiments.pattern_compose import REPERTOIRE, Pattern


# --- structural matching, with an optional HOLE-CONSISTENCY fix --------------------------------------

def _match(pat: ast.AST, tgt: ast.AST, binds: dict, consistent: bool) -> bool:
    """Structural AST match. A hole (a Name whose id starts `HOLE`) is a wildcard. With `consistent`, a
    repeated hole id must bind structurally-equal subtrees (so `sum(x)/len(y)` is NOT a mean)."""
    if isinstance(pat, ast.Name) and pat.id.startswith("HOLE"):
        if not consistent:
            return True
        if pat.id in binds:
            return ast.dump(binds[pat.id]) == ast.dump(tgt)
        binds[pat.id] = tgt
        return True
    if type(pat) is not type(tgt):
        return False
    for f in pat._fields:
        pv, tv = getattr(pat, f, None), getattr(tgt, f, None)
        if isinstance(pv, list):
            if not isinstance(tv, list) or len(pv) != len(tv):
                return False
            for a, b in zip(pv, tv):
                if isinstance(a, ast.AST):
                    if not (isinstance(b, ast.AST) and _match(a, b, binds, consistent)):
                        return False
                elif a != b:
                    return False
        elif isinstance(pv, ast.AST):
            if not (isinstance(tv, ast.AST) and _match(pv, tv, binds, consistent)):
                return False
        elif pv != tv:
            return False
    return True


def _shape(p: Pattern, distinct: bool) -> ast.AST:
    """The pattern's template as an AST with its holes replaced by markers — one shared `HOLE` (naive) or
    a distinct `HOLE_<name>` per hole (so consistency can tie repeated holes together)."""
    fills = {h: (f"HOLE_{h}" if distinct else "HOLE") for h in p.holes}
    return ast.parse(p.template.format(**fills), mode="eval").body


def naive_recognize(code: str) -> "tuple[str, str] | None":
    """Today's recognizer: parse the code as a single expression, match with INDEPENDENT wildcards."""
    try:
        tgt = ast.parse(code, mode="eval").body
    except SyntaxError:
        return None                                      # multi-statement code isn't even parsed
    for intent, pats in REPERTOIRE.items():
        for p in pats:
            if _match(_shape(p, distinct=False), tgt, {}, consistent=False):
                return (intent, p.name)
    return None


# --- PART 2 fix: NORMALIZE (inline temps, de-alias) then match with HOLE-CONSISTENCY -----------------

def _inline(node: ast.AST, binds: dict) -> ast.AST:
    """Copy-propagate: replace each temp Name by the (already-inlined) expression assigned to it."""
    class R(ast.NodeTransformer):
        def visit_Name(self, n):
            return copy.deepcopy(binds[n.id]) if n.id in binds else n
    return R().visit(copy.deepcopy(node))


def _dealias(node: ast.AST) -> ast.AST:
    """A declared library equivalence: `…mean(X)` / `mean(X)` == `sum(X) / len(X)` — one normalization rule."""
    class R(ast.NodeTransformer):
        def visit_Call(self, n):
            self.generic_visit(n)
            f = n.func
            is_mean = (isinstance(f, ast.Attribute) and f.attr == "mean") or (isinstance(f, ast.Name) and f.id == "mean")
            if is_mean and len(n.args) == 1:
                a = n.args[0]
                mk = lambda fn: ast.Call(func=ast.Name(fn, ast.Load()), args=[copy.deepcopy(a)], keywords=[])
                return ast.BinOp(left=mk("sum"), op=ast.Div(), right=mk("len"))
            return n
    return R().visit(node)


def _canonical_expr(code: str) -> "ast.AST | None":
    """Reduce a code snippet to a single canonical expression: inline simple `name = expr` temps into the
    trailing expression, then de-alias. Returns None if the code carries an un-normalizable construct (a
    loop / conditional) — the syntactic CLIFF where recognition must abstain, not guess."""
    mod = ast.parse(textwrap.dedent(code))
    binds: dict = {}
    final: "ast.AST | None" = None
    for stmt in mod.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            binds[stmt.targets[0].id] = _inline(stmt.value, binds)
        elif isinstance(stmt, ast.Expr):
            final = _inline(stmt.value, binds)
        else:
            return None                                  # a For/If/… — beyond syntactic normalization
    return _dealias(final) if final is not None else None


def robust_recognize(code: str) -> "tuple[str, str] | str | None":
    """Normalize to a canonical expression, then match with HOLE-CONSISTENCY. Returns the (intent,pattern),
    or `"CLIFF"` when the code can't be normalized (honest unknown), or None (normalized, nothing matched)."""
    expr = _canonical_expr(code)
    if expr is None:
        return "CLIFF"
    for intent, pats in REPERTOIRE.items():
        for p in pats:
            if _match(_shape(p, distinct=True), expr, {}, consistent=True):
                return (intent, p.name)
    return None


# --- the cases: one intent, many human spellings, with ground-truth recognition ---------------------

@dataclass(frozen=True)
class Case:
    label: str
    code: str
    truth: "tuple[str, str] | None"   # what recognition SHOULD return (None = not this pattern at all)
    note: str


MEAN = ("average_of", "mean")
CASES: tuple[Case, ...] = (
    Case("template", "sum(xs) / len(xs)", MEAN, "the exact template spelling"),
    Case("other_var", "sum(ys) / len(ys)", MEAN, "same shape, different variable"),
    Case("total_baseline", "sum(xs)", ("average_of", "total"), "a different pattern in the repertoire"),
    Case("mismatched_args", "sum(xs) / len(ys)", None, "sum of xs over len of ys — NOT a mean (over-match risk)"),
    Case("sum_over_const", "sum(xs) / 2", None, "sum over a constant — not an average"),
    Case("intermediate_var", "t = sum(xs)\nt / len(xs)", MEAN, "an intermediate variable (normalizable: inline)"),
    Case("library_call", "statistics.mean(xs)", MEAN, "a library call (normalizable: de-alias)"),
    Case("accumulator_loop", "s = 0\nfor e in xs:\n    s += e\ns / len(xs)", MEAN,
         "a hand-rolled sum loop — a SEMANTIC idiom, beyond syntactic normalization"),
)


def _verdict(recog, truth) -> str:
    if recog == truth:
        return "CORRECT"
    if recog in (None, "CLIFF"):
        return "MISSED" if truth is not None else "CORRECT"   # abstaining on a non-instance is correct
    return "WRONG"                                             # named a pattern that isn't the truth


def main() -> None:
    print("UNDERSTAND ROBUSTNESS — how much spelling variation survives recognition? (intent: average = mean)\n")

    print("PART 1 — NAIVE recognizer (exact spelling, independent wildcards):\n")
    print(f"  {'case':18} {'truth':22} {'recognized':22} verdict")
    print(f"  {'-'*18} {'-'*22} {'-'*22} {'-'*8}")
    naive_wrong, naive_missed = [], []
    for c in CASES:
        r = naive_recognize(c.code)
        v = _verdict(r, c.truth)
        if v == "WRONG":
            naive_wrong.append(c.label)
        if v == "MISSED":
            naive_missed.append(c.label)
        print(f"  {c.label:18} {str(c.truth):22} {str(r):22} {v}")
    print(f"\n  naive: {len(naive_wrong)} MIS-IDENTIFIED (silent, FATAL): {naive_wrong};  "
          f"{len(naive_missed)} MISSED (normalization tax): {naive_missed}\n")

    print("PART 2 — with HOLE-CONSISTENCY + light NORMALIZATION (inline temp, de-alias library call):\n")
    print(f"  {'case':18} {'truth':22} {'recognized':22} verdict")
    print(f"  {'-'*18} {'-'*22} {'-'*22} {'-'*8}")
    reclaimed, cliffs, wrong = [], [], []
    for c in CASES:
        r = robust_recognize(c.code)
        v = _verdict(r, c.truth)
        if v == "WRONG":
            wrong.append(c.label)
        if v == "CORRECT" and c.label in naive_missed:
            reclaimed.append(c.label)
        if r == "CLIFF":
            cliffs.append(c.label)
        print(f"  {c.label:18} {str(c.truth):22} {str(r):22} {v}")
    print(f"\n  robust: {len(wrong)} mis-identified: {wrong or '[]'} (hole-consistency killed the over-match);")
    print(f"          {len(reclaimed)} RECLAIMED by normalization: {reclaimed};")
    print(f"          {len(cliffs)} honest CLIFF (abstained -> membrane): {cliffs}\n")

    print("The tax is finite-rule-payable across a BAND of spelling variation (different vars, intermediate")
    print("temps, library aliases) — each a small normalization rule — and hole-consistency removes the")
    print("silent mis-ID. The CLIFF is at SEMANTIC idioms (a loop that means `sum`): syntactic normalization")
    print("can't reach it, so recognition abstains honestly rather than guess. That boundary — normalize vs")
    print("abstain — is the same membrane the scalability sweep found, now on the understand side. The next")
    print("rule-growth question is measurable: run this over a REAL corpus of one intent's spellings.")


if __name__ == "__main__":
    main()
