"""Demo 5 - whole-function auto-fix: repair to a fixpoint, every outcome, regression-checked.

The other demos fix ONE site. This one drives the repair as a means-ends loop toward a GOAL STATE -
a clean function. While any outcome of ANY effect remains under the hypothesis, it retrieves and
verifies candidate edits, keeps only those that make progress AND introduce no new outcome
(regression-checking), CHOOSEs the graded-best, applies it, and re-analyzes - until the function is
clean or honestly stuck. The output is edited source plus an audit log of what it did and why.

    python demos/05_whole_function_repair.py
"""
from _util import banner, show_source, try_changing

from pystrider import intake_function, analyze_all, repair_all


SOURCE = """
def process(cfg, data):
    conn = cfg
    a = conn.open()
    rows = data
    return rows
"""


def main() -> None:
    banner("1. SOURCE - two DIFFERENT bugs, two DIFFERENT effects")
    show_source(SOURCE)
    ik = intake_function(SOURCE)
    hyp = {"cfg": "none", "data": "none"}
    print("\n  outcomes under cfg=None, data=None:")
    for o in analyze_all(ik, hyp):
        print(f"    - {o.label:12} (line {o.line}) -> {o.kind}")

    banner("2. repair_all  ->  fix EVERY outcome, each edit verified + regression-checked")
    plan = repair_all(ik, hyp)
    for line in plan.summary():
        print("  " + line)

    banner("3. FINAL SOURCE (clean under re-execution)")
    show_source(plan.source)
    residual = analyze_all(intake_function(plan.source), hyp)
    print("\n  re-analysis of the edited source:", residual or "clean - no outcome remains")

    try_changing(
        "* Add a third bug (another deref) - repair_all fixes it too, in one more step.",
        "* Cap the budget: repair_all(ik, hyp, max_steps=1) - it fixes one and reports `stuck` honestly.",
        "* Make one bug unfixable (deref a non-variable base) - repair_all stops with `stuck` set,",
        "  rather than pretending; the audit log shows exactly how far it got.",
    )


if __name__ == "__main__":
    main()
