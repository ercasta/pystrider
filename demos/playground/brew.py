"""The BREW — four authored blocks in, a verified Textual app out.

    cart knobs + business.cnl + ux.cnl + textual.cnl + bridge.cnl + design.cnl
        -> REASON   forward-chain every block to quiescence
        -> COMPOSE  resolve each design decision (same world, same loop)
        -> EMIT     real Textual source, assembled per DERIVED feature
        -> VERIFY   drive it headlessly through Textual's Pilot and read what happened

This module owns no business, UX or library knowledge of its own. Every fact and
rule lives in the swappable `.cnl` blocks beside it; what is here is the knobs, the
one piece of arithmetic, the source templates, and the driver.

⭐ **REASON and COMPOSE are ONE settle.** They were two stages on an earlier
floor — a backward reader against an earlier engine, then `grammapy` objects in
Python. Here `design.py`'s checks are rules on the same loop as the block rules,
so there is a single fixpoint from `cart customer_tier premium` to *this design
is admitted*.

⚠ **The arithmetic is a RULE, and it is deliberately the only one.** *Does this
order clear the threshold* is a real number crossing a boundary; the DECISION that
follows is the business block's. So `ground_qualification` computes the comparison
and asserts `order_qualifies yes`, and `business.cnl` decides what that earns. The
boundary between what Python computes and what a rule concludes is the whole seam,
and putting the comparison in the block would have meant inventing arithmetic in
CNL to no benefit.

⚠⚠ **VERIFY RUNS THE APP; it does not inspect the source.** A repair that
"succeeds" while emitting byte-identical source is a shipped bug an earlier
engine once caught only by an independent gate. A generated UI has the same
failure mode: a template that renders the right widgets and never wires them
reads perfectly. So the claim here is `events`, observed from a real Textual
app under Pilot — the discount was shown, and highlighted, and the
irreversible checkout was gated BEFORE it completed, because the running app
did those things in that order.

⚠⚠ 2026-08-29: rewritten off `Facts` onto `loopingrules.loop.Loop` and
`cnl.Vocabulary` directly — see `pystrider.cnl`'s own module note for why this
package still carries a small atom-interning class where every other module
moved to fixed components. `Facts(cnl.install(blocks), scenario(cart),
design.install)` used to thread one shared adapter through three installers;
now the SAME `Vocabulary` is built once (`cnl.install(blocks)(loop)`) and
passed explicitly to `scenario`/`design.install`, since there is no longer an
implicit `Facts` object for them to discover it through.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from loopingrules.loop import Loop

from pystrider import cnl, strict

from . import design

_HERE = Path(__file__).parent

#: The five swappable knowledge files, in load order. ⚠ Additive: each is authored
#: in isolation and joined only through shared predicates and the bridge.
BLOCKS = ("business", "ux", "textual", "bridge", "design")


@dataclass(frozen=True)
class Cart:
    """The scenario — the knobs you turn. Everything else is DERIVED from these
    plus the blocks."""

    name: str = "cart"
    customer_tier: str = "premium"     # premium (loyal) | basic
    order_spend: float = 150.0         # the order amount, in your currency
    irreversible: bool = False         # a final purchase -> UX obliges a confirmation step
    highlight_style: str = "reverse"   # a Rich style: reverse | bold


# --- the scenario, as a domain -------------------------------------------------

def scenario(cart: Cart):
    """The cart's own facts, plus the one comparison Python grounds.

    ⚠ The knob values are interned at install, never inside a rule: `Vocabulary.
    word` spawns on a miss and a spawn moves `revision`, so a rule that minted
    would look like it fired on every pass and the world would never settle.
    """

    def installer(loop, v: cnl.Vocabulary) -> None:
        for term in (cart.name, cart.customer_tier, "yes", str(cart.order_spend)):
            v.word(term)
        subject = v.word(cart.name)
        loop.world.attach(subject, cnl.predicate_component("customer_tier")(
            v.word(cart.customer_tier)))
        loop.world.attach(subject, cnl.predicate_component("order_spend")(
            v.word(str(cart.order_spend))))
        # ⚠ What makes this entity findable AS the thing under design. `design.py`
        # looks the cart up by what it is, not by a handle passed in.
        loop.world.attach(subject, cnl.predicate_component("has_checkout")(v.word("yes")))
        if cart.irreversible:
            loop.world.attach(subject, cnl.predicate_component("action_irreversible")(
                v.word("yes")))
        loop.rule(ground_qualification(v), name="brew.ground_qualification")

    return installer


def ground_qualification(v: cnl.Vocabulary):
    """The §8 comparison boundary: the number crosses it in Python, the DECISION
    is left to `business.cnl`.

    ⭐ It reads the threshold out of the BLOCK rather than holding one, so editing
    `discount_policy threshold 100` re-derives the whole app — which is the claim
    the playground exists to make.
    """
    threshold_pred = cnl.predicate_component("threshold")
    order_spend_pred = cnl.predicate_component("order_spend")
    order_qualifies_pred = cnl.predicate_component("order_qualifies")

    def rule(w) -> None:
        policy, yes = v.known("discount_policy"), v.known("yes")
        cart = design._cart(v)
        if policy is None or yes is None or cart is None:
            return
        threshold_held, spend_held = w.get(policy, threshold_pred), w.get(cart, order_spend_pred)
        if threshold_held is None or spend_held is None:
            return
        threshold, spend = v.text(threshold_held.object), v.text(spend_held.object)
        if float(spend) > float(threshold):
            w.attach(cart, order_qualifies_pred(yes))

    return rule


def blocks_with(**edits) -> tuple:
    """The authored blocks, with named ones re-parsed from edited text.

    ⭐ `blocks_with(textual=text.replace("styled_label  supported_by textual", ""))`
    is how a caller asks *what would this system be if the toolkit could not do
    that* — the swap the playground is for, without touching the files.
    """
    out = []
    for name in BLOCKS:
        text = edits.get(name)
        if text is None:
            out.append(cnl.load(_HERE / f"{name}.cnl"))
        else:
            out.append(cnl.parse(text, name=name))
    return tuple(out)


def block_text(name: str) -> str:
    """One authored block's source text, for editing."""
    return (_HERE / f"{name}.cnl").read_text(encoding="utf-8")


