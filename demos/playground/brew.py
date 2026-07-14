"""The BREW ENGINE — load the four CNL building blocks, reason across them, compose with grammapy,
emit a runnable Textual app, and trust it because it DRIVES green.

This is the "brew them together" step of the playground. It owns no business, UX, or library
knowledge of its own — every fact and rule lives in the swappable `.cnl` blocks next to this file
(`business.cnl`, `ux.cnl`, `textual.cnl`, `bridge.cnl`). The engine only:

    1. LOADS the blocks and sorts each line into facts (bare triples) or rules (`... when ...`);
    2. REASONS — grounds the order's spend-vs-threshold comparison (arithmetic is the tool's job),
       then asks the composed rules `is <cart> grants_discount yes` and `who admitted_for <cart>`;
    3. COMPOSES the derived feature set through grammapy's proven combinators (Accumulate for the
       on-screen widgets, §12 `resolve` for the screen shape, Scope for the confirm-gate reachability);
    4. EMITS a real Textual `App` assembled per derived feature (no whole-string templates);
    5. VERIFIES by DRIVING it headlessly through Textual's Pilot and reading the event trace.

The whole point: change a knob (or a line in a `.cnl` block) and the emitted, verified UI changes —
with the reasoning behind every change auditable via `ask_goal(..., "why ...")`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import ugm as h
from ugm import ask_goal, load_machine_rules
from grammapy import (Accumulate, Channel, CompositionError, DecisionPoint, Defaulted, Footprint,
                      Forced, Item, Production, Scope, ScopeNode, resolve)

_HERE = Path(__file__).parent
BLOCKS = ("business", "ux", "textual", "bridge")   # the four swappable knowledge files


# --- the KNOBS -------------------------------------------------------------------------------

@dataclass(frozen=True)
class Cart:
    """The scenario — the knobs you turn. Everything else is DERIVED from these plus the `.cnl`
    blocks. `order_spend` is a real number compared against the business block's threshold;
    `irreversible` fires the UX confirm obligation; `highlight_style` is how the discount is shown."""
    name: str = "cart"
    customer_tier: str = "premium"     # premium (loyal) | basic
    order_spend: float = 150.0         # the order amount, in your currency
    irreversible: bool = False         # a final purchase -> UX obliges a confirmation step
    highlight_style: str = "reverse"   # how the discount is highlighted (a Rich style: reverse | bold)


# --- LOAD the CNL building blocks (facts vs rules) -------------------------------------------

def load_block(name: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Read one `.cnl` block, dropping comments/blanks, and sort each line into a FACT (a bare
    `s p o` triple) or a RULE (`head when body ...`). This is the only parsing the engine does —
    everything else is the standard ugm/grammapy pattern (facts on a graph, rules as a bank)."""
    facts: list[tuple[str, str, str]] = []
    rules: list[str] = []
    for raw in (_HERE / f"{name}.cnl").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if " when " in line:
            rules.append(line)
        else:
            toks = line.split()
            if len(toks) != 3:
                raise ValueError(f"{name}.cnl: not a 3-token fact nor a rule: {raw!r}")
            facts.append((toks[0], toks[1], toks[2]))
    return facts, rules


def load_kb(blocks: tuple[str, ...] = BLOCKS) -> tuple[list[tuple[str, str, str]], list[str]]:
    """The concatenated knowledge base: every block's facts and rules, summed. Blocks are additive —
    each is authored in isolation and joined only through shared predicates and the bridge."""
    facts: list[tuple[str, str, str]] = []
    rules: list[str] = []
    for b in blocks:
        f, r = load_block(b)
        facts += f
        rules += r
    return facts, rules


def _const(facts, subject: str, pred: str) -> float:
    return float(next(o for (s, p, o) in facts if s == subject and p == pred))


# --- REASON: ground the arithmetic, then ask the composed rules -----------------------------

def _scenario_facts(cart: Cart, kb_facts) -> list[tuple[str, str, str]]:
    """The cart's own facts (the knobs), plus the ONE fact the tool grounds by arithmetic: the order
    qualifies iff its spend clears the business block's threshold (the §8 comparison boundary — the
    number crosses the boundary in Python, the *decision* is left to the rules)."""
    facts = [(cart.name, "customer_tier", cart.customer_tier)]
    if cart.order_spend > _const(kb_facts, "discount_policy", "threshold"):
        facts.append((cart.name, "order_qualifies", "yes"))
    if cart.irreversible:
        facts.append((cart.name, "action_irreversible", "yes"))
    return facts


def _graph(triples) -> "h.Graph":
    g = h.Graph()
    ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids:
            ids[x] = g.add_node(x)
        return ids[x]
    for s, p, o in triples:
        g.add_relation(n(s), p, n(o))
    return g


