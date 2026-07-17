"""PARTIAL recognizers — understand a loop by the ASPECTS it has, not as one whole idiom.

`understand_curve` found the holistic curve is flat: only ~4% of real stdlib loops reduce to a single
clean value-idiom, because a holistic recognizer is all-or-nothing — a loop is `map` only if its WHOLE
body is exactly the append, and 43% of real loops have multi-statement bodies, so they score zero.

The fix (the user's idea): recognize ASPECTS independently. A real loop often DOES several things — it
accumulates a sum, appends to a list, populates a dict, and calls a side effect. A partial recognizer
cares about ONE aspect and ignores the rest, so a compound loop is understood as the SET of aspects it
has, with the unrecognized statements left as an explicit, honest residual. This is exactly the footprint
move (describe what you can, abstain on the rest) applied to understanding — per-statement, not per-loop.

This probe measures the reclaim curve AGAIN, per-aspect, over the same corpus, and compares:

    HOLISTIC  — a loop counts only if it is ONE idiom end-to-end        (understand_curve: ~4%)
    PARTIAL   — a loop counts if it has >=1 recognized value-aspect;      (this probe)
                and, per action, what fraction of a loop's statements are recognized value-aspects

The value aspects (each ONE partial rule): ACCUMULATE (`x += …` / `x = x op …`), COLLECT
(`c.append/add/extend/update(…)`), INDEX-SET (`d[k] = …`). Everything else — a bare side-effect call,
plain control flow — is honest residual, named as such. Partial recognition never claims a loop's whole
intent; it names the value-building aspects it can prove, which is a strictly richer, still-honest read.

Run it: `python -m experiments.understand_curve` then `python -m experiments.understand_partial`.
"""
from __future__ import annotations

import ast
import glob
import os
from collections import Counter

from experiments.understand_curve import _child_blocks, scan_corpus, _idiom


VALUE_ASPECTS = {"accumulate", "collect", "index-set"}


def _refs_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node))


def _aspect(s: ast.AST) -> "str | None":
    """The aspect of a LEAF statement, or None if it is a compound statement to recurse into."""
    if isinstance(s, ast.AugAssign):
        return "accumulate"                              # x += … (or *=, etc.)
    if isinstance(s, ast.Assign) and len(s.targets) == 1:
        t = s.targets[0]
        if isinstance(t, ast.Subscript):
            return "index-set"                           # d[k] = … / a[i] = …
        if isinstance(t, ast.Name) and isinstance(s.value, ast.BinOp) and _refs_name(s.value, t.id):
            return "accumulate"                          # x = x + … (accumulate spelled long)
        return "scalar-assign"
    if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
        f = s.value.func
        if isinstance(f, ast.Attribute) and f.attr in ("append", "add", "extend", "update", "insert", "appendleft", "discard"):
            return "collect"                             # builds a collection
        return "side-effect"                             # a call we don't model (honest residual)
    if isinstance(s, (ast.Return, ast.Break, ast.Continue, ast.Raise, ast.Pass, ast.Assert,
                      ast.Delete, ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom)):
        return "control/other"
    if isinstance(s, ast.Expr):
        return "side-effect"                             # yield / await / bare expression
    return None                                          # if/for/while/with/try -> recurse into blocks


def leaf_aspects(stmts: "list") -> "list[str]":
    """Every leaf statement's aspect within a body, descending through control flow."""
    out: "list[str]" = []
    for s in stmts:
        a = _aspect(s)
        if a is not None:
            out.append(a)
        else:
            for b in _child_blocks(s):
                out.extend(leaf_aspects(b))
    return out


def main() -> None:
    stdlib = os.path.dirname(os.__file__)
    files = sorted(glob.glob(os.path.join(stdlib, "*.py")))
    hits = scan_corpus(files)                             # reuse the same corpus + loop extraction
    total = len(hits)

    holistic = sum(1 for h in hits if h.idiom is not None)

    loops_with_value = 0
    all_leaves: Counter = Counter()
    for h in hits:
        asp = leaf_aspects(h.node.body)
        all_leaves.update(asp)
        if any(a in VALUE_ASPECTS for a in asp):
            loops_with_value += 1
    total_leaves = sum(all_leaves.values())
    value_leaves = sum(all_leaves[a] for a in VALUE_ASPECTS)

    def bar(frac, w=34):
        return "#" * round(frac * w)

    print(f"PARTIAL vs HOLISTIC — understanding real loops by aspect ({total} loops, {len(files)} stdlib files)\n")

    print("  HOLISTIC (a loop = one whole idiom):")
    print(f"    fully recognized   {bar(holistic / total)} {100 * holistic / total:5.1f}%\n")

    print("  PARTIAL (a loop has >=1 recognized value-aspect):")
    print(f"    >=1 value aspect    {bar(loops_with_value / total)} {100 * loops_with_value / total:5.1f}%")
    print(f"    -> partial recognition lifts loop coverage {loops_with_value / max(holistic,1):.0f}x over holistic\n")

    print("  per-ACTION coverage (every leaf statement across all loop bodies):")
    for a, n in all_leaves.most_common():
        tag = "  (value aspect)" if a in VALUE_ASPECTS else "  (residual)"
        print(f"    {a:14} {bar(n / total_leaves)} {n:6}  ({100 * n / total_leaves:4.1f}%){tag}")
    print(f"\n    recognized value-actions: {value_leaves}/{total_leaves} = {100 * value_leaves / total_leaves:.0f}% "
          f"of everything real loops DO is a nameable value-building aspect;")
    print(f"    the rest is honest residual (side-effects + control), named, not guessed.\n")

    print("  READING: partial/aspect recognition is the right unit — it turns a 4% holistic curve into")
    print(f"  {100 * loops_with_value / total:.0f}% of loops with a recognized value-aspect and ~{100 * value_leaves / total_leaves:.0f}% of loop-actions named.")
    print("  It never claims a loop's whole intent (that stays the membrane's job); it proves the aspects it")
    print("  can and leaves the rest explicit — the footprint discipline, now for understanding. The next")
    print("  step is COMPOSING aspects into a loop summary ('builds `out` by map, tracks `n` by count').")


if __name__ == "__main__":
    main()
