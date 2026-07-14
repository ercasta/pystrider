# =============================================================================
# PLAYGROUND — bring your rules, bridge them, brew a working UI
# =============================================================================
# Run:   python demos/playground/playground.py
#
# This is a sandbox, not a lecture. Four independent knowledge blocks live next to
# this file, each in its own vocabulary:
#
#     business.cnl   prices, discounts, loyal customers
#     ux.cnl         confirming transactions, what "show a discount" means
#     textual.cnl    what the Textual widget toolkit can build
#     bridge.cnl     the only crosswalk between the three above
#
# The brew engine (`brew.py`) loads them, reasons across them, composes the result
# with grammapy's proven combinators, EMITS a real Textual app, and trusts it
# because it DRIVES it headlessly and reads what happened. Nothing is hardcoded:
# turn a knob below (or edit a line in any `.cnl` block) and the emitted, verified
# UI changes — with the reasoning behind every change auditable.
#
# The § PLAYGROUND menu at the bottom is a big pile of knobs to turn.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import brew
from brew import Cart


def launch(cart: Cart) -> None:
    """Emit the app for `cart` and RUN it interactively (not headless) so you can click through it
    and take a screenshot. `python demos/playground/playground.py --run`."""
    r = brew.reason(cart)
    _, screen = brew.compose(cart, r.features)
    source = brew.emit(cart, r, screen or "one_screen")
    ns: dict[str, object] = {}
    exec(compile(source, "<emitted-checkout>", "exec"), ns)
    ns["CheckoutApp"]().run()


# =============================================================================
# § CONFIG — the knobs. Edit these, re-run, watch the UI re-derive.
# =============================================================================
CART = Cart(
    customer_tier="premium",   # "premium" (loyal) earns the discount; "basic" does not
    order_spend=150,           # the order amount; must clear business.cnl's threshold (100) to qualify
    irreversible=False,        # True -> the UX block obliges a confirmation step (the screen flips)
    highlight_style="reverse", # how the discount is highlighted (a Rich style: "reverse" or "bold")
)


# =============================================================================
def _rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def show(cart: Cart) -> None:
    """Brew one cart and narrate every step: the loaded blocks, the reasoning, grammapy's decisions,
    the emitted UI, and the drive that verifies it."""
    _rule(f"BREW: {cart.customer_tier} customer, order {cart.order_spend}, "
          f"{'irreversible (final)' if cart.irreversible else 'reversible'}")

    # --- 1. the building blocks, loaded independently -------------------------------------------
    print("\n[1] four independent knowledge blocks (each its own vocabulary):")
    for name in brew.BLOCKS:
        facts, rules = brew.load_block(name)
        print(f"      {name + '.cnl':<14} {len(facts)} fact(s), {len(rules)} rule(s)")

    # --- 2. reason across them ------------------------------------------------------------------
    r = brew.reason(cart)
    print("\n[2] reason across the blocks (business -> UX -> bridge):")
    print(f"      grants_discount? {r.granted}   (a premium customer over threshold earns "
          f"{r.rate:.0f}% off)")
    print(f"      admitted features: {sorted(r.features) or '[]'}   "
          f"(a UX feature enters only if the library supports its realizer)")
    if r.granted:
        print("      why the discount is a benefit the UI must show:")
        for line in brew.why(cart, f"why {cart.name} has_benefit discount"):
            print(f"          {line}")

    # --- 3. compose with grammapy ---------------------------------------------------------------
    decisions, screen = brew.compose(cart, r.features)
    print("\n[3] compose every decision through a grammapy combinator:")
    for d in decisions:
        print(f"      {d.point:<8} [{d.combinator:<10}] -> {d.value}   (admitted={d.admitted})")

    # --- 4. emit + 5. drive ---------------------------------------------------------------------
    b = brew.brew(cart)
    print(f"\n[4] emit a Textual app -> screen shape: {b.screen}"
          f"   ({len(b.source.splitlines())} lines of real Textual source)")
    vr = b.verify
    print("\n[5] DRIVE it headlessly (trust by execution, not by claim):")
    print(f"      events: {vr.events}")
    print(f"      safety(ok)={vr.ok}  liveness(live)={vr.live}  discount-shown(shown)={vr.shown}")
    verdict = "WORKS" if (vr.ok and vr.live and vr.shown) else "FAILED A CONTRACT"
    print(f"      => {verdict}")