@dataclass
class Reasoning:
    granted: bool                      # does the business block grant a discount?
    rate: float                        # the discount percent (business data), for pricing the app
    features: set[str]                 # which UX features are ADMITTED (bridge-gated by library support)
    facts: list[tuple[str, str, str]]  # the full fact base (for `why` traces)
    rules: object                      # the parsed rule bank


_KNOWN_FEATURES = {"confirmation_step", "highlighted_discount"}


def reason(cart: Cart) -> Reasoning:
    """Load the blocks, ground the scenario, and derive the discount + admitted feature set with two
    backward queries over the composed rules. No glue — `grants_discount` and `admitted_for` are
    ordinary derived predicates, so this is `ask_goal`, and the `why` of each is available for free."""
    kb_facts, kb_rules = load_kb()
    facts = kb_facts + _scenario_facts(cart, kb_facts)
    g = _graph(facts)
    rules = load_machine_rules("\n".join(kb_rules))
    granted = ask_goal(g, f"is {cart.name} grants_discount yes", rules) == ["yes"]
    answers = ask_goal(g, f"who admitted_for {cart.name}", rules)
    features = {a.split(" ", 1)[0] for a in answers if a.split(" ", 1)[0] in _KNOWN_FEATURES}
    return Reasoning(granted=granted, rate=_const(kb_facts, "discount_policy", "rate"),
                     features=features, facts=facts, rules=rules)


def why(cart: Cart, question: str) -> list[str]:
    """The proof for any derived fact — e.g. `why cart has_benefit discount` or
    `why cart requires_feature highlighted_discount` — one journal spanning business, UX, and bridge."""
    kb_facts, kb_rules = load_kb()
    g = _graph(kb_facts + _scenario_facts(cart, kb_facts))
    return ask_goal(g, question, load_machine_rules("\n".join(kb_rules)))


# --- COMPOSE the feature set with grammapy's proven combinators ------------------------------

SCREEN_POINT = DecisionPoint(
    "screen",
    productions=(
        Production("one_screen", frozenset()),                       # the compact default
        Production("confirm_screen", frozenset({"confirmation"})),   # provides the confirmation capability
    ),
    default="one_screen",
)
COMPLETE_SIGNAL = "needs_confirmation"   # the control effect an irreversible checkout emits


def _required_caps(features: set[str]) -> frozenset:
    return frozenset({"confirmation"}) if "confirmation_step" in features else frozenset()


def _screen_atoms(features: set[str]) -> list[Item]:
    """Each on-screen widget as a grammapy Accumulate atom writing its own slot — the frame rule
    admits the set iff their writes are pairwise disjoint (interference caught at design time)."""
    items = [
        Item(label="input amount", footprint=Footprint.of(writes=[Channel("screen.amount")])),
        Item(label="checkout button", footprint=Footprint.of(writes=[Channel("screen.checkout")])),
        Item(label="result label", footprint=Footprint.of(writes=[Channel("screen.result")])),
    ]
    if "highlighted_discount" in features:
        items.append(Item(label="discount highlight",
                          footprint=Footprint.of(writes=[Channel("screen.result.style")])))
    return items


def _scope_tree(cart: Cart, screen: str) -> ScopeNode:
    """The control tree: the completion leaf EMITS `needs_confirmation` iff irreversible; the confirm
    screen (when present) HANDLES it. Scope admits the app iff every emitted signal is covered."""
    complete = ScopeNode.of("complete_purchase",
                            emits=[COMPLETE_SIGNAL] if cart.irreversible else [])
    if screen == "confirm_screen":
        gate = ScopeNode.of("confirm_screen", handles=[COMPLETE_SIGNAL], children=[complete])
        return ScopeNode.of("CheckoutApp", children=[gate])
    return ScopeNode.of("CheckoutApp", children=[complete])


@dataclass
class Decision:
    point: str
    combinator: str
    value: str
    admitted: bool
    detail: str = ""


def compose(cart: Cart, features: set[str]) -> tuple[list[Decision], str | None]:
    """Resolve every design-time decision through its grammapy combinator: the widget set (Accumulate),
    the screen shape (§12 resolve), and the completion-effect reachability (Scope). Returns the
    decisions and the resolved screen (None if it did not resolve to exactly one production)."""
    decisions: list[Decision] = []

    atoms = _screen_atoms(features)                                  # 1. widgets — Accumulate
    try:
        Accumulate.check(atoms)
        decisions.append(Decision("widgets", "Accumulate", f"{len(atoms)} atoms, writes disjoint", True))
    except CompositionError as e:
        decisions.append(Decision("widgets", "Accumulate", "rejected", False, str(e)))

    res = resolve(SCREEN_POINT, _required_caps(features))            # 2. screen — §12 resolve
    screen = res.production if isinstance(res, (Forced, Defaulted)) else None
    decisions.append(Decision("screen", "resolve", screen or "unresolved", screen is not None, str(res)))

    try:                                                            # 3. effect handling — Scope
        Scope.check(_scope_tree(cart, screen or "one_screen"))
        decisions.append(Decision("effect", "Scope",
                                  f"{COMPLETE_SIGNAL} handled" if cart.irreversible else "no effect", True))
    except CompositionError as e:
        decisions.append(Decision("effect", "Scope", "rejected", False, str(e)))

    return decisions, screen


