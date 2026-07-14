"""Pins for the refusal UX (experiments/refusal.py) — roadmap Phase 3, held line #3 ("refusal is a feature").

Generation breadth = KB coverage: at the edge of coverage the honest behaviour is neither a crash nor a
guess but a NAMED GAP — what capability is uncovered, and the shape of the KB entry that would fill it.
These pins hold that an unprovided requirement refuses with an authoring on-ramp, an ambiguous one asks
for a declared preference, a covered one proceeds, and refusal is a first-class return value of the
generation loop (not an exception). The gap boundary rests on the CNL-derived §12 `resolve`.
"""
import pytest

from experiments.refusal import Gap, gap_of, Refusal, synthesize_or_refuse
from experiments.app_synthesis import Spec, SCREEN_POINT, Synthesis
from grammapy import DecisionPoint, Production


def test_a_covered_requirement_has_no_gap():
    # confirm_screen provides 'confirmation' -> the point resolves cleanly, no refusal.
    assert gap_of(SCREEN_POINT, ["confirmation"]) is None
    assert gap_of(SCREEN_POINT, []) is None                    # silent -> defaulted, also no gap


def test_an_unprovided_requirement_names_the_gap_and_the_fill():
    gap = gap_of(SCREEN_POINT, ["biometric"])
    assert isinstance(gap, Gap) and gap.kind == "unprovided"
    assert gap.requirement == frozenset({"biometric"})
    # the fill is the shape of the KB entry that would close it — a production providing the capability.
    assert "provides" in gap.fill and "biometric" in gap.fill
    assert any("no production provides" in line for line in gap.render())


def test_an_ambiguous_requirement_asks_for_a_declared_preference():
    two = DecisionPoint("screen", (
        Production("confirm_modal", frozenset({"confirmation"})),
        Production("confirm_inline", frozenset({"confirmation"}))), default="confirm_modal")
    gap = gap_of(two, ["confirmation"])
    assert isinstance(gap, Gap) and gap.kind == "ambiguous"
    assert set(gap.survivors) == {"confirm_modal", "confirm_inline"}
    assert "preference" in gap.fill                            # the fill is a declared preference


def test_synthesize_or_refuse_emits_when_covered():
    out = synthesize_or_refuse(Spec(name="w", irreversible=True))
    assert isinstance(out, Synthesis)
    assert out.verify.ok and out.verify.live                  # a verified app, not a refusal


def test_synthesize_or_refuse_refuses_when_uncovered():
    # a requirement the KB cannot cover -> a Refusal value (NOT an exception, NOT a guessed emission).
    out = synthesize_or_refuse(Spec(name="w", irreversible=True), requires=["biometric"])
    assert isinstance(out, Refusal)
    assert out.gaps and out.gaps[0].kind == "unprovided"
    assert "biometric" in out.gaps[0].requirement


def test_refusal_is_a_value_not_a_crash():
    # the whole point of held line #3: an uncovered spec never raises — it returns a named gap.
    try:
        out = synthesize_or_refuse(Spec(name="w"), requires=["quantum_signature"])
    except Exception as e:                                     # pragma: no cover
        pytest.fail(f"refusal must not raise, got {e!r}")
    assert isinstance(out, Refusal) and out.gaps


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