# --- REASON + COMPOSE ----------------------------------------------------------

@dataclass
class Reasoning:
    vocabulary: cnl.Vocabulary
    loop: Loop                    # kept for `.rules`/`.errors` -- introspection, never re-run
    blocks: tuple
    granted: bool                 # does the business block grant a discount?
    rate: float                   # the discount percent (business data)
    features: List[str]           # the UX features ADMITTED through the bridge
    ticks: int                    # how many passes the whole thing took to settle

    def why(self, subject: str, predicate: str, obj: str) -> List[str]:
        return cnl.explain(self.vocabulary, self.blocks, cnl.Triple(subject, predicate, obj))


def reason(cart: Cart, blocks=None) -> Reasoning:
    """Load the blocks, install the scenario and the design checks, and settle.

    ⚠ `blocks` is a parameter so a caller can hand in an EDITED block without
    writing to disk. Swapping a block is the claim this playground makes, and a
    test that has to mutate the authored files to check it is a test that can leave
    them mutated.
    """
    blocks = cnl.load_all(_HERE, BLOCKS) if blocks is None else tuple(blocks)
    loop = Loop()
    v = cnl.install(blocks)(loop)
    scenario(cart)(loop, v)
    design.install(loop, v)
    settled = strict.run(loop)
    subject = v.known(cart.name)
    features = sorted(v.text(x) for x in design._subjects_relating_to(v, "admitted_for", subject))
    policy = v.known("discount_policy")
    rate = v.world.get(policy, cnl.predicate_component("rate"))
    return Reasoning(vocabulary=v, loop=loop, blocks=blocks,
                     granted=cnl.ask(v, cart.name, "grants_discount", "yes"),
                     rate=float(v.text(rate.object)),
                     features=features, ticks=settled.ticks)