# --- EMIT the Textual app, assembled per DERIVED feature -------------------------------------

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

# emitted only when the `highlighted_discount` feature is admitted — the UX rule made concrete.
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
    """Assemble the app source from the pieces the DERIVED features call for: a confirm screen iff the
    screen resolved to `confirm_screen`, a discount display iff `highlighted_discount` is admitted, and
    the matching button handler. Built per feature, not selected from whole-string skeletons."""
    highlight = "highlighted_discount" in reasoning.features
    confirm = screen == "confirm_screen"
    parts = [_HEADER]
    if confirm:
        parts.append(_CONFIRM_IMPORT)
        parts.append(_CONFIRM_SCREEN)
    app = _APP_HEAD.format(rate=reasoning.rate, applies=reasoning.granted, style=cart.highlight_style)
    if highlight:
        app += _SHOW_DISCOUNT
    app += _HANDLER_CONFIRM if confirm else _HANDLER_DIRECT
    parts.append(app)
    return "\n".join(parts)


# --- VERIFY by DRIVING the emitted app through Textual's Pilot -------------------------------

@dataclass
class VerifyResult:
    """What DRIVING the emitted app OBSERVED, under three contracts:

    * `ok`   — SAFETY: an irreversible checkout never `completed` without a prior `gate_shown`.
    * `live` — LIVENESS: driving the HAPPY path (confirm), the purchase actually completes.
    * `shown` — HONESTY: when the business granted a discount, it was `discount_shown` AND
      `highlighted` before completion — "show a discount" verified as behaviour, not a claim."""
    events: list[str]
    completed: bool
    gated: bool
    discount_shown: bool
    highlighted: bool
    ok: bool
    live: bool
    shown: bool


async def _drive(app, amount: str, choice: str) -> None:
    """Type `amount` into the input, press Checkout, and resolve any confirm gate by pressing `choice`
    (`confirm-ok` proceeds, `confirm-cancel` aborts). One driver carries either app shape to completion."""
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


def _run_events(source: str, amount: str, choice: str) -> list[str]:
    """Exec the emitted app source and drive it once, returning the observed event trace. Safe: the
    source is our own pre-minted, self-contained skeleton."""
    ns: dict[str, object] = {}
    exec(compile(source, "<emitted-checkout>", "exec"), ns)
    app = ns["CheckoutApp"]()
    asyncio.run(_drive(app, amount, choice))
    return list(app.events)


def verify(source: str, cart: Cart, reasoning: Reasoning, choice: str = "confirm-ok") -> VerifyResult:
    """RUN the emitted app under Textual's headless Pilot and read its event trace — trust by execution.
    Reports safety (`ok`), liveness (`live`), and discount honesty (`shown`)."""
    amount = str(int(cart.order_spend))
    events = _run_events(source, amount, choice)

    def first(pred: str):
        return next((i for i, e in enumerate(events) if e.startswith(pred)), None)

    completed_at = first("completed")
    completed = completed_at is not None
    gate_at = events.index("gate_shown") if "gate_shown" in events else None
    gated = gate_at is not None and (completed_at is None or gate_at < completed_at)
    ds_at = first("discount_shown")
    discount_shown = ds_at is not None
    highlighted = "highlighted" in events

    ok = (not cart.irreversible) or (not completed) or gated
    if choice == "confirm-ok":
        live = completed
    else:
        live = any(e.startswith("completed") for e in _run_events(source, amount, "confirm-ok"))
    shown = (not reasoning.granted) or (
        discount_shown and highlighted and (completed_at is None or ds_at < completed_at))
    return VerifyResult(events=events, completed=completed, gated=gated, discount_shown=discount_shown,
                        highlighted=highlighted, ok=ok, live=live, shown=shown)


# --- the whole brew -------------------------------------------------------------------------

@dataclass
class Brew:
    cart: Cart
    reasoning: Reasoning
    decisions: list[Decision]
    screen: str
    source: str
    verify: VerifyResult | None

    @property
    def admitted(self) -> bool:
        return all(d.admitted for d in self.decisions)


def brew(cart: Cart) -> Brew:
    """cart knobs + the four CNL blocks -> REASON (discount + admitted features) -> COMPOSE every
    decision through grammapy -> EMIT real Textual source -> VERIFY by DRIVING it. The one loop the
    playground turns the knobs on."""
    r = reason(cart)
    decisions, screen = compose(cart, r.features)
    screen = screen or "one_screen"
    source = emit(cart, r, screen) if all(d.admitted for d in decisions) else ""
    vr = verify(source, cart, r) if source else None
    return Brew(cart=cart, reasoning=r, decisions=decisions, screen=screen, source=source, verify=vr)
