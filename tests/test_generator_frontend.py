"""Pins for the external-generator-front-end probe (experiments/generator_frontend.py) — Phase 5 steps 5–6.

The capstone claim: an UNTRUSTED generator drafting a design "by pattern" yields TRUSTWORTHY software,
because each mistake it can make is caught by a specific downstream gate it does not control (the derived
obligation, grammapy's Scope + Accumulate, the Pilot), and a rejection self-corrects via reasoning-repair.
Requires `textual`.
"""
import pytest

from experiments.generator_frontend import (
    parse_intent, Draft, gate, repair, run,
    sound_generator, lazy_generator, sloppy_generator, sterile_generator,
)
from experiments.app_synthesis import Spec, check_reachability, required_capabilities, _button_atom
from grammapy import Accumulate, CompositionError

IRREVERSIBLE = "a cash withdrawal app; the withdrawal is irreversible"
LENIENT = "a cash withdrawal app"


def test_intent_parse_detects_the_irreversibility_fact():
    assert parse_intent(IRREVERSIBLE).irreversible is True
    assert parse_intent(LENIENT).irreversible is False


def test_sound_generator_passes_every_gate_and_drives_green():
    o = run(IRREVERSIBLE, sound_generator)
    assert o.first.accepted and o.trustworthy
    assert o.first.verify.events == ["gate_shown", "withdrawn 42"]   # gated before the withdrawal


def test_lazy_generator_is_caught_by_the_obligation_gate():
    o = run(IRREVERSIBLE, lazy_generator)
    assert not o.first.accepted
    assert o.first.gate == "reasoning/obligation"     # GATE 1 catches the ignored obligation
    assert "confirmation" in o.first.reason


def test_lazy_structure_is_also_independently_caught_by_scope():
    # belt-and-suspenders: even if the obligation gate were absent, grammapy Scope rejects the same
    # lazy one-screen structure on an irreversible spec (the effect escapes) — two independent gates.
    with pytest.raises(CompositionError):
        check_reachability(Spec(name="s", irreversible=True), "one_screen")


def test_sloppy_generator_is_caught_by_accumulate():
    o = run(IRREVERSIBLE, sloppy_generator)
    assert not o.first.accepted
    assert o.first.gate == "grammapy/Accumulate"      # passes obligation + Scope, fails the frame rule


def test_sterile_generator_is_caught_by_the_liveness_gate():
    # Phase 0: a confirm screen with no proceed button passes the obligation, Scope, and Accumulate
    # (its writes are disjoint), and is caught ONLY by the Pilot's LIVENESS contract — the gate the
    # safety-only oracle could never fire, making GATE 4 a real rejector for the first time.
    draft = sterile_generator(parse_intent(IRREVERSIBLE))
    # it genuinely survives the three design-time gates:
    assert draft.screen == "confirm_screen"                       # provides confirmation (GATE 1 ok)
    check_reachability(draft.spec, draft.screen)                  # Scope admits (GATE 2 ok, no raise)
    Accumulate.check([_button_atom(b) for b in draft.buttons])    # disjoint writes (GATE 3 ok, no raise)
    o = run(IRREVERSIBLE, sterile_generator)
    assert not o.first.accepted
    assert o.first.gate == "pystrider/Pilot-liveness"             # only the liveness contract catches it
    assert o.first.verify is not None and not o.first.verify.live
    assert o.repaired.screen == "confirm_screen" and o.final.accepted and o.trustworthy


def test_the_gated_button_set_is_the_one_that_ships():
    # Phase 0 draft-vs-artifact: a confirm draft with an EMPTY button set emits the preference default
    # (ok+cancel). The gate must certify THAT emitted set — driving green — not the empty draft set.
    o = run(IRREVERSIBLE, lambda spec: Draft(spec, "confirm_screen", ()))
    assert o.first.accepted and o.trustworthy
    assert o.first.verify.events == ["gate_shown", "withdrawn 42"]   # the shipped default set drives live


def test_a_rejected_draft_is_repaired_by_reasoning_and_then_accepted():
    for generator in (lazy_generator, sloppy_generator, sterile_generator):
        o = run(IRREVERSIBLE, generator)
        assert not o.first.accepted                   # the draft was rejected
        assert o.repaired.screen == "confirm_screen"  # reasoning re-derived the sound design
        assert o.final.accepted and o.trustworthy     # which re-gates clean and drives
        assert o.final.verify.events == ["gate_shown", "withdrawn 42"]


def test_lenient_intent_accepts_the_compact_app():
    o = run(LENIENT, sound_generator)
    assert o.first.accepted and o.first.gate == "accepted"
    assert o.first.verify.events == ["withdrawn 42"]  # no gate needed, none shown


def test_repair_of_a_sound_draft_is_idempotent_shape():
    # repairing an already-sound irreversible draft still yields a confirm design (no oscillation).
    sound = sound_generator(parse_intent(IRREVERSIBLE))
    assert repair(sound).screen == "confirm_screen"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
