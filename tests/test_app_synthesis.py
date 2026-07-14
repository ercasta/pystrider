"""Behaviour pins for the app-synthesis probe (experiments/app_synthesis.py).

The probe synthesizes a RUNNABLE Textual app across three bridged vocabularies (business, framework,
UX) and verifies it by DRIVING it with a headless Pilot. These pins hold the two claims that make it a
result: (1) one business/UX fact flips the selected app shape (the mirror of every synthesis flip), and
(2) the flip is EXECUTION-verified, not merely declared — driving the winner OBSERVES a confirmation
gate the loser lacks. Requires `textual`.
"""
import pytest

from experiments.app_synthesis import (
    Spec, required_features, requirement_trace, synthesize,
    verify_by_pilot, confirm_buttons, confirm_button_trace,
    _emit_one_screen, _emit_confirm_screen,
)


def test_lenient_spec_requires_nothing_and_picks_the_compact_app():
    r = synthesize(Spec(name="withdraw_spec"))
    assert r.required == set()
    assert r.winner == "one_screen"                       # compact wins by fit when nothing required
    assert set(r.selection.realizing) == {"one_screen", "confirm_screen"}


def test_irreversible_fact_flips_the_winner_to_the_confirm_app():
    r = synthesize(Spec(name="withdraw_spec", irreversible=True))
    assert r.required == {"confirmation_step"}            # DERIVED across business -> UX -> framework
    assert r.selection.realizing == ["confirm_screen"]    # one_screen no longer realizes the spec
    assert r.winner == "confirm_screen"


def test_required_feature_is_gated_by_framework_support():
    # the UX requirement is admitted only because a framework capability realizes it AND textual
    # supports that capability — the bridge is load-bearing, not decorative.
    assert required_features(Spec(name="s", irreversible=True)) == {"confirmation_step"}
    assert required_features(Spec(name="s", irreversible=False)) == set()


def test_requirement_trace_composes_business_deontic_and_framework_fragments():
    tr = " ".join(requirement_trace(Spec(name="withdraw_spec", irreversible=True), "confirmation_step"))
    assert "withdrawal is_irreversible yes" in tr              # BUSINESS fragment
    assert "obliged confirm" in tr                             # DEONTIC fragment (obligation)
    assert "confirm deontic_needs confirmation_step" in tr     # deontic -> feature
    assert "confirmation_step realized_by modal_confirm" in tr # the BRIDGE
    assert "modal_confirm supported_by textual" in tr          # absorbed FRAMEWORK support


def test_confirm_buttons_default_to_ok_and_cancel():
    assert confirm_buttons(Spec(name="s", irreversible=True)) == {"ok", "cancel"}
    # no confirm screen needed -> no buttons derived (the preference is gated on the feature).
    assert confirm_buttons(Spec(name="s", irreversible=False)) == set()


def test_spec_overrides_the_default_button_set():
    # "default unless the spec says otherwise": naming a button set REPLACES the default.
    assert confirm_buttons(Spec(name="s", irreversible=True, buttons=("ok",))) == {"ok"}
    assert confirm_buttons(Spec(name="s", irreversible=True, buttons=("ok", "cancel", "help"))) == {
        "ok", "cancel", "help"}


def test_default_button_provenance_is_a_default_not_an_override():
    tr = " ".join(confirm_button_trace(Spec(name="s", irreversible=True), "cancel"))
    assert "default_button cancel" in tr                       # it is present BY DEFAULT
    assert "requires_confirm_button" not in tr                 # not because the spec asked for it


def test_default_cancel_button_is_real_driving_it_aborts():
    spec = Spec(name="withdraw_spec", irreversible=True)
    vr = verify_by_pilot(_emit_confirm_screen(spec), spec, confirm_choice="cancel")
    assert vr.gated and not vr.performed and vr.ok             # gated, aborted safely, contract intact
    assert vr.events == ["gate_shown"]


def test_overridden_buttons_appear_in_the_emitted_screen():
    spec = Spec(name="s", irreversible=True, buttons=("ok",))
    src = _emit_confirm_screen(spec)
    assert 'id="confirm-ok"' in src and 'id="confirm-cancel"' not in src   # the override materialized


def test_driving_the_winner_withdraws_and_is_gated():
    spec = Spec(name="withdraw_spec", irreversible=True)
    r = synthesize(spec)
    vr = r.verify
    assert vr.performed and vr.gated and vr.ok
    assert vr.events == ["gate_shown", "withdrawn 42"]         # the gate is OBSERVED before the withdrawal


def test_lenient_winner_withdraws_without_a_gate():
    r = synthesize(Spec(name="withdraw_spec"))
    vr = r.verify
    assert vr.performed and not vr.gated and vr.ok
    assert vr.events == ["withdrawn 42"]


def test_the_flip_is_execution_verified_not_merely_declared():
    # drive BOTH apps under the irreversible spec: only the confirm app satisfies it by EXECUTION.
    strict = Spec(name="withdraw_spec", irreversible=True)
    confirm = verify_by_pilot(_emit_confirm_screen(strict), strict)
    one = verify_by_pilot(_emit_one_screen(strict), strict)
    assert confirm.gated and confirm.ok                        # the winner has the gate
    assert one.performed and not one.gated and not one.ok      # the loser withdraws with NO gate -> rejected


def test_emitted_app_is_syntactically_real_and_self_contained():
    # the emitted source is real, importable Textual code (compiles + defines the app class).
    src = _emit_confirm_screen(Spec(name="s", irreversible=True))
    ns: dict = {}
    exec(compile(src, "<test>", "exec"), ns)
    assert "WithdrawApp" in ns and "ConfirmScreen" in ns


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
