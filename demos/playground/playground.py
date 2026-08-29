"""Run the brew and print the evidence.

    python -m demos.playground.playground            # the default cart
    python -m demos.playground.playground --flip     # ...and the same cart made irreversible

⭐ The point of printing it this way is that every line below is DERIVED. Change a
knob here, or a line in any `.cnl` block beside this file, and the reasoning, the
design decisions, the emitted source and the observed event trace all move together
— with `why` available for any derived fact.
"""
from __future__ import annotations

import sys

from .brew import Cart, brew


def report(cart: Cart) -> bool:
    b = brew(cart)
    r = b.reasoning
    print(f"\n{'=' * 78}\nCART  tier={cart.customer_tier}  spend={cart.order_spend}  "
          f"irreversible={cart.irreversible}\n{'=' * 78}")

    print(f"\nREASON   ({len(r.blocks)} blocks, {len(r.loop.rules)} rules, "
          f"settled in {r.ticks} ticks)")
    print(f"  discount granted : {r.granted}   (rate {r.rate}%)")
    print(f"  features admitted: {', '.join(r.features) or '(none)'}")
    for feature in r.features:
        for line in r.why(feature, "admitted_for", cart.name):
            print(f"    why {line}")

    print("\nCOMPOSE")
    for d in b.decisions:
        mark = "ok " if d["admitted"] else "REJECTED"
        print(f"  {d['point']:8} {d['combinator']:11} {mark:9} {d['value']}"
              + (f"   [{d['detail']}]" if d["detail"] else ""))
    print(f"  screen shape     : {b.screen}")

    if not b.source:
        print("\nEMIT     nothing — a decision point refused, so no app is claimed.")
        return False

    print(f"\nEMIT     {len(b.source.splitlines())} lines of Textual"
          f"{', with the confirm gate' if b.screen == 'confirm_screen' else ''}"
          f"{', with the discount highlight' if 'def _show_discount' in b.source else ''}")

    v = b.verified
    print(f"\nDRIVE -> events: {v.events}")
    print(f"         safety(ok)={v.ok}  liveness(live)={v.live}  "
          f"discount-shown(shown)={v.shown}   => {'WORKS' if v.works else 'FAILS'}")
    return v.works


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    carts = [Cart()]
    if "--flip" in argv:
        carts.append(Cart(irreversible=True))
    results = [report(cart) for cart in carts]
    print()
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
