"""Pins for versioned recovery (experiments/versioned_recovery.py).

The capstone: representing state as append-only, fragment-attributed VERSIONS (instead of a mutable
dict) makes the SAME planner rules recover a CLOBBER completely — the limit procedure_assembly hit.
These pins hold five claims: (1) the clobber now recovers to a FULLY correct current version; (2) the
un-versioned in-place model stays broken (pinning the delta the representation buys); (3) monotonicity
is respected — the clobbering write is RETAINED in the history, never deleted, just superseded; (4) the
recovery DECISION is the rules' (`excluded` marker), read off the graph, not new Python logic; and
(5) the projection obeys `excluded` (a unit check of the current-version resolution).
"""
from experiments.versioned_recovery import run_versioned, project_current, Write, SHIFT_OK


def test_clobber_recovers_completely_when_state_is_versioned():
    r = run_versioned("clobber", ("scale", "shift_bad"), alternatives=(SHIFT_OK,))
    assert r.current == {"scaled": 10, "shifted": 15}    # scaled REVERSED back to 10
    assert r.ok


def test_the_in_place_model_stays_broken_the_delta_versioning_buys():
    r = run_versioned("clobber", ("scale", "shift_bad"), alternatives=(SHIFT_OK,))
    # the mutable-dict model (procedure_assembly's) ends corrupted — this is exactly what versioning fixes
    assert r.in_place == {"scaled": 15, "shifted": 15}
    assert r.in_place != r.current


def test_monotone_the_clobbering_write_is_retained_not_deleted():
    r = run_versioned("clobber", ("scale", "shift_bad"), alternatives=(SHIFT_OK,))
    # the bad write still exists in the append-only history (nothing is ever deleted) ...
    assert Write(1, "scaled", 15, "shift_bad") in r.log
    # ... and scale's correct earlier write also survives (it was never overwritten)
    assert Write(0, "scaled", 10, "scale") in r.log


def test_recovery_decision_is_the_rules_excluded_marker():
    r = run_versioned("clobber", ("scale", "shift_bad"), alternatives=(SHIFT_OK,))
    assert r.excluded == {"shift_bad"}                   # set by corpus/procedure.cnl, read off the graph


def test_projection_obeys_excluded():
    # a pure unit check: last live write per channel wins; an excluded fragment's write is skipped.
    log = [Write(0, "scaled", 10, "scale"), Write(1, "scaled", 15, "shift_bad"),
           Write(2, "shifted", 15, "shift_ok")]
    assert project_current(log, excluded=set()) == {"scaled": 15, "shifted": 15}      # no exclusion: clobber wins
    assert project_current(log, excluded={"shift_bad"}) == {"scaled": 10, "shifted": 15}  # excluded: reversed


def test_omission_stays_correct_under_versioning():
    r = run_versioned("omission", ("scale", "shift_flaky"), alternatives=(SHIFT_OK,))
    assert r.ok and r.current == {"scaled": 10, "shifted": 15}
