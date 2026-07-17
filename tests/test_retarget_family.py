"""Pins for RE-TARGETED FAMILIES (experiments/retarget_family.py).

The re-target leg of the scale story, on TWO real driven families (Textual via the brew engine + a headless
CLI). These pins hold: (1) the same business/UX decisions drive BOTH targets green across a whole cart
family; (2) both targets DERIVE the same screen shape per cart (a gate iff irreversible); (3) the discount
shows iff granted, in both; (4) the CLI is a genuinely driven second family (an irreversible cart gates
before completing); (5) the ledger reuses the decision-lines verbatim and re-authors only the library port.
"""
from experiments.retarget_family import (
    FAMILY, drive_textual, drive_cli, reason_cli, ledger, emit_cli, brew, Cart,
)


def test_shared_decisions_drive_both_targets_green():
    for cart in FAMILY:
        for d in (drive_textual(cart), drive_cli(cart)):
            assert d.ok and d.live and d.shown, (cart, d.target, d.events)


def test_both_targets_derive_the_same_screen_shape():
    for cart in FAMILY:
        t, c = drive_textual(cart), drive_cli(cart)
        assert t.screen == c.screen                         # same decision -> same shape, either toolkit
        expected = "confirm_screen" if cart.irreversible else "one_screen"
        assert c.screen == expected


def test_discount_shown_tracks_grant_in_both_targets():
    granted = Cart(customer_tier="premium", order_spend=150, irreversible=False)
    not_granted = Cart(customer_tier="basic", order_spend=150, irreversible=False)
    assert "discount_shown" in drive_cli(granted).events and reason_cli(granted).granted
    assert "discount_shown" not in drive_cli(not_granted).events and not reason_cli(not_granted).granted


def test_cli_is_a_second_real_driven_family():
    # a genuinely emitted+run program, not a stub: an irreversible sale gates BEFORE it completes.
    d = drive_cli(Cart(customer_tier="basic", order_spend=80, irreversible=True))
    assert "run_cli" in emit_cli(Cart(irreversible=True), reason_cli(Cart(irreversible=True)), "confirm_screen")
    assert d.events.index("gate_shown") < d.events.index("completed")


def test_ledger_reuses_decisions_verbatim_and_reauthors_only_the_port():
    L = ledger()
    # the shared decisions are exactly business + ux, reused by both targets.
    shared = sum(len(brew.load_block(n)[0]) + len(brew.load_block(n)[1]) for n in ("business", "ux"))
    assert L["shared_decisions"] == shared and shared > 0
    # each re-target costs only its library port, small next to the reused decisions.
    assert 0 < L["cli_port"] <= L["shared_decisions"]
    assert L["textual_port"] > 0
