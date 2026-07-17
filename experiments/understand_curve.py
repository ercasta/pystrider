"""The RECLAIM CURVE — measure, over REAL code, how far a few idiom rules get you.

`understand_semantic` showed the cliff is climbable one idiom-rule-tier at a time, each rule generalizing
across a spelling family. The open question that decides whether the understand-half SCALES: over REAL
code, does a HANDFUL of idiom rules cover most of it (the curve saturates fast — tractable rule-growth), or
is real code a long tail of one-offs (the curve stays low — the membrane does the heavy lifting)?

This probe answers it empirically for one well-defined, ubiquitous slice — the `for` loop — over the
Python STANDARD LIBRARY (real code, written by many people, none of it ours). It runs a small library of
idiom recognizers, each ONE rule for ONE family:

    fold        acc = <identity>; for e in it: acc <op>= f(e)      -> sum / prod / count   (dataflow)
    map         out = [];         for e in it: out.append(f(e))    -> [f(e) for e in it]
    filter      out = [];         for e in it: if p(e): out.append(e)
    dict-build  d = {};           for …:        d[k] = v

Every recognizer is CONSERVATIVE (adjacent init, single-statement body) so a match is high-confidence and
honest — the established property (0 mis-ID). What no tier recognizes is the CLIFF: a genuinely imperative
loop (side effects, multi-statement body, control flow) — the residual that needs a higher rule-tier or the
membrane. So the recognized fraction is a sound LOWER BOUND on idiom coverage, and the curve's shape is the
information: how quickly coverage saturates, and how big the honest residual is.

Run it: `python -m experiments.understand_curve`
"""
from __future__ import annotations

import ast
import glob
import os
from collections import Counter
from dataclasses import dataclass

from experiments.understand_semantic import recognize_fold


# --- the idiom recognizers: each ONE rule for ONE family (for_stmt + preceding binds -> idiom name) --

def _empty_list(n: ast.AST) -> bool:
    return (isinstance(n, ast.List) and not n.elts) or (
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "list" and not n.args)


def _empty_dict(n: ast.AST) -> bool:
    return (isinstance(n, ast.Dict) and not n.keys) or (
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "dict" and not n.args)


def _append_coll(stmt: ast.AST) -> "str | None":
    """The collection name if `stmt` is `coll.append(EXPR)`."""
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        f = stmt.value.func
        if isinstance(f, ast.Attribute) and f.attr == "append" and isinstance(f.value, ast.Name) and len(stmt.value.args) == 1:
            return f.value.id
    return None


def _idiom(fs: ast.For, binds: dict) -> "str | None":
    """Recognize the loop as an idiom, or None (the cliff). Conservative by design."""
    fold = recognize_fold(fs, binds)                     # the dataflow tier (sum/prod/count)
    if fold is not None:
        _, reducer, _, _, rhs = fold
        return "count" if reducer == "sum" and isinstance(rhs, ast.Constant) and rhs.value == 1 else reducer
    if len(fs.body) == 1:
        s = fs.body[0]
        coll = _append_coll(s)
        if coll and _empty_list(binds.get(coll)):
            return "map"
        if isinstance(s, ast.If) and not s.orelse and len(s.body) == 1:
            c = _append_coll(s.body[0])
            if c and _empty_list(binds.get(c)):
                return "filter"
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Subscript) \
                and isinstance(s.targets[0].value, ast.Name) and _empty_dict(binds.get(s.targets[0].value.id)):
            return "dict-build"
    return None


# --- scan a corpus: classify every `for` loop with the binds in scope before it ---------------------

@dataclass
class Hit:
    idiom: "str | None"
    node: ast.For


def _child_blocks(s: ast.AST) -> "list[list]":
    blocks = [b for a in ("body", "orelse", "finalbody") if isinstance((b := getattr(s, a, None)), list)]
    blocks += [h.body for h in getattr(s, "handlers", []) or []]
    return blocks


def _scan_block(stmts: "list", out: "list[Hit]") -> None:
    binds: dict = {}
    for s in stmts:
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
            binds[s.targets[0].id] = s.value            # track adjacent inits (local dataflow)
        if isinstance(s, ast.For):
            out.append(Hit(_idiom(s, dict(binds)), s))
        for b in _child_blocks(s):
            _scan_block(b, out)