# --- EMIT ----------------------------------------------------------------------

_HEADER = """\
from textual.app import App, ComposeResult
from textual.widgets import Input, Button, Static
from rich.text import Text
"""
_CONFIRM_IMPORT = "from textual.screen import ModalScreen\n"

_CONFIRM_SCREEN = '''
class ConfirmScreen(ModalScreen):
    """UX confirmation gate for the irreversible checkout."""

    def compose(self) -> ComposeResult:
        yield Static("Confirm your purchase?")
        yield Button("Confirm", id="confirm-ok")
        yield Button("Cancel", id="confirm-cancel")

    def on_mount(self) -> None:
        self.app.events.append("gate_shown")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm-ok")
'''

_APP_HEAD = '''
class CheckoutApp(App):
    """Synthesized checkout app. `events` is the observable trace the verifier reads."""

    DISCOUNT_RATE = {rate}
    APPLIES = {applies}
    HIGHLIGHT_STYLE = "{style}"

    def __init__(self):
        super().__init__()
        self.events = []

    def compose(self) -> ComposeResult:
        yield Input(id="amount")
        yield Button("Checkout", id="checkout")
        yield Static(id="result")

    def _validate(self, raw):
        try:
            amt = float(raw)
        except ValueError:
            self.events.append("rejected non-numeric")
            return None
        if amt <= 0:
            self.events.append("rejected non-positive")
            return None
        return amt

    def _price(self, amount):
        if self.APPLIES:
            return round(amount * (1 - self.DISCOUNT_RATE / 100), 2)
        return round(amount, 2)

    def _complete(self, total):
        self.events.append("completed " + str(total))
'''

#: emitted ONLY when `highlighted_discount` is admitted — the UX rule made concrete.
_SHOW_DISCOUNT = '''
    def _show_discount(self, amount, total):
        saved = round(amount - total, 2)
        label = Text("You saved " + str(saved) + "  ->  pay " + str(total), style=self.HIGHLIGHT_STYLE)
        self.query_one("#result", Static).update(label)
        self.events.append("discount_shown " + str(total))
        self.events.append("highlighted")
'''

_HANDLER_DIRECT = '''
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "checkout":
            return
        amount = self._validate(self.query_one("#amount", Input).value)
        if amount is None:
            return
        total = self._price(amount)
        if hasattr(self, "_show_discount"):
            self._show_discount(amount, total)
        self._complete(total)
'''

#: emitted ONLY when the screen resolved to `confirm_screen` — the gate the UX
#: obligation forced, with completion moved INSIDE the dismissal callback.
_HANDLER_CONFIRM = '''
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "checkout":
            return
        amount = self._validate(self.query_one("#amount", Input).value)
        if amount is None:
            return
        total = self._price(amount)
        if hasattr(self, "_show_discount"):
            self._show_discount(amount, total)
        def after(confirmed):
            if confirmed:
                self._complete(total)
        self.push_screen(ConfirmScreen(), after)
'''


def emit(cart: Cart, reasoning: Reasoning, screen: str) -> str:
    """Assemble the app from the pieces the DERIVED features call for.

    ⚠ Built per feature, never selected from whole-string skeletons: the confirm
    screen is present iff the screen shape resolved to it, and `_show_discount`
    exists iff `highlighted_discount` came through the bridge. `hasattr` in the
    handler is what lets the two vary independently.
    """
    highlight = "highlighted_discount" in reasoning.features
    confirm = screen == "confirm_screen"
    parts = [_HEADER]
    if confirm:
        parts.append(_CONFIRM_IMPORT)
        parts.append(_CONFIRM_SCREEN)
    app = _APP_HEAD.format(rate=reasoning.rate, applies=reasoning.granted,
                           style=cart.highlight_style)
    if highlight:
        app += _SHOW_DISCOUNT
    app += _HANDLER_CONFIRM if confirm else _HANDLER_DIRECT
    parts.append(app)
    return "\n".join(parts)


