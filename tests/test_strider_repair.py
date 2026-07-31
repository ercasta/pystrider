"""Pins for slice 3 (experiments/strider_repair.py) — a goal driving a code repair on the new engine.

The two pins that carry the most weight are `test_the_repair_reaches_the_REAL_graph` (a plan that
succeeds in imagination while changing nothing looks identical to a real fix from the inside) and
`test_control_the_gate_BITES` (a gate that never fails proves nothing).
"""
import pytest

import experiments.strider_repair as R
from strider.lift import reachable
from strider.mf import driver

INTENDED = lambda age: "adult" if age >= 18 else "minor"      # noqa: E731 — the reference semantics


@pytest.fixture(scope="module")
def done():
    """The whole loop, run once: diagnose, pursue, adopt, emit."""
    out = R.repair()
    out["repaired"] = R.adopt(out)
    return out


# --- diagnosis, by derivation ---------------------------------------------------------------------------

def test_the_diagnosis_names_exactly_the_failing_example(done):
    """Which examples disagree IS the diagnosis — no declared intent, just the bug report's pairs."""
    disagreeing = [x for x, (_obs, _exp, agrees) in done["before"].items() if not agrees]
    assert disagreeing == [18]


def test_the_diagnosis_derives_rather_than_executes(done):
    """⭐ Forced, not chosen. The driver judges candidates by imagining, and `dispatch.service` refuses an
    imagined target — so a candidate repair can never be evaluated by running the patched code. The
    evaluator is a microfunction reading structure, which runs happily on a workbench copy."""
    lib = done["lib"]
    assert "evaluate_case" in lib.operations
    _params, program = __import__("strider").mf.function.load(lib.graph, "evaluate_case")
    opcodes = {ins.op for ins in program if not isinstance(ins, str)}
    assert "DISPATCH" not in opcodes                    # nothing in it can reach the world
    assert "CALL" not in opcodes


# --- the plan --------------------------------------------------------------------------------------------

def test_the_driver_finds_a_plan(done):
    assert done["report"]["found"]


def test_the_plan_is_CHANGE_then_OBSERVE(done):
    """A repair is not done until its effect is observed — two steps, not one, and the driver found that
    shape rather than being told it."""
    steps = driver.plan_steps(done["lib"].graph, done["report"])
    assert steps == ("lower_threshold", "evaluate_case")


def test_both_repair_families_were_available_to_choose_from(done):
    """The search had a real choice. `relax_comparison` also fixes these cases; first-wins picked the
    other. Worth pinning so a future single-family library does not look like the same result."""
    assert {"relax_comparison", "lower_threshold"} <= set(done["lib"].operations)


def test_the_rival_repair_is_ALSO_valid(done):
    """⚠ Both families genuinely fix it, so 'the driver found A' must not be read as 'B was wrong'."""
    lib, _got, task, _branch, cases = R.setup()
    from strider.mf import function
    comparison = next(n for n in reachable(lib, task) if lib.graph.kind(n) == "compare")
    function.invoke(lib.graph, "relax_comparison", {"c": comparison})
    for c in cases:
        function.invoke(lib.graph, "evaluate_case", {"k": c})
    assert all(lib.graph.attr(c, "agrees") for c in cases)


# --- ⭐ the repair must reach REALITY ---------------------------------------------------------------------

def test_the_repair_reaches_the_REAL_graph(done):
    """⚠ THE BUG THIS PIN EXISTS FOR. The first version passed the frame PATH to `execute`, which wants
    the winning LEAF FRAME. It replayed nothing, returned a clean-looking report, and the emitted source
    was byte-identical to the bug. A plan that 'succeeds' while changing nothing is indistinguishable
    from a real fix unless something looks at the artifact."""
    assert "17" in done["repaired"]
    assert done["repaired"] != R.BUGGY


def test_the_emitted_repair_is_still_valid_python(done):
    import ast
    ast.parse(done["repaired"])


# --- ⭐ the independent gate -------------------------------------------------------------------------------

def test_the_gate_runs_the_emitted_code_past_the_examples(done):
    """The plan was chosen by derivation over 3 examples. A repair can satisfy those and be wrong
    everywhere else; sweeping past them is what distinguishes a fix from a fit."""
    gate = R.confirm(done["repaired"], INTENDED)
    assert gate["generalises"], gate["disagreements"]
    assert gate["checked"] > len(R.CASES)


def test_control_the_gate_BITES(done):
    """⚠ Vacuity control. A gate that cannot fail measures nothing — the UNREPAIRED source must be caught,
    and caught at exactly the input the examples flagged."""
    gate = R.confirm(R.BUGGY, INTENDED)
    assert not gate["generalises"]
    assert gate["disagreements"] == [18]


# --- honest refusal ----------------------------------------------------------------------------------------

UNMODELLED = """def classify(age):
    if age < 18:
        return 'adult'
    else:
        return 'minor'"""


def test_an_unmodelled_operator_is_REFUSED_not_guessed():
    """⚠⚠ THE SILENT WRONG ANSWER THIS CAUGHT. The evaluator's comment claimed it modelled `gt` and `ge`
    only; the code fell through to the `gt` path for everything else, so `age < 18` was derived as though
    it read `age > 18` and `classify(10)` came back `'minor'` when the code plainly returns `'adult'`.

    Found by testing the docstring's CLAIM against the code's BEHAVIOUR — a membrane described in prose
    is not a membrane."""
    lib, _got, _task, _branch, cases = R.setup(UNMODELLED, ((18, "minor"), (10, "adult")))
    R.diagnose(lib, cases)
    assert all(lib.graph.attr(c, "agrees") is None for c in cases)       # no verdict claimed
    assert all(lib.graph.attr(c, "observed") is None for c in cases)     # and nothing derived
    assert {lib.graph.attr(c, "unmodelled_operator") for c in cases} == {"lt"}


def test_a_refused_case_leaves_the_goal_UNMET_so_no_repair_is_credited():
    """The refusal has to cost something, or it is decoration: an unevaluable case can never satisfy its
    constraint, so nothing can be reported as having fixed it."""
    from strider.mf import goal as G
    lib, _got, task, _branch, cases = R.setup(UNMODELLED, ((18, "minor"), (10, "adult")))
    R.diagnose(lib, cases)
    goal = R.build_goal(lib, task, cases)
    assert len(G.unmet(lib.graph, goal)) == len(cases)