def scan_corpus(files: "list[str]") -> "list[Hit]":
    hits: "list[Hit]" = []
    for fp in files:
        try:
            tree = ast.parse(open(fp, encoding="utf-8", errors="ignore").read())
        except (SyntaxError, ValueError):
            continue
        _scan_block(tree.body, hits)
    return hits


# --- the curve ------------------------------------------------------------------------------------

def _bar(frac: float, width: int = 34) -> str:
    return "#" * round(frac * width)


def main() -> None:
    stdlib = os.path.dirname(os.__file__)
    files = sorted(glob.glob(os.path.join(stdlib, "*.py")))
    hits = scan_corpus(files)
    total = len(hits)
    recognized = [h for h in hits if h.idiom is not None]
    counts = Counter(h.idiom for h in recognized)

    print(f"RECLAIM CURVE — for-loop idiom coverage over the Python standard library\n")
    print(f"  corpus: {len(files)} stdlib files, {total} `for` loops\n")

    print("  per-idiom coverage (one rule per family):")
    for idiom, n in counts.most_common():
        print(f"    {idiom:12} {_bar(n / total):34} {n:5}  ({100 * n / total:4.1f}%)")
    cliff = total - len(recognized)
    print(f"    {'CLIFF':12} {_bar(cliff / total):34} {cliff:5}  ({100 * cliff / total:4.1f}%)\n")

    print("  reclaim curve — cumulative coverage as idiom tiers are added (most-common first):")
    cum = 0
    for idiom, n in counts.most_common():
        cum += n
        print(f"    + {idiom:12} -> {100 * cum / total:5.1f}%   {_bar(cum / total)}")
    print(f"    residual CLIFF -> {100 * cliff / total:5.1f}%  (needs a higher idiom-tier or the membrane)\n")

    # characterize the cliff — is it a recognizer-strictness artifact, or genuinely imperative code?
    cliff_nodes = [h.node for h in hits if h.idiom is None]
    blen = Counter(min(len(n.body), 4) for n in cliff_nodes)
    multi = sum(v for k, v in blen.items() if k >= 2)
    singles = [n.body[0] for n in cliff_nodes if len(n.body) == 1]

    def _kind(s: ast.AST) -> str:
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
            return "side-effect call  (for x in xs: f(x))"
        if isinstance(s, ast.If):
            return "conditional        (for x in xs: if …)"
        if isinstance(s, ast.Assign):
            return "scalar assign"
        return type(s).__name__
    kinds = Counter(_kind(s) for s in singles)
    # headroom: single-statement collection mutations a few more idiom rules could still reclaim.
    headroom = sum(1 for s in singles if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
                   and isinstance(s.value.func, ast.Attribute)
                   and s.value.func.attr in ("append", "add", "update", "extend"))

    print("  what the CLIFF actually is (is it strictness, or genuinely imperative?):")
    print(f"    multi-statement bodies (2+):   {multi:5}  ({100 * multi / total:4.1f}%)  -- genuinely compound loops")
    for k, n in kinds.most_common(4):
        print(f"    single: {k:36} {n:5}  ({100 * n / total:4.1f}%)")
    print(f"    (only ~{headroom} single-stmt collection-mutations remain uncaught -> conservatism costs ~{100*headroom/total:.0f}%, not the story)\n")

    print("  a sample of CLIFF loops (genuinely imperative — the honest residual):")
    for h in [x for x in hits if x.idiom is None][:5]:
        print(f"    - {ast.unparse(h.node).splitlines()[0][:86]}")
    print()
    print(f"  READING: only {100 * len(recognized) / total:.0f}% of real loops reduce to a clean value-idiom;")
    print(f"  the curve is FLAT, not fast-saturating, and the {100 * cliff / total:.0f}% residual is REAL — ~half are")
    print("  multi-statement imperative bodies and ~1-in-8 are bare side-effect (foreach) loops, neither of")
    print("  which is a value-comprehension. So understanding ARBITRARY foreign loop-code by idiom rules has")
    print("  a long tail: the symbolic core covers a minority (honestly), and the rest is the membrane. This")
    print("  CORRECTS the toy-case optimism — and it is specific to recovering a loop's value-intent, not to")
    print("  all understanding (a call to a known API is 'understood' cheaply — the absorb track).")


if __name__ == "__main__":
    main()
