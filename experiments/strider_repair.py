"""SLICE 3 — a GOAL drives a code repair, end to end, on the microfunctions engine.

Everything before this could read code and write code. Nothing could *do* anything: there was no goal, no
plan, and no repair. This is the slice where `pystrider`'s pipeline meets ugm's driver, and it is deliberately
the same bug `experiments/first_principles_repair.py` solved on the OLD engine — an off-by-one guard, given
only as examples — so the re-derivation can be checked against a real prior result rather than against our
own judgement.

**The bug, in the honest shape a bug report actually has.** No declared intent, no spec: an already-written
function, and a handful of `(input, expected)` pairs.

    def classify(age):
        if age > 18:      # says 'minor' at exactly 18
            return 'adult'
        else:
            return 'minor'

**⭐ THE ARCHITECTURAL FINDING, and it decided the whole design.** A repair must be JUDGED before it is
chosen, and the driver judges by *imagining*: it copies the graph onto a workbench and applies a candidate
there. `dispatch.service` refuses an imagined target, so nothing inside a plan can reach the world —
which means **a candidate repair can never be evaluated by running the patched code.** Execution is
structurally unavailable where the choosing happens, and that is a guarantee rather than an oversight.

So the evaluation has to DERIVE the answer from structure: read the operator, the threshold and the branch
bodies, and work out what the function would return. That is `pystrider/rules/repair.mf`'s `evaluate_case`,
and it is pure graph reasoning, so it runs happily on a copy.

    IMAGINATION DERIVES.  REALITY EXECUTES.

The derivation chooses the repair; running the emitted source afterwards is an *independent* gate saying
the derivation was right about the real language. Arriving at that split from the engine's constraints —
rather than adopting it as a principle — is the result worth keeping, because the old engine's repair probe
reached the identical division ("derive by reasoning, never by `exec`; confirm by execution at the end")
from the opposite direction.

**Two independent repair families**, so the search has a real choice: `relax_comparison` (the boundary is
right, the strictness is wrong) and `lower_threshold` (the strictness is right, the boundary is off by
one). Both genuinely fix these cases, which makes "which did it pick, and was the other also valid" a
question with an answer rather than a coincidence.

Run it: `python -m experiments.strider_repair`
"""
from __future__ import annotations

import pystrider
from pystrider.emit import emit
from pystrider.lift import reachable
from pystrider.mf import driver, goal as G, types

BUGGY = """def classify(age):
    if age > 18:
        return 'adult'
    else:
        return 'minor'"""

#: The intent, as a real bug report carries it: examples, not a specification. 18 is the one that fails.
CASES = ((18, "adult"), (25, "adult"), (10, "minor"))


def setup(source: str = BUGGY, cases=CASES):
    """Intake the code, declare the types the planner needs, and materialise the cases as graph nodes."""
    lib = pystrider.load()
    g = lib.graph
    got = pystrider.intake(lib, source, origin="bug report")

    # ⚠ Types are what make the repairs PROPOSABLE. `driver.proposals` enumerates type-valid bindings, so
    # an operation nothing can be bound to is an operation the planner cannot see.
    types.declare_type(g, "comparison", {"left": ("name", 1), "right": ("constant", 1)})
    types.declare_type(g, "case", {"of": ("if_stmt", 1)})
    types.declare_type(g, "checked_case", base="case", attrs={"agrees": True})

    branch = next(n for n in reachable(lib, got.module) if g.kind(n) == "if_stmt")

    # ⚠ The task node exists so `pursue` can reach BOTH the code and the cases from one subject. A case
    # points AT the code (metadata points inward), so copying from the code alone would not include them
    # and the goal would be unevaluable on every frame.
    task = g.mint("repair_task")
    g.link(task, "code", got.module)
    made = []
    for value, expected in cases:
        case = g.mint("case", input=value, expects=expected)
        g.link(case, "of", branch)
        g.link(task, "case", case)
        made.append(case)
    return lib, got, task, branch, made


def state_of_cases(lib, cases) -> dict:
    """What each case currently observes — the diagnosis, before anything is repaired."""
    g = lib.graph
    return {g.attr(c, "input"): (g.attr(c, "observed"), g.attr(c, "expects"), g.attr(c, "agrees"))
            for c in cases}