def main() -> None:
    print("PLAYGROUND - bring your rules, bridge them, brew a working UI\n"
          "(edit the CONFIG block above, or any demos/playground/*.cnl block, then re-run)")

    # the configured cart
    show(CART)

    # a guided tour of two flips, so a first run shows the machine reacting to knowledge
    _rule("TOUR - turn one knob at a time and watch the UI re-derive")

    print("\n(a) the LOYALTY flip: premium vs basic customer, same order")
    for tier in ("premium", "basic"):
        b = brew.brew(Cart(customer_tier=tier, order_spend=150))
        note = "discount shown, highlighted" if b.reasoning.granted else "no discount"
        feats = str(sorted(b.reasoning.features) or [])
        print(f"      {tier:<8} -> features {feats:<28} events {b.verify.events}   ({note})")

    print("\n(b) the CONFIRMATION flip: mark the checkout irreversible")
    for irr in (False, True):
        b = brew.brew(Cart(irreversible=irr))
        print(f"      irreversible={str(irr):<5} -> screen {b.screen:<14} "
              f"events {b.verify.events}")
    print("\n  Same knowledge blocks; one business/UX fact each time. The confirmation gate is FORCED\n"
          "  by the deontic UX rule (not chosen), and DRIVING both apps proves the flip is real:\n"
          "  the irreversible app shows the gate before completing; the reversible one never does.")


if __name__ == "__main__":
    if "--run" in sys.argv:
        launch(CART)          # open the emitted app interactively (for a screenshot)
    else:
        main()


# =============================================================================
# § PLAYGROUND — turn the knobs (edit, re-run, watch the UI re-derive)
# =============================================================================
#
# THE CART (edit § CONFIG above) --------------------------------------------
# A) Lose the loyalty. Set `customer_tier="basic"`. Re-run: `grants_discount?`
#    goes False, the `highlighted_discount` feature drops, and the emitted app no
#    longer shows (or highlights) any discount — it just completes at full price.
# B) Small order. Set `order_spend=80` (below business.cnl's threshold of 100).
#    Even a premium customer earns nothing — the qualifying comparison fails.
# C) Make it final. Set `irreversible=True`. The UX block's deontic rule obliges a
#    confirmation step, the screen shape FLIPS to `confirm_screen`, and driving the
#    app now shows `gate_shown` before `completed`.
# D) Restyle the discount. Set `highlight_style="bold"`. The emitted Static's Rich
#    style changes; the highlight is still verified as behaviour (`highlighted`).
#
# THE BUSINESS BLOCK (edit business.cnl) ------------------------------------
# E) Move the threshold. Change `discount_policy threshold 100` to `... 200`.
#    A 150 order stops qualifying — a business change, no code change.
# F) Sweeten the deal. Change `discount_policy rate 10` to `... 25`. The emitted
#    app prices every qualifying cart at 25% off (the number flows rule -> UI).
# G) A new loyalty tier. Add facts `gold is_a premium` won't work (premium is a
#    value, not a node) — instead add a rule
#    `?cart grants_discount yes when ?cart customer_tier gold and ?cart order_qualifies yes`
#    and set the cart's tier to "gold". Two independent ways to earn the discount.
#
# THE UX BLOCK (edit ux.cnl) ------------------------------------------------
# H) Change what "show a discount" MEANS. Delete the `highlighted_discount` rule
#    and add `?cart requires_feature plain_discount when ?cart has_benefit discount`.
#    You'll need a matching bridge line + library capability for it to be admitted
#    (see the bridge block) — the honest "the toolkit must support it" gate.
# I) Always confirm. Add `?cart obliged confirm when ?cart is_a cart` (an
#    unconditional obligation). Every checkout now gates, reversible or not.
#
# THE LIBRARY BLOCK (edit textual.cnl) --------------------------------------
# J) Take away a capability. Delete `styled_label supported_by textual`. Re-run:
#    the discount is still GRANTED by the business block, but `highlighted_discount`
#    is no longer ADMITTED (the bridge can't reach a supported realizer) — the
#    "your toolkit can't do that yet" gap, surfaced instead of silently dropped.
#
# THE BRIDGE BLOCK (edit bridge.cnl) ----------------------------------------
# K) Cut a wire. Delete `confirmation_step realized_by modal_confirm`. Now even an
#    irreversible cart cannot get its confirmation step admitted — the feature is
#    required by UX but unreachable, because the ONLY crosswalk was removed.
#
# ASK YOUR OWN --------------------------------------------------------------
# L) Trace anything. In a Python shell:
#       import brew; from brew import Cart
#       print(brew.why(Cart(irreversible=True), "why cart requires_feature confirmation_step"))
#    Every derived fact carries its `why` — the reasoning is always auditable.
