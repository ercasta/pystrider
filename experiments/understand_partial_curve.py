"""Does the PARTIAL curve keep climbing — and is it HONEST? (the informative follow-up)

`understand_partial` lifted loop coverage from 4% (holistic) to 52% (≥1 value-aspect) with three aspect
rules. Naming those aspects into a summary would be semantic chunking — no new information. The informative
questions are the ones this probe measures, over the same real corpus (stdlib for-loops):

  1. CURVE SHAPE — add more aspect rules (here: min/max-reduce, `if e < acc: acc = e`). Does coverage keep
     climbing, and with what marginal return per rule? A curve still rising says rule-growth pays; a plateau
     says the residual is the irreducible membrane (genuine side-effects + control).

  2. FAITHFULNESS — the honesty check every prior sweep had. The flat walker reports `if e > 0:
     out.append(e)` as plain `collect`, silently DROPPING the guard — so some of the 52% is OVER-CLAIMED
     (an aspect asserted unconditionally that actually fires only under a condition). This measures how much,
     by tracking whether each value-aspect sits under a guard. Fixing it = tagging the aspect `(cond)`, the
     partial-recognition analog of footprint abstention: describe the aspect AND its condition, or say so.

The point is not a prettier output; it is: how far does the symbolic understand-half reach as rules grow,
and is the coverage it claims real. Recognition stays honest — a guarded aspect is labelled, not asserted flat.

Run it: `python -m experiments.understand_partial_curve`
"""
from __future__ import annotations

import ast
import glob
import os

from experiments.understand_curve import _child_blocks, scan_corpus
from experiments.understand_partial import _aspect, VALUE_ASPECTS

VALUE2 = VALUE_ASPECTS | {"minmax-reduce"}


def _minmax(s: ast.AST) -> "str | None":
    """`if <acc> <cmp> <expr>: <acc> = <expr'>` — a reduce-by-comparison (running min/max). Recognized as
    one aspect (`minmax-reduce`) without committing to the direction (honest partial)."""
    if not (isinstance(s, ast.If) and not s.orelse and len(s.body) == 1):
        return None
    b = s.body[0]
    if not (isinstance(b, ast.Assign) and len(b.targets) == 1 and isinstance(b.targets[0], ast.Name)):
        return None
    acc = b.targets[0].id
    t = s.test
    if isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
        if any(isinstance(n, ast.Name) and n.id == acc for n in [t.left, *t.comparators]):
            return "minmax-reduce"
    return None


def describe(stmts: "list", guarded: bool, out: "list[str]") -> None:
    """Guard-AWARE aspect walk: a value-aspect found under a conditional is tagged `(cond)` (so the guard is
    not silently dropped), and an `if` that is itself a min/max-reduce is recognized as one aspect."""
    for s in stmts:
        mm = _minmax(s)
        if mm:
            out.append(mm)
            continue
        a = _aspect(s)
        if a is not None:
            out.append(a + ("(cond)" if guarded and a in VALUE_ASPECTS else ""))
        elif isinstance(s, ast.If):
            describe(s.body, True, out)
            describe(s.orelse, True, out)
        else:
            for b in _child_blocks(s):
                describe(b, guarded, out)


def _base(a: str) -> str:
    return a.replace("(cond)", "")


def main() -> None:
    files = sorted(glob.glob(os.path.join(os.path.dirname(os.__file__), "*.py")))
    hits = scan_corpus(files)
    total = len(hits)

    # per loop: the guard-aware aspect list, and the set of value-aspect TYPES it has.
    per_loop = []
    for h in hits:
        out: "list[str]" = []
        describe(h.node.body, False, out)
        per_loop.append(out)

    def covers(types: set) -> int:
        return sum(1 for a in per_loop if any(_base(x) in types for x in a))

    print(f"PARTIAL CURVE — does coverage climb with more rules, and is it honest? ({total} loops)\n")

    # (1) marginal reclaim curve: add value-aspect types most-common-first, cumulative loop coverage.
    freq = {t: covers({t}) for t in VALUE2}
    order = sorted(VALUE2, key=lambda t: -freq[t])
    print("  (1) marginal reclaim curve — cumulative loops with >=1 value-aspect as rules are added:")
    added: set = set()
    prev = 0
    for t in order:
        added.add(t)
        cum = covers(added)
        marg = cum - prev
        prev = cum
        bar = "#" * round(cum / total * 34)
        print(f"    + {t:14} -> {100*cum/total:5.1f}%  (+{100*marg/total:4.1f}%)  {bar}")
    print(f"    holistic was 3.6%. The marginal per rule is the signal: still climbing vs plateauing.\n")

    # (2) faithfulness: how many recognized value-aspects were UNDER A GUARD (flat walker dropped it)?
    val_occurrences = [x for a in per_loop for x in a if _base(x) in VALUE_ASPECTS]
    guarded = [x for x in val_occurrences if x.endswith("(cond)")]
    print("  (2) faithfulness — was the 52% honest, or were guards silently dropped?")
    print(f"    {len(guarded)} of {len(val_occurrences)} value-aspects ({100*len(guarded)/max(len(val_occurrences),1):.0f}%) sit UNDER A GUARD")
    print(f"    — the flat walker reported these as UNCONDITIONAL (e.g. `collect` for `if p: out.append`),")
    print(f"    over-claiming. Guard-aware recognition labels them `(cond)` instead of asserting them flat.\n")

    # the irreducible residual — what stays unrecognized after the value rules (the genuine membrane).
    from collections import Counter
    residual = Counter(_base(x) for a in per_loop for x in a if _base(x) not in VALUE2)
    res_total = sum(residual.values())
    print("  the irreducible residual (not a value-aspect — genuine effects/control/state):")
    for k, n in residual.most_common():
        print(f"    {k:14} {n:6}  ({100*n/res_total:4.1f}% of residual actions)")
    print()
    print("  READING: (1) the curve's marginal return per added rule tells you if understanding is a paying")
    print("  rule-growth program or a plateau at the membrane; (2) a non-trivial slice of the 52% was guarded,")
    print("  so faithful partial recognition must carry the CONDITION, not just the aspect — the same honesty")
    print("  discipline (describe precisely or abstain) as the footprint and scalability sweeps. Naming aspects")
    print("  into a summary (semantic chunking) is downstream of BOTH answers, and informative only after them.")


if __name__ == "__main__":
    main()
