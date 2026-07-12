"""Demo 2 - value flow that is state-threaded: reassignment, branches, and loops.

The naive "a variable has one value" model (SSA) gets `y = a; y = b` wrong. pystrider threads
value through a pre-materialized `(program-point, variable)` CELL lattice, so reassignment,
branch-merge, and bounded loop unrolling are all correct - and every value UNION at a join is a
rule DERIVATION (the frame rule firing once per incoming edge), never a Python-computed lattice
meet.

    python demos/02_state_threading.py
"""
from _util import banner, show_source, try_changing

from pystrider import intake_function, analyze


REASSIGN = """
def pick(a, b):
    y = a
    y = b
    return y.run()
"""

BRANCH = """
def choose(flag, a, b):
    if flag:
        y = a
    else:
        y = b
    return y.run()
"""

LOOP = """
def drain(seed, item):
    y = seed
    while item:
        y = item
    return y.run()
"""


def _report(title: str, src: str, hypotheses: list[dict]) -> None:
    banner(title)
    show_source(src)
    ik = intake_function(src)
    for hyp in hypotheses:
        outs = analyze(ik, hyp)
        verdict = "AttributeError" if outs else "safe"
        pretty = ", ".join(f"{k}={'None' if v == 'none' else 'obj'}" for k, v in hyp.items())
        print(f"    suppose {pretty:28} -> {verdict}")


def main() -> None:
    _report("REASSIGNMENT - the deref reads the LAST value written (not both)", REASSIGN, [
        {"a": "none", "b": "object"},   # y ends as b (object) -> safe, despite a=None
        {"a": "object", "b": "none"},   # y ends as b (None)   -> raises
    ])
    _report("BRANCH-MERGE - the join is the UNION of both arms (may-analysis)", BRANCH, [
        {"flag": "object", "a": "object", "b": "none"},   # else-arm can bind None -> may raise
        {"flag": "object", "a": "object", "b": "object"},  # neither arm is None    -> safe
    ])
    _report("LOOP (unrolled to the fuel budget) - union over 0..k iterations", LOOP, [
        {"seed": "none", "item": "object"},   # 0 iterations: y stays seed=None -> may raise
        {"seed": "object", "item": "none"},   # >=1 iteration: y becomes item=None -> may raise
        {"seed": "object", "item": "object"},  # every path non-None -> safe
    ])

    try_changing(
        "* In REASSIGN, swap the two assignments - the verdicts flip (the LAST write wins).",
        "* In BRANCH, delete the `else:` arm - the fall-through path keeps the pre-branch value.",
        "* Loop unrolling depth is a knob: `intake_function(LOOP, loop_unroll=1)` misses a bug that",
        "  first appears on the 2nd iteration - the pre-materialized state pool IS the fuel budget.",
    )


if __name__ == "__main__":
    main()
