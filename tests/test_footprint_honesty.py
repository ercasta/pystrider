"""Behaviour pins for the footprint-honesty probe (experiments/footprint_honesty.py).

The probe closes grammapy's roadmap step 7: grammapy's non-interference guarantee is decided from
*declared* footprints, so it is only as true as the declarations. pystrider certifies a declaration the
way it certifies everything — by EXECUTION. These pins hold the two claims that make it a result:
(1) honesty is an execution property (a dishonest atom is caught only by running it), and (2) execution
can REJECT a composition grammapy admitted from disjoint *declared* footprints.
"""
import pytest

from experiments.footprint_honesty import (
    Atom, RecordingStore, observed_writes, footprint_honest,
    verify_composition, honest_button, dishonest_cancel,
)
from grammapy import Accumulate, Channel, CompositionError, Footprint


def test_recording_store_captures_every_write():
    store = RecordingStore()
    store["a"] = 1
    store["b"] = 2
    store["a"] = 3                      # a re-write is not a new channel
    assert store.written == {"a", "b"}


def test_observed_writes_runs_the_atom_body():
    atom = Atom("x", Footprint.of(writes=[Channel("p"), Channel("q")]),
                body='store["p"] = 1\nstore["q"] = 2\n')
    assert observed_writes(atom) == {"p", "q"}


def test_an_honest_atom_writes_only_what_it_declared():
    r = footprint_honest(honest_button("ok", affirmative=True))
    assert r.declared == {"confirm.button.ok", "confirm.submit"}
    assert r.observed == {"confirm.button.ok", "confirm.submit"}
    assert r.honest and r.undeclared == set()


def test_a_dishonest_atom_is_caught_only_by_execution():
    bad = dishonest_cancel()
    # the DECLARATION omits confirm.submit — nothing static can see the write.
    assert {c.name for c in bad.footprint.writes} == {"confirm.button.cancel"}
    r = footprint_honest(bad)
    assert not r.honest
    assert r.undeclared == {"confirm.submit"}          # the write it did not admit to
    assert "confirm.submit" in r.observed


def test_grammapy_admits_the_dishonest_pair_by_declaration():
    # the whole point: the DECLARED footprints of ok + dishonest-cancel are disjoint, so grammapy's
    # design-time check sees no conflict — the guarantee is issued on a false premise.
    ok, cancel_bad = honest_button("ok", affirmative=True), dishonest_cancel()
    Accumulate.check([ok.item, cancel_bad.item])       # no raise: admitted by declaration


def test_execution_rejects_a_composition_grammapy_admitted():
    ok, cancel_bad = honest_button("ok", affirmative=True), dishonest_cancel()
    v = verify_composition([ok, cancel_bad])
    assert v.admitted_by_declaration                   # grammapy said yes (disjoint DECLARED writes)
    assert not v.honest                                # but an atom lied
    assert [r.label for r in v.dishonest] == ["button cancel"]
    assert not v.safe_by_execution                     # observed writes actually collide
    assert not v.trustworthy
    assert "confirm.submit" in (v.execution_error or "")   # the real collision is named


def test_an_honest_composition_is_trustworthy_on_all_three_axes():
    ok, cancel = honest_button("ok", affirmative=True), honest_button("cancel", affirmative=False)
    v = verify_composition([ok, cancel])
    assert v.admitted_by_declaration and v.honest and v.safe_by_execution
    assert v.trustworthy


def test_a_declaration_time_rejection_is_also_reported():
    # two affirmative atoms both DECLARE (and write) confirm.submit -> grammapy rejects at design time,
    # and execution independently confirms the collision. Both halves agree on a genuinely-broken set.
    ok, yes = honest_button("ok", affirmative=True), honest_button("yes", affirmative=True)
    v = verify_composition([ok, yes])
    assert not v.admitted_by_declaration               # grammapy already refuses it
    assert v.honest                                    # both atoms are honest — they DID declare submit
    assert not v.safe_by_execution                     # and execution sees the same collision
    assert not v.trustworthy


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
