"""End-to-end walkthrough of the spike. Run:  python -m pystrider.demo

Mirrors the design's vertical spike, steps 1-5, printing what the engine did at each stage.
"""
from __future__ import annotations

from .intake import intake_function
from .analysis import analyze, repair

SOURCE = """
def f(x):
    y = x
    return y.bar()
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


if __name__ == "__main__":
    main()
