"""End-to-end walkthrough of the spike. Run:  python -m pystrider.demo

Mirrors the design's vertical spike, steps 1-5, printing what the engine did at each stage.
"""
from __future__ import annotations

from .intake import intake_function
from .analysis import analyze, guarded_variant

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

    _banner("5b. MODIFICATION  -- insert `if x is not None:` guard, re-execute")
    site = ik.attributes[0]
    guard = guarded_variant(ik, "x", site)
    after = analyze(ik, {"x": "none"}, extra_facts=guard)
    print("  V2 facts added:", guard)
    print("  outcomes under x=None after the edit:",
          after or "none  OK (guard makes the deref unreachable -- outcome cleared)")


if __name__ == "__main__":
    main()
