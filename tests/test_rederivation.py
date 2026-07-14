"""Pins for the re-derivation diff (experiments/rederivation.py) — roadmap Phase 3 (generation wedge).

The 'policy change -> verified code change' artifact: change one succinct spec sentence, re-derive, and
present the spec delta, the resolved-decision delta (each with its derivation), and the emitted-source
delta in lockstep — with both the before and after apps Pilot-verified. These pins hold the claim that a
spec change maps to a code change VIA a derivation (not a regeneration), and that a no-op change
re-derives to nothing (deterministic generation). Requires `textual`.
"""
import pytest

from experiments.rederivation import rederive, ReDerivation
from experiments.app_synthesis import Spec

REVERSIBLE = Spec(name="withdraw_spec", irreversible=False)
IRREVERSIBLE = Spec(name="withdraw_spec", irreversible=True)


def test_the_policy_flip_re_resolves_the_screen_decision():
    rd = rederive(REVERSIBLE, IRREVERSIBLE)
    assert rd.spec_changes == ["irreversible: False -> True"]          # the single spec sentence that moved
    by_point = {c.point: c for c in rd.decision_changes}
    assert by_point["screen"].before == "one_screen" and by_point["screen"].after == "confirm_screen"
    assert by_point["confirm_policy"].after == "obligatory"           # the deontic policy re-resolved too
    assert by_point["confirm_buttons"].after == "ok,cancel"           # a decision point that APPEARED


def test_the_changed_decision_carries_its_derivation():
    # the differentiator over a text diff: the screen change is explained by the real deontic derivation.
    rd = rederive(REVERSIBLE, IRREVERSIBLE)
    why = " ".join(next(c for c in rd.decision_changes if c.point == "screen").why)
    assert "withdrawal is_irreversible yes" in why                    # the business fact that changed
    assert "obliged confirm" in why                                   # the deontic obligation it fired
    assert "confirmation_step realized_by modal_confirm" in why       # the framework bridge


def test_the_source_delta_reflects_the_decision_change():
    rd = rederive(REVERSIBLE, IRREVERSIBLE)
    added = "\n".join(l for l in rd.source_diff if l.startswith("+"))
    assert "class ConfirmScreen" in added                             # the confirm screen is now emitted
    assert "push_screen(ConfirmScreen()" in added                     # and the handler routes through it


def test_it_is_a_VERIFIED_code_change_not_a_re_emission():
    rd = rederive(REVERSIBLE, IRREVERSIBLE)
    assert rd.verified                                                # both before and after drove green
    assert rd.changed


def test_a_defeasible_preference_change_re_derives_the_button_set():
    default = Spec(name="withdraw_spec", irreversible=True)
    override = Spec(name="withdraw_spec", irreversible=True, buttons=("ok",))
    rd = rederive(default, override)
    btn = next(c for c in rd.decision_changes if c.point == "confirm_buttons")
    assert btn.before == "ok,cancel" and btn.after == "ok"
    removed = "\n".join(l for l in rd.source_diff if l.startswith("-"))
    assert "confirm-cancel" in removed                                # the Cancel widget is dropped


def test_a_no_op_change_re_derives_to_nothing():
    # determinism: the same spec yields byte-identical code -> no spec delta, no decisions, no source diff.
    rd = rederive(IRREVERSIBLE, Spec(name="withdraw_spec", irreversible=True))
    assert rd.spec_changes == [] and rd.decision_changes == [] and rd.source_diff == []
    assert not rd.changed


def test_re_derivation_is_deterministic():
    # generation is derivational, not sampled -> two runs give an identical source delta.
    a = rederive(REVERSIBLE, IRREVERSIBLE)
    b = rederive(REVERSIBLE, IRREVERSIBLE)
    assert a.source_diff == b.source_diff
    assert a.before.source == b.before.source and a.after.source == b.after.source


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
