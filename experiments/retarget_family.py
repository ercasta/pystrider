"""RE-TARGETED FAMILIES — the same business/UX decisions drive a SECOND library, end-to-end and DRIVEN.

The composability-coverage finding argued that even a re-target (Textual -> another toolkit) REUSES the
business/UX decisions — "the expensive part is the library, not re-deciding the app." That was read off the
vocabulary; this probe makes it a running, driven fact on TWO real families:

    shared decisions        business.cnl + ux.cnl          authored ONCE, reused by BOTH targets verbatim
    target A = Textual       textual.cnl + bridge.cnl       the existing driven app (via the brew engine)
    target B = CLI           an in-probe library + bridge   a second toolkit port: emit + DRIVE headlessly

Both targets consume the identical business/UX rules (the discount policy, the confirm obligation, what
"show a discount" means). Only the LIBRARY block and its bridge crosswalk — plus the emit/drive for that
toolkit — are re-authored. The probe RUNS a whole family of carts through BOTH targets and checks the SAME
behavioral contracts on each (a confirm gate precedes completion iff the sale is irreversible; the discount
is shown iff granted). Then it measures the ledger: decision-lines reused vs port-lines re-authored.

The claim it grounds: the irreducible, expensive part (the decisions) is authored once and reused across
targets at ZERO re-authoring; a re-target costs only its library port, and both families are trusted the
same way — by DRIVING them, not by claim. This is the "re-targeted families" leg of the scale story (the
other leg, feature-interaction, is `interaction_scaling.py`).

Run it: `python -m experiments.retarget_family`
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demos" / "playground"))
import brew                                  # the real engine: reuse load_block / reason / compose / brew
from brew import Cart
import ugm as h
from ugm import ask_goal, load_machine_rules


# --- the SHARED decisions (authored once) and the CLI PORT (the only re-authored CNL) --------------

SHARED_BLOCKS = ("business", "ux")           # the decisions — reused verbatim by both targets

# The CLI library block + bridge: the re-authored port. Structurally identical in role to textual.cnl +
# bridge.cnl — it names CLI capabilities and crosswalks the SAME UX features onto them. Note it references
# the SAME feature predicates (`confirmation_step`, `highlighted_discount`) the ux block emits.
CLI_LIBRARY = """
cli_prompt supported_by cli
cli_banner supported_by cli
""".strip()

CLI_BRIDGE = """
confirmation_step realized_by cli_prompt
highlighted_discount realized_by cli_banner
?feat admitted_for ?cart when ?cart requires_feature ?feat and ?feat realized_by ?cap and ?cap supported_by cli
""".strip()


def _split(block_text: str) -> "tuple[list[tuple[str,str,str]], list[str]]":
    facts, rules = [], []
    for raw in block_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        (rules if " when " in line else facts).append(line if " when " in line else tuple(line.split()))
    return facts, rules


# --- REASON for the CLI target: reuse the shared business/UX rules, swap in the CLI library+bridge --

def reason_cli(cart: Cart) -> "brew.Reasoning":
    """Derive the discount + admitted features for the CLI target. Mirrors `brew.reason`, but the library
    and bridge are the CLI port instead of Textual — the business/UX rules are the SAME objects. So a
    feature is admitted only if the CLI toolkit supports its realizer (the honest 'can this toolkit do it'
    gate, re-targeted)."""
    facts: "list[tuple[str,str,str]]" = []
    rules: "list[str]" = []
    for name in SHARED_BLOCKS:               # business + ux, verbatim
        f, r = brew.load_block(name)
        facts += f
        rules += r
    lib_f, _ = _split(CLI_LIBRARY)
    br_f, br_r = _split(CLI_BRIDGE)
    facts += lib_f + br_f
    rules += br_r

    facts += brew._scenario_facts(cart, facts)
    g = brew._graph(facts)
    mrules = load_machine_rules("\n".join(rules))
    granted = ask_goal(g, f"is {cart.name} grants_discount yes", mrules) == ["yes"]
    answers = ask_goal(g, f"who admitted_for {cart.name}", mrules)
    features = {a.split(" ", 1)[0] for a in answers if a.split(" ", 1)[0] in brew._KNOWN_FEATURES}
    return brew.Reasoning(granted=granted, rate=brew._const(facts, "discount_policy", "rate"),
                          features=features, facts=facts, rules=mrules)


# --- EMIT + DRIVE the CLI target (the second real, driven family) ----------------------------------

def emit_cli(cart: Cart, r: "brew.Reasoning", screen: str) -> str:
    """Emit a real, runnable CLI checkout as `run_cli(inputs)` returning an EVENT TRACE — the same trace
    vocabulary the Textual target is driven against (`discount_shown`, `gate_shown`, `completed`). Every
    branch is DERIVED: the banner iff the discount feature was admitted, the gate iff the screen composed
    to a confirm shape. No template — the derived booleans shape the emitted source."""
    show_discount = "highlighted_discount" in r.features
    gated = screen == "confirm_screen"
    lines = [
        "def run_cli(inputs):",
        "    events = []",
        f"    amount = {cart.order_spend}",
    ]
    if show_discount:
        lines += [f"    events.append('discount_shown')   # *** {r.rate:.0f}% OFF ***"]
    if gated:
        lines += [
            "    events.append('gate_shown')",
            "    ans = inputs.pop(0) if inputs else 'y'",
            "    if ans != 'y':",
            "        events.append('aborted'); return events",
        ]
    lines += ["    events.append('completed')", "    return events"]
    return "\n".join(lines)


@dataclass(frozen=True)
class Driven:
    target: str
    screen: str
    events: "tuple[str, ...]"
    ok: bool         # safety: a confirm gate precedes completion iff the sale is irreversible
    live: bool       # liveness: the checkout completes
    shown: bool      # the discount was shown iff granted


def _contracts(cart: Cart, granted: bool, events: "tuple[str, ...]") -> "tuple[bool,bool,bool]":
    """The behavioral contracts, identical across targets and read off the event trace."""
    live = "completed" in events
    if cart.irreversible:                    # safety: the gate must come before completion
        ok = ("gate_shown" in events and "completed" in events
              and events.index("gate_shown") < events.index("completed"))
    else:
        ok = "gate_shown" not in events      # a reversible sale must NOT gate
    shown = ("discount_shown" in events) == granted
    return ok, live, shown


def drive_cli(cart: Cart) -> Driven:
    """Emit the CLI app and RUN it headlessly with a scripted confirm — trust by execution, re-targeted."""
    r = reason_cli(cart)
    _, screen = brew.compose(cart, r.features)
    screen = screen or "one_screen"
    ns: dict = {}
    exec(emit_cli(cart, r, screen), ns)
    events = tuple(ns["run_cli"](["y"]))     # scripted: the shopper confirms
    ok, live, shown = _contracts(cart, r.granted, events)
    return Driven("cli", screen, events, ok, live, shown)


def drive_textual(cart: Cart) -> Driven:
    """Target A: reuse the brew engine — emit the real Textual app and drive it through Pilot."""
    b = brew.brew(cart)
    return Driven("textual", b.screen, tuple(b.verify.events), b.verify.ok, b.verify.live, b.verify.shown)


# --- the ledger: decision-lines reused vs port-lines re-authored -----------------------------------

def _count(block_text_or_name: str, is_file: bool) -> int:
    fr = brew.load_block(block_text_or_name) if is_file else _split(block_text_or_name)
    return len(fr[0]) + len(fr[1])


def ledger() -> dict:
    shared = sum(_count(n, True) for n in SHARED_BLOCKS)                 # authored once, reused by both
    textual_port = _count("textual", True) + _count("bridge", True)     # target A re-authored
    cli_port = _count(CLI_LIBRARY, False) + _count(CLI_BRIDGE, False)   # target B re-authored
    return {"shared_decisions": shared, "textual_port": textual_port, "cli_port": cli_port}


FAMILY = (                                   # a spectrum of carts — the SAME family driven through both targets
    Cart(customer_tier="premium", order_spend=150, irreversible=False),
    Cart(customer_tier="premium", order_spend=150, irreversible=True),
    Cart(customer_tier="basic",   order_spend=150, irreversible=False),
    Cart(customer_tier="basic",   order_spend=80,  irreversible=True),
)


def main() -> None:
    print("RE-TARGETED FAMILIES — the same business/UX decisions drive TWO libraries, both DRIVEN green.\n")

    print("PART 1 — a whole family of carts, through BOTH targets, checked against the SAME contracts:\n")
    print(f"      {'cart':34} {'target':8} {'screen':15} {'ok/live/shown':14} events")
    print(f"      {'-'*34} {'-'*8} {'-'*15} {'-'*14} {'-'*30}")
    all_green = True
    for cart in FAMILY:
        desc = f"{cart.customer_tier}/{cart.order_spend}/{'irrev' if cart.irreversible else 'rev'}"
        for d in (drive_textual(cart), drive_cli(cart)):
            flags = f"{d.ok}/{d.live}/{d.shown}"
            all_green &= (d.ok and d.live and d.shown)
            print(f"      {desc:34} {d.target:8} {d.screen:15} {flags:14} {list(d.events)}")
        print()
    print(f"  Every cart, both targets, all contracts: {'ALL GREEN' if all_green else 'A CONTRACT FAILED'}.")
    print("  The confirm gate appears in BOTH families exactly when the sale is irreversible; the discount")
    print("  shows in BOTH exactly when granted — because both read the SAME business/UX decisions.\n")

    print("PART 2 — the ledger: what was authored ONCE vs re-authored per target port:\n")
    L = ledger()
    print(f"      shared decisions (business + ux), reused by BOTH targets : {L['shared_decisions']} lines")
    print(f"      Textual port     (textual.cnl + bridge.cnl)              : {L['textual_port']} lines re-authored")
    print(f"      CLI port         (library + bridge)                      : {L['cli_port']} lines re-authored")
    reuse = L["shared_decisions"] / (L["shared_decisions"] + L["cli_port"])
    print(f"\n  Re-targeting to the CLI reused {L['shared_decisions']}/{L['shared_decisions']} decision-lines"
          f" verbatim ({100*reuse:.0f}% of the second app's spec was already written); only the {L['cli_port']}-line")
    print("  library port was new. The expensive part — the DECISIONS — is authored once and reused; the")
    print("  re-target cost is the toolkit port, and both families are trusted by DRIVING, not by claim.\n")

    print("READING: the same business/UX CNL drives two independent, driven toolkits. A re-target does not")
    print("re-decide the app — it re-authors only the library block + bridge, and the emitted family is")
    print("verified identically on each target by execution. That is the 'compose the decisions once, target")
    print("many libraries' leg of the scale story: decisions reused at zero cost, ports the only new lines.")


if __name__ == "__main__":
    main()
