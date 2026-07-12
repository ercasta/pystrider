"""Demo 1 - the core loop: SUPPOSE a value, RUN the semantics, read the OUTCOME, REPAIR it.

The whole idea of pystrider in one screen. We do NOT scan for a bug pattern; we *suppose* an
input value, *symbolically run* the function by applying an operational semantics expressed as
UGM rules, and read what happens - with a real provenance trace behind the verdict. Then we
retrieve a repair from an effect-keyed library, materialize it as real Python, and verify it by
re-running the analysis on the edited code.

    python demos/01_none_deref.py
"""
from _util import banner, show_source, show_trace, try_changing

from pystrider import intake_function, analyze, choose_repair
import pystrider.operators as ops


SOURCE = """
def read_config(env):
    cfg = env
    return cfg.get("port")
"""


def main() -> None:
    banner("1. SOURCE UNDER ANALYSIS")
    show_source(SOURCE)
    ik = intake_function(SOURCE)
    print(f"\n  intake -> {len(ik.facts)} AST+CFG facts, "
          f"{len(ik.attributes)} attribute-access site(s). No data-flow graph: value flow is "
          f"COMPUTED by the semantics rules, not precomputed.")

    banner("2. SUPPOSE env = None  ->  run the semantics  ->  OUTCOME + trace")
    outs = analyze(ik, {"env": "none"})
    for o in outs:
        print("  OUTCOME:", o.headline())
        print("  RECORD trace (real UGM provenance, rendered by ask_goal 'why'):")
        show_trace(o.trace, indent="      ")

    banner("3. SOUNDNESS  ->  SUPPOSE env = <some object>  (must NOT fire)")
    print("  outcomes:", analyze(ik, {"env": "object"}) or "none  (no false positive)")

    banner("4. REPAIR  ->  retrieve (backward-CHAIN), materialize, verify, CHOOSE the best")
    sel = choose_repair(ik, {"env": "none"}, outs[0])
    for c in sel.candidates:
        mark = "verified" if c.cleared else "UNVERIFIED"
        print(f"    - {c.name:16} tests {c.var:4} | fit {c.fit:.2f} | {mark} | {c.description}")
    print(f"\n  CHOOSE picks: {sel.winner.name}  ->")
    show_source(sel.winner.v2_source, indent="      ")

    try_changing(
        "* Move the deref before the assignment (`return env.get(...)` first) - same outcome, shorter trace.",
        "* Add a guard `if cfg is not None:` around the return - the outcome disappears (no repair needed).",
        "* Suppose a second param and deref it too - two independent outcomes, each with its own repair.",
    )


if __name__ == "__main__":
    main()
