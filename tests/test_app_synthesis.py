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
    compose_confirm_screen, _affirmative_of,
    choose_screen, _confirmation_state, SCREEN_PRODUCTIONS, CONFIRMATION_ENUM,
    check_reachability, app_scope_tree, CONFIRM_SIGNAL,
    resolve_confirm, _confirm_verdicts, CONFIRM_SAFETY, CONFIRM_LENIENT,
    _emit_one_screen, _emit_confirm_screen,
)
from grammapy import ABSENT, Choice, CompositionError, guard_coverage, unhandled_emissions


def test_lenient_spec_requires_nothing_and_picks_the_compact_app():
    r = synthesize(Spec(name="withdraw_spec"))
    assert r.required == set()
    assert _confirmation_state(r.spec) is ABSENT          # spec silent on confirmation -> default branch
    assert r.winner == "one_screen"                       # the grammapy Choice fires the default production


def test_irreversible_fact_flips_the_winner_to_the_confirm_app():
    r = synthesize(Spec(name="withdraw_spec", irreversible=True))
    assert r.required == {"confirmation_step"}            # DERIVED across business -> deontic -> framework
    assert _confirmation_state(r.spec) == "required"      # the obligation set the decision key's state
    assert r.winner == "confirm_screen"                   # so the Choice fires the confirm production


def test_screen_choice_guards_partition_the_domain():
    # the app's screen decision is a SOUND exclusive-Choice: its guards partition {required, absent}.
    assert guard_coverage(CONFIRMATION_ENUM, SCREEN_PRODUCTIONS) == []
    Choice.check(CONFIRMATION_ENUM, SCREEN_PRODUCTIONS)   # no raise
    assert choose_screen(Spec(name="s")) == "one_screen"
    assert choose_screen(Spec(name="s", irreversible=True)) == "confirm_screen"


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


# --- Phase 1: composition through grammapy's Accumulate (footprint disjointness) ---------------

def test_default_button_set_composes_through_grammapy():
    items = compose_confirm_screen(Spec(name="s", irreversible=True))   # no raise == admitted
    writes = {str(c) for it in items for c in it.footprint.writes}
    assert writes == {"confirm.button.ok", "confirm.button.cancel", "confirm.submit"}


def test_two_proceed_buttons_are_rejected_at_design_time():
    # ok and yes are both affirmative -> both bind `confirm.submit` -> grammapy refuses the composition.
    with pytest.raises(CompositionError) as ctx:
        compose_confirm_screen(Spec(name="s", irreversible=True, buttons=("ok", "yes")))
    msg = str(ctx.value)
    assert "confirm.submit" in msg                 # the shared channel is named
    assert "button ok" in msg and "button yes" in msg   # both offending features are named


def test_synthesize_records_a_composition_rejection_and_emits_nothing():
    bad = synthesize(Spec(name="withdraw_spec", irreversible=True, buttons=("ok", "yes")))
    assert bad.composed is False
    assert bad.source == "" and bad.verify is None        # no source emitted, no app driven
    assert "confirm.submit" in bad.composition_error


def test_synthesize_marks_a_wellformed_app_as_composed():
    good = synthesize(Spec(name="withdraw_spec", irreversible=True))
    assert good.composed is True and good.composition_error is None
    assert good.verify.performed and good.verify.ok


def test_affirmative_button_drives_the_emitted_dismiss():
    # an overridden affirmative (`yes`) must be the id the emitted screen proceeds on.
    spec = Spec(name="s", irreversible=True, buttons=("yes", "cancel"))
    assert _affirmative_of(spec) == "yes"
    assert 'event.button.id == "confirm-yes"' in _emit_confirm_screen(spec)


# --- Phase 2b: reachability of the withdrawal effect through grammapy's Scope -----------------

def test_irreversible_withdrawal_emits_the_confirm_signal():
    tree = app_scope_tree(Spec(name="s", irreversible=True), "confirm_screen")
    # the perform leaf (under the gate) emits the control signal; a reversible one emits nothing.
    perform = tree.children[0].children[0]
    assert perform.emits == frozenset({CONFIRM_SIGNAL})
    assert app_scope_tree(Spec(name="s"), "one_screen").children[0].emits == frozenset()


def test_confirm_structure_handles_the_effect_and_is_admitted():
    check_reachability(Spec(name="s", irreversible=True), "confirm_screen")   # no raise
    assert unhandled_emissions(app_scope_tree(Spec(name="s", irreversible=True), "confirm_screen")) == []


def test_one_screen_structure_leaks_the_irreversible_effect():
    # force the compact structure on an irreversible spec: Scope catches the escaping effect.
    with pytest.raises(CompositionError) as ctx:
        check_reachability(Spec(name="s", irreversible=True), "one_screen")
    msg = str(ctx.value)
    assert "escape their scope" in msg
    assert CONFIRM_SIGNAL in msg and "perform_withdrawal" in msg


def test_reversible_one_screen_has_no_effect_to_handle():
    check_reachability(Spec(name="s"), "one_screen")             # no emit -> trivially reachable


# --- Phase 2c: deontic conflict resolution through grammapy's Fold ----------------------------

def test_trusted_session_cannot_waive_a_safety_confirmation():
    # irreversible + trusted -> conflicting votes; the safety policy makes the obligation win.
    conflict = Spec(name="s", irreversible=True, trusted=True)
    votes = {it.value for it in _confirm_verdicts(conflict)}
    assert votes == {"optional", "obligatory", "waived"}        # all three voted
    assert resolve_confirm(conflict, CONFIRM_SAFETY) == "obligatory"
    assert _confirmation_state(conflict) == "required"          # so a confirm screen is STILL forced
    assert choose_screen(conflict) == "confirm_screen"


def test_declared_policy_flips_the_outcome():
    conflict = Spec(name="s", irreversible=True, trusted=True)
    assert resolve_confirm(conflict, CONFIRM_SAFETY) == "obligatory"   # obligation overrides
    assert resolve_confirm(conflict, CONFIRM_LENIENT) == "waived"      # same votes, waiver overrides


def test_trusted_alone_needs_no_confirmation():
    # a reversible action, trusted or not, has no obligation to override -> no confirmation.
    assert resolve_confirm(Spec(name="s", trusted=True)) == "optional"
    assert _confirmation_state(Spec(name="s", trusted=True)) is ABSENT


def test_fold_leaves_non_trusted_behaviour_unchanged():
    # the Fold is transparent when there is no waiver vote: prior Choice behaviour is preserved.
    assert _confirmation_state(Spec(name="s")) is ABSENT
    assert _confirmation_state(Spec(name="s", irreversible=True)) == "required"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
