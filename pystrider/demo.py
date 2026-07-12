"""End-to-end walkthrough of the spike. Run:  python -m pystrider.demo

Mirrors the design's vertical spike, steps 1-5, printing what the engine did at each stage.
"""
from __future__ import annotations

from .intake import intake_function
from .analysis import analyze, repair, choose_repair
from .session import Session

SOURCE = """
def f(x):
    y = x
    return y.bar()
"""

# slice B: two functions in one shared graph, a value flowing across the call boundary.
CALLER = """
def caller(m):
    return callee(m)
"""
CALLEE = """
def callee(p):
    return p.foo()
"""


def _banner(t: str) -> None:
    print(f"\n{'='*70}\n{t}\n{'='*70}")


def main() -> None:
    print("SOURCE UNDER ANALYSIS:")
    print(SOURCE.strip())

    _banner("1-2. INTAKE  (ast -> AST+CFG base facts; no DFG overlay)")
    ik = intake_function(SOURCE)
    print(f"function {ik.func}({', '.join(ik.params)}) -> {len(ik.facts)} facts, "
          f"{len(ik.attributes)} attribute-access site(s)")
    for s, p, o in ik.facts:
        print(f"    {s:8} {p:12} {o}")

    _banner("3-4. SUPPOSE x = None  -- CHAIN semantics -- OUTCOME + RECORD trace")
    outs = analyze(ik, {"x": "none"})
    for o in outs:
        print("OUTCOME:", o.headline())
        print("  RECORD trace (real ugm provenance, rendered by ask_goal 'why'):")
        for line in o.trace:
            print("    " + line)
    if not outs:
        print("  (no outcome)")

    _banner("5a. SOUNDNESS CHECK  -- SUPPOSE x = <non-None object>  (must NOT fire)")
    print("  outcomes:", analyze(ik, {"x": "object"}) or "none  OK (no false AttributeError)")

    _banner("5b. MODIFICATION  -- materialize a real edit, then verify by re-execution")
    if outs:
        rep = repair(ik, {"x": "none"}, outs[0])
        print(f"  operator: insert `if {rep.var} is not None:` around the deref")
        print("  --- V2 SOURCE (actual edited Python, re-intaken & re-analyzed) ---")
        for ln in rep.v2_source.splitlines():
            print("    " + ln)
        print("  ----------------------------------------------------------------")
        print("  outcome under x=None after the edit:",
              "CLEARED  OK" if rep.cleared else f"STILL PRESENT: {rep.residual}")

    _banner("5c. MEANS-ENDS  -- RETRIEVE operators by effect (backward-CHAIN), verify, CHOOSE")
    if outs:
        sel = choose_repair(ik, {"x": "none"}, outs[0])
        print("  operators retrieved from the effect-keyed library for `attribute_error`,")
        print("  each materialized as real source and verified by re-execution:")
        for c in sel.candidates:
            mark = "verified" if c.cleared else "UNVERIFIED"
            print(f"    - {c.name:16} tests {c.var:2} | fit {c.fit:.2f} | {mark} | {c.description}")
        print("  CHOOSE (ugm firmware, graded — smallest/most-local wins):")
        for ln in sel.trace:
            print("    " + ln)
        print(f"  -> winner: {sel.winner.name} (`if {sel.winner.var} is not None:`)")

    _banner("6. SESSION  -- two functions in ONE shared graph; value flow across a call")
    print("  caller:", CALLER.strip().replace("\n", " ; "))
    print("  callee:", CALLEE.strip().replace("\n", " ; "))
    sess = Session()
    sess.add_function(CALLER)
    sess.add_function(CALLEE)
    for a, b, param in sess.link_calls():
        print(f"  linked: {a}(...) -> {b}, arg wired to param `{param}`")
    print("  SUPPOSE caller's input m = None  ->  outcome must surface INSIDE the callee:")
    xouts = sess.analyze_across_call("caller", {"m": "none"}, "callee")
    for o in xouts:
        print(f"    OUTCOME: {o.label} (line {o.line}) -> AttributeError, inside `callee`")
        print("    RECORD trace (value threads caller-cell -> link -> callee-cell -> deref):")
        for line in o.trace:
            print("      " + line)
    print("  SOUNDNESS: caller's input m = <object> ->",
          sess.analyze_across_call("caller", {"m": "object"}, "callee")
          or "no outcome  OK")


if __name__ == "__main__":
    main()
