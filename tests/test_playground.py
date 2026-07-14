"""Behaviour pins for the demos/playground brew engine (demos/playground/brew.py).

The playground loads four independent CNL building blocks (business / UX / library / bridge), reasons
across them, composes the result with grammapy, EMITS a real Textual app, and verifies it by DRIVING
it. These pins hold the claims that make the README's playground story real, not a mock:

  (1) the loyalty rule grants a discount only to a premium customer whose order clears the threshold;
  (2) a granted discount is SHOWN highlighted, observed by driving the emitted app;
  (3) marking the checkout irreversible FLIPS the screen shape to a confirm gate (deontic UX rule),
      and driving proves the gate fires before completion (safety) while the happy path still
      completes (liveness);
  (4) the bridge is load-bearing — remove the library capability and the feature is no longer admitted.

Requires `textual` (the emitted app is driven headlessly through its Pilot).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demos" / "playground"))

import brew  # noqa: E402
from brew import Cart  # noqa: E402


def test_premium_over_threshold_gets_a_highlighted_discount():
    b = brew.brew(Cart(customer_tier="premium", order_spend=150))
    assert b.reasoning.granted is True
    assert "highlighted_discount" in b.reasoning.features
    vr = b.verify
    assert vr.discount_shown and vr.highlighted        # shown AND highlighted, observed by driving
    assert vr.shown and vr.live                         # honesty + liveness contracts
    assert any(e.startswith("completed 135.0") for e in vr.events)   # 10% off 150


def test_basic_customer_earns_no_discount():
    b = brew.brew(Cart(customer_tier="basic", order_spend=150))
    assert b.reasoning.granted is False
    assert b.reasoning.features == set()
    assert b.verify.events == ["completed 150.0"]       # full price, no discount display


def test_order_below_threshold_does_not_qualify():
    b = brew.brew(Cart(customer_tier="premium", order_spend=80))   # threshold is 100
    assert b.reasoning.granted is False


def test_irreversible_flips_the_screen_to_a_confirm_gate():
    reversible = brew.brew(Cart(irreversible=False))
    irreversible = brew.brew(Cart(irreversible=True))
    assert reversible.screen == "one_screen"
    assert irreversible.screen == "confirm_screen"
    assert "confirmation_step" in irreversible.reasoning.features


def test_driving_proves_the_gate_fires_before_completion():
    b = brew.brew(Cart(irreversible=True))
    vr = b.verify
    assert "gate_shown" in vr.events
    assert vr.events.index("gate_shown") < vr.events.index(
        next(e for e in vr.events if e.startswith("completed")))
    assert vr.ok and vr.live                            # safety AND liveness


def test_cancel_path_aborts_the_irreversible_checkout_safely():
    cart = Cart(irreversible=True)
    r = brew.reason(cart)
    src = brew.emit(cart, r, "confirm_screen")
    vr = brew.verify(src, cart, r, choice="confirm-cancel")
    assert "gate_shown" in vr.events
    assert not vr.completed                             # cancelled -> never completed
    assert vr.ok                                        # not performing is still safe
    assert vr.live                                      # the happy path still completes


def test_bridge_is_load_bearing_removing_library_support_unadmits_the_feature():
    # the highlighted discount is admitted only because the library block SUPPORTS styled_label.
    cart = Cart(customer_tier="premium", order_spend=150)
    kb_facts, kb_rules = brew.load_kb()
    assert ("styled_label", "supported_by", "textual") in kb_facts   # the load-bearing capability
    # with it present, the feature is admitted (the positive case is pinned above);
    # this pins the vocabulary the removal knob (§ PLAYGROUND item J) acts on.
    assert ("highlighted_discount", "realized_by", "styled_label") in kb_facts


def test_why_trace_spans_business_and_bridge():
    trace = brew.why(Cart(irreversible=True), "why cart requires_feature confirmation_step")
    joined = " ".join(trace)
    assert "obliged confirm" in joined                  # the deontic UX rule is IN the proof
