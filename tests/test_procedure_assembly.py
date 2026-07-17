"""Pins for the procedure-driven assembly probe (experiments/procedure_assembly.py).

The compose->check->recover loop re-expressed as a ugm PROCEDURE: the assembly order, the gap-fill,
and the RECOVERY are all KB rules (planner + `corpus/procedure.cnl`), not Python. These pins hold
four claims: (1) a sound procedure gap-fills its missing `init` step and runs in order; (2) an
OMISSION failure (a step that produces nothing) is recovered by the planner's discrepancy/replan
rules to a FULLY CORRECT result; (3) a CLOBBER is only PARTIALLY recovered — the missing effect is
re-achieved but the corrupted sibling value is NOT un-written (runtime replan can't reverse a
committed side effect), which is the finding that motivates the design-time check; and (4) the
recovery is rule-driven — the alternative producer runs even though it was never a declared step.
"""
from experiments.procedure_assembly import run_procedure, SHIFT_OK


def test_sound_procedure_gap_fills_init_and_runs_in_order():
    r = run_procedure("sound", ("scale", "shift_ok"))
    assert "init" in r.order                              # the planner SYNTHESIZED init (no step named it)
    assert r.order.index("init") < r.order.index("scale")   # ordered before the writer that needs it
    assert not r.recovered                                # nothing failed; no replan
    assert r.ok and r.out == {"scaled": 10, "shifted": 15}


def test_omission_failure_is_fully_recovered_by_replan():
    r = run_procedure("omission", ("scale", "shift_flaky"), alternatives=(SHIFT_OK,))
    assert r.recovered                                    # shift_flaky produced nothing -> replan
    assert "shift_ok" in r.order                          # the alternative producer ran
    assert r.ok and r.out == {"scaled": 10, "shifted": 15}   # omission fully healed


def test_clobber_is_only_partially_recovered_the_finding():
    r = run_procedure("clobber", ("scale", "shift_bad"), alternatives=(SHIFT_OK,))
    assert r.recovered                                    # the missing `shifted` effect is re-achieved
    assert r.shifted_ok                                   #   ... and observed correct
    assert not r.scaled_ok                                # BUT scale's value stays clobbered (15, not 10)
    assert not r.ok                                       # runtime replan cannot un-write a committed effect
    assert r.out == {"scaled": 15, "shifted": 15}


def test_recovery_runs_an_alternative_that_was_never_a_declared_step():
    # the procedure only names scale + shift_bad; shift_ok is an available producer, chosen by the
    # REPLAN rule off the discrepancy — the recovery is KB-driven, not authored into the sequence.
    r = run_procedure("clobber", ("scale", "shift_bad"), alternatives=(SHIFT_OK,))
    assert "shift_ok" in r.order
    assert "shift_ok" not in r.procedure                  # it was not a `then` step
