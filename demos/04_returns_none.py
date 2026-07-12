"""Demo 4 - a second effect kind: "returns None when a non-None was intended".

The point: the whole loop - an operational-semantics rule, an effect-keyed operator library,
backward-CHAIN retrieval, verify-by-re-execution, and graded CHOOSE - GENERALIZES past None-derefs
with NO new machinery. A second outcome is authored as one more `.cnl` rule plus two library
operators; everything else is reused.

    python demos/04_returns_none.py
"""
from _util import banner, show_source, show_trace, try_changing

from pystrider import intake_function, analyze, analyze_return_none, choose_repair
import pystrider.operators as ops


SOURCE = """
def lookup(cache, key):
    hit = cache
    return hit
"""


def main() -> None:
    banner("1. SOURCE - a function that may return None")
    show_source(SOURCE)
    ik = intake_function(SOURCE)

    banner("2. SUPPOSE cache = None  ->  the RETURN yields None (effect 2)")
    outs = analyze_return_none(ik, {"cache": "none"})
    for o in outs:
        print(f"    OUTCOME: `{o.label}` (line {o.line}) -> returns None [{o.kind}]")
        print("    trace:")
        show_trace(o.trace, indent="      ")
    print("\n  the None-deref effect (effect 1) does NOT fire here - no attribute access:",
          analyze(ik, {"cache": "none"}) or "[]")

    banner("3. REPAIR - retrieved for the `returns_none` effect key, verified, CHOSEN")
    sel = choose_repair(ik, {"cache": "none"}, outs[0],
                        provides_fn=ops.provides_return, analyzer=analyze_return_none)
    for c in sel.candidates:
        mark = "verified" if c.cleared else "UNVERIFIED"
        print(f"    - {c.name:15} | fit {c.fit:.2f} | {mark} | {c.description}")
    print(f"\n  CHOOSE picks the graded-best ({sel.winner.name}) ->")
    show_source(sel.winner.v2_source, indent="      ")

    try_changing(
        "* Suppose cache = <object> - the function returns non-None, so no outcome fires.",
        "* Add a deref `return hit.value` - now BOTH effects fire on the same function.",
        "* Add a third operator to pystrider/operators.py keyed to `returns_none` and watch CHOOSE",
        "  weigh it against the two coalesce edits (operators are DATA - no code change to the loop).",
    )


if __name__ == "__main__":
    main()