# --- VERIFY, by DRIVING --------------------------------------------------------

@dataclass
class Verified:
    """What driving the emitted app OBSERVED, under three contracts.

    * `ok`    — SAFETY: an irreversible checkout never `completed` without a prior
      `gate_shown`.
    * `live`  — LIVENESS: driving the happy path, the purchase actually completes.
    * `shown` — HONESTY: when the business granted a discount, it was
      `discount_shown` AND `highlighted` before completion.
    """

    events: List[str] = field(default_factory=list)
    completed: bool = False
    gated: bool = False
    discount_shown: bool = False
    highlighted: bool = False
    ok: bool = False
    live: bool = False
    shown: bool = False

    @property
    def works(self) -> bool:
        return self.ok and self.live and self.shown


async def _drive(app, amount: str, choice: str) -> None:
    """Type the amount, press Checkout, and resolve any confirm gate with `choice`."""
    async with app.run_test() as pilot:
        await pilot.click("#amount")
        for ch in amount:
            await pilot.press(ch)
        await pilot.click("#checkout")
        await pilot.pause()
        for _ in range(3):
            if len(app.screen_stack) <= 1:
                break
            try:
                await pilot.click(f"#{choice}")
            except Exception:
                break
            await pilot.pause()


def _run_events(source: str, amount: str, choice: str) -> List[str]:
    """Exec the emitted app and drive it once, returning the observed trace."""
    namespace: dict = {}
    exec(compile(source, "<emitted-checkout>", "exec"), namespace)   # noqa: S102
    app = namespace["CheckoutApp"]()
    asyncio.run(_drive(app, amount, choice))
    return list(app.events)


def verify(source: str, cart: Cart, reasoning: Reasoning,
           choice: str = "confirm-ok") -> Verified:
    amount = str(int(cart.order_spend))
    events = _run_events(source, amount, choice)

    def first(prefix: str) -> Optional[int]:
        return next((i for i, e in enumerate(events) if e.startswith(prefix)), None)

    completed_at = first("completed")
    gate_at = events.index("gate_shown") if "gate_shown" in events else None
    shown_at = first("discount_shown")

    gated = gate_at is not None and (completed_at is None or gate_at < completed_at)
    ok = (not cart.irreversible) or (completed_at is None) or gated
    if choice == "confirm-ok":
        live = completed_at is not None
    else:
        live = any(e.startswith("completed")
                   for e in _run_events(source, amount, "confirm-ok"))
    shown = (not reasoning.granted) or (
        shown_at is not None and "highlighted" in events
        and (completed_at is None or shown_at < completed_at))
    return Verified(events=events, completed=completed_at is not None, gated=gated,
                    discount_shown=shown_at is not None,
                    highlighted="highlighted" in events, ok=ok, live=live, shown=shown)


# --- the whole brew ------------------------------------------------------------

@dataclass
class Brew:
    cart: Cart
    reasoning: Reasoning
    decisions: List[dict]
    screen: str
    source: str
    verified: Optional[Verified]

    @property
    def admitted(self) -> bool:
        return bool(self.decisions) and all(d["admitted"] for d in self.decisions)


def brew(cart: Cart = Cart(), blocks=None) -> Brew:
    """Turn the knobs, and get back a verified app — or an honest refusal.

    ⚠ Nothing is emitted unless every decision point was admitted. A design with an
    uncovered control signal does not get a best-effort app; it gets no app, and the
    decision table says which point refused it.
    """
    r = reason(cart, blocks)
    table = design.decisions(r.vocabulary)
    screen = design.chosen_screen(r.vocabulary) or "one_screen"
    ok = bool(table) and all(d["admitted"] for d in table)
    source = emit(cart, r, screen) if ok else ""
    return Brew(cart=cart, reasoning=r, decisions=table, screen=screen,
                source=source, verified=verify(source, cart, r) if source else None)
