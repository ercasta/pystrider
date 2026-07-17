"""Pins for versioned software (experiments/versioned_software.py).

The program itself is a build DAG with a movable `current` pointer: repair mints the next version
(never patches in place), every past build is retained and re-emittable, and undo/redo is a pointer
move. These pins hold: (1) a buggy draft is repaired into a NEW build that ships; (2) the DAG is
monotone — the old build survives and still emits its (buggy) source; (3) the transition carries
provenance (revised_from / replaced / reason); (4) time travel — a past build emits different, still-
runnable source; and (5) undo/redo moves `current` with nothing deleted.
"""
from experiments.versioned_software import develop, SoftwareRepo, _diff, REQUIRED
from experiments.compose_recover import compose, verify


def test_buggy_draft_is_repaired_into_a_new_build_that_ships():
    dev = develop(prefer={"shifted": "shift_bad"})
    assert dev.ok
    assert dev.shipped.id == 2                            # build 1 rejected, build 2 shipped
    assert [f.name for f in dev.shipped.comp.fragments] == ["scale", "shift_ok"]
    assert verify(dev.shipped.comp, REQUIRED).result == {"scaled": 10, "shifted": 15}


def test_the_dag_is_monotone_old_build_survives_and_still_emits():
    dev = develop(prefer={"shifted": "shift_bad"})
    repo = dev.repo
    assert [b.id for b in repo.builds()] == [1, 2]        # both versions retained
    # build 1 (the buggy one) is untouched and still emits its original, broken source
    assert "out['scaled'] = x + 10" in repo.emit(1)       # the clobber line, still there
    assert verify(repo.builds()[0].comp, REQUIRED).result == {"scaled": 15}   # runs to the bug


def test_the_repair_transition_carries_provenance():
    dev = develop(prefer={"shifted": "shift_bad"})
    repo = dev.repo
    b2 = repo._by_id[2]
    assert b2.revised_from == 1 and b2.replaced == "shift_bad" and b2.added == "shift_ok"
    assert "revised from build 1" in repo.why(2) and "shift_bad" in repo.why(2)


def test_time_travel_diff_between_builds():
    dev = develop(prefer={"shifted": "shift_bad"})
    d = _diff(dev.repo, 1, 2)
    assert "-    out['scaled'] = x + 10" in d             # the buggy line removed in build 2
    assert "+    out['shifted'] = x + 10" in d            # the fixed line added


def test_undo_and_redo_move_current_without_deleting():
    dev = develop(prefer={"shifted": "shift_bad"})
    repo = dev.repo
    assert repo.current().id == 2
    repo.move_current(1)                                  # UNDO
    assert repo.current().id == 1
    assert verify(repo.current().comp, REQUIRED).result == {"scaled": 15}   # the old buggy program
    repo.move_current(2)                                  # REDO
    assert repo.current().id == 2
    assert verify(repo.current().comp, REQUIRED).result == {"scaled": 10, "shifted": 15}


def test_a_clean_draft_ships_as_build_1_with_no_revision():
    dev = develop(prefer={"shifted": "shift_ok"})
    assert dev.ok and dev.shipped.id == 1                 # no repair needed
    assert dev.repo._by_id[1].revised_from is None