def diagnose(lib, cases) -> dict:
    """Run the evaluator once over the unrepaired code. Which examples disagree IS the diagnosis."""
    from pystrider.mf import function
    for c in cases:
        function.invoke(lib.graph, "evaluate_case", {"k": c})
    return state_of_cases(lib, cases)


def build_goal(lib, task, cases):
    """Every case must agree. Constraints on the WORLD, one per example."""
    g = lib.graph
    goal = G.open_goal(g, about=task, label="every example must agree")
    for c in cases:
        G.require_attr(g, goal, c, "agrees", True)
    return goal


def repair(source: str = BUGGY, cases=CASES, **kw) -> dict:
    """The whole loop: intake, diagnose, pursue a plan by imagining, then confirm in reality."""
    lib, got, task, _branch, case_nodes = setup(source, cases)
    g = lib.graph
    before = diagnose(lib, case_nodes)

    goal = build_goal(lib, task, case_nodes)
    thread = _thread(g)
    report = driver.pursue(g, goal, thread, task, **kw)
    return {"lib": lib, "module": got.module, "task": task, "cases": case_nodes,
            "before": before, "goal": goal, "report": report}


def _thread(g):
    from pystrider.mf import asm  # noqa: F401  (kept local: thread lives beside the driver, not the library)
    from pystrider.mf import thread as T
    return T.open_thread(g, "repair")


def adopt(out: dict) -> str:
    """Replay the imagined plan against the REAL graph, then emit the repaired source.

    `execution.execute` was written for workbench plans long before this existed and replays this one
    unchanged — the plan is not a value our planner returned, it is the frame path, which already *is*
    replayable."""
    from pystrider.mf import execution as E
    lib, report = out["lib"], out["report"]
    # ⚠ `execute` takes the winning LEAF FRAME, not the frame path. Passing the path silently replayed
    # nothing and returned a clean-looking report — caught only by the gate below noticing the emitted
    # code was unchanged. A plan that "succeeded" while changing nothing is exactly the failure the
    # independent gate exists for, and it found one on its first run.
    out["execution"] = E.execute(lib.graph, report["workbench"], report["frame"])
    return emit(lib, out["module"])


def confirm(repaired: str, intended, sweep=range(0, 40)) -> dict:
    """⭐ THE INDEPENDENT GATE. Run the emitted code for real, over MORE inputs than the examples.

    The plan was chosen by derivation on a workbench, where execution is structurally impossible. This is
    the other half of that split, and it is deliberately not the same question: the examples asked "does
    this repair satisfy the three cases I was given", and a repair can pass those while being wrong
    everywhere else. Sweeping past them is what distinguishes a fix from a fit.

    `intended` is the reference semantics — supplied by the caller, never derived from the repair, or the
    check would be grading the answer against itself."""
    namespace: dict = {}
    exec(compile(repaired, "<repaired>", "exec"), namespace)      # noqa: S102 — the point of the gate
    fn = namespace["classify"]
    disagreements = [x for x in sweep if fn(x) != intended(x)]
    return {"ran": True, "checked": len(list(sweep)), "disagreements": disagreements,
            "generalises": not disagreements}


def main() -> None:
    out = repair()
    lib, report = out["lib"], out["report"]

    print("=== the bug, as reported ===")
    print(BUGGY)
    print("\n=== diagnosis (derived, nothing executed) ===")
    for value, (observed, expects, agrees) in sorted(out["before"].items()):
        mark = "ok " if agrees else "BAD"
        print(f"  {mark} classify({value}) -> {observed!r}, expected {expects!r}")

    print("\n=== the search (imagination: derives, never executes) ===")
    print("  found          :", report.get("found"))
    print("  plan           :", driver.plan_steps(lib.graph, report))
    print("  imagined states:", report.get("steps"))

    repaired = adopt(out)
    print("\n=== the repair, replayed for real and emitted ===")
    print(repaired)

    gate = confirm(repaired, lambda age: "adult" if age >= 18 else "minor")
    print("\n=== the independent gate (reality: executes) ===")
    print(f"  ran the emitted code over {gate['checked']} inputs, not just the 3 examples")
    print("  disagreements with the intended semantics:", gate["disagreements"] or "none")
    print("  generalises:", gate["generalises"])


if __name__ == "__main__":
    main()
