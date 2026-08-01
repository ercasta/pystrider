"""SLICE 7 — a GOAL derives a real Textual app, and the app is trusted because it is DRIVEN.

This is the README's ending, re-derived on the microfunctions engine. The old one (`demos/playground/`)
loaded four CNL blocks, forward-chained a feature set, composed it with grammapy and assembled the source
by concatenating template strings. The new engine has no forward chaining and this probe has no templates.
Both halves of that sentence are the result.

**⭐ WHAT REPLACES FORWARD CHAINING: a rule's CONDITION is its PARAMETER TYPE.** `grant_discount(b:
qualified_build)` cannot be proposed against a build that has not been qualified, so the planner
rediscovers the dependency order rather than being told it. Turn the knobs and a different plan comes back,
and **the plan IS the derivation** — an ordered account of what was done and why each step was available,
which is a better audit trail than the saturated graph it replaces, because a saturated graph says only
what became true.

**⭐ WHAT REPLACES THE TEMPLATES: graph surgery on a parsed AST.** The skeleton and every fragment go
through `strider.intake`, so each carries `from_code`, an `origin` and a `source_line`. The operations in
`strider/rules/app.mf` splice *those nodes* into the class body, and `strider.emit` renders the result
through `ast.unparse`. Nothing is concatenated, so nothing can be concatenated wrong: the output is valid
Python by construction rather than by inspection, and a fragment containing a construct `strider` cannot
model is REFUSED by the membrane instead of being pasted in unread.

**⚠ THE HONEST LINE BETWEEN AUTHORED AND DERIVED.** The fragment *bodies* are authored Python. This is not
a system that invents `_show_discount`. What is derived is which fragments are in the app and how they are
assembled — from the knobs, by a search that could have gone otherwise. The seams are named (`_present`,
`_finish`), each is filled by exactly one fragment, and which one is the plan's answer.

**⭐ THE SAME THREE CONTRACTS ARE DERIVED AND THEN OBSERVED.** `strider_repair` reached the division
IMAGINATION DERIVES, REALITY EXECUTES because `dispatch.service` refuses an imagined target. Here that
division lands on the *same propositions* from both sides:

| | derived, at plan time | observed, at drive time |
|---|---|---|
| SAFETY | `install_direct_finish` demands `irreversible = false`, so no plan reaches an ungated irreversible app | no `completed` event without a prior `gate_shown` |
| LIVENESS | the goal is unmet until some `_finish` is installed | driving the happy path actually `completed` |
| HONESTY | `install_discount_display` demands `discount = true` | `discount_shown` and `highlighted` precede `completed` |

Types make the unsafe app unreachable rather than detected, which is stronger than a check — **and weaker
than it first looks, in two ways worth naming.** A parameter type is enforced by `driver.proposals`, so it
binds the PLANNER and not a caller: `function.invoke` does not check parameter types, which a pin here
found by asserting a raise and watching the call succeed. `app.mf` now carries an explicit `CHECK` for
that. And both together are only as good as what the types *say* — so `unsafe_without_the_type()` below
relaxes exactly that type, rebuilds, and shows the Pilot drive catching what the derivation stopped
preventing. A green whose control was never run is a green that measures nothing.

**⭐⭐ THE DRIVE EARNED ITS KEEP ON THE FIRST RUN, and the bug it found is the argument for this whole
layer.** The `_present` seam was originally called `_display` — and `App._display` is one of Textual's own
private methods, the one the compositor calls to paint the screen. The emitted app overrode it. Every
structural check passed: the module parsed, the fragment was complete, the plan was valid, the round trip
was byte-exact. It crashed on the first repaint with `unsupported operand type(s) for -: 'Screen' and
'LayoutUpdate'`.

Nothing upstream of execution could have caught that. The graph does not know what `App` already defines,
and the collision is not a property of our code at all — it is a property of code we do not own. **A
generator that verifies its output only against its own model of the world cannot see the world**, which
is precisely why "trust it because you drove it" is a different claim from "trust it because it type
checks". Recorded rather than quietly renamed, because the rename is worth nothing and the reason is worth
a lot.

Run it: `python -m experiments.strider_app`   (needs `pip install textual`)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import strider
from strider.emit import emit
from strider.lift import reachable
from strider.mf import driver, function, goal as G, types

# --- the authored code: one skeleton with two named SEAMS, and the fragments that fill them ------------
#
# ⚠ `ModalScreen` is imported unconditionally even though the gate is only sometimes emitted. Making the
# import conditional would mean inserting a statement BEFORE the class rather than appending after it, and
# `defines` is ordered — an unused import is a cosmetic cost, a mis-ordered one is a broken module.

SKELETON = '''\
from textual import on
from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static
from rich.text import Text


class CheckoutApp(App):
    DISCOUNT_RATE = 20
    APPLIES = False
    HIGHLIGHT_STYLE = 'reverse'

    def __init__(self):
        super().__init__()
        self.events = []

    def compose(self) -> ComposeResult:
        yield Input(id='amount')
        yield Button('Checkout', id='checkout')
        yield Static(id='result')

    def _validate(self, raw):
        text = raw.strip()
        if not text.replace('.', '', 1).isdigit():
            self.events.append('rejected non-numeric')
            return None
        amount = float(text)
        if amount <= 0:
            self.events.append('rejected non-positive')
            return None
        return amount

    def _price(self, amount):
        if self.APPLIES:
            return round(amount * (1 - self.DISCOUNT_RATE / 100), 2)
        return round(amount, 2)

    def _complete(self, total):
        self.events.append('completed ' + str(total))

    @on(Button.Pressed, '#checkout')
    def _checkout(self, event) -> None:
        amount = self._validate(self.query_one('#amount', Input).value)
        if amount is None:
            return
        total = self._price(amount)
        self._present(amount, total)
        self._finish(total)
'''

#: The `_present` seam, filled when the business granted a discount.
DISCOUNT_DISPLAY = '''\
def _present(self, amount, total):
    saved = round(amount - total, 2)
    label = Text(f'You saved {saved}  ->  pay {total}', style=self.HIGHLIGHT_STYLE)
    self.query_one('#result', Static).update(label)
    self.events.append(f'discount_shown {total}')
    self.events.append('highlighted')
'''

#: The same seam when it did not. ⚠ A REAL fragment, not an absence — the skeleton calls `self._present`
#: unconditionally, so "no discount" has to be something the app DOES. The old version asked
#: `hasattr(self, '_show_discount')` at run time, which is the app inspecting itself to find out what was
#: decided about it; here the decision is in the code that got installed.
PLAIN_DISPLAY = '''\
def _present(self, amount, total):
    self.query_one('#result', Static).update(f'Pay {total}')
'''

#: The `_finish` seam for a reversible checkout: complete it.
DIRECT_FINISH = '''\
def _finish(self, total):
    self._complete(total)
'''

#: And for an irreversible one: gate it first. Only ever installed with `CONFIRM_SCREEN`.
GATED_FINISH = '''\
def _finish(self, total):
    def after(confirmed):
        if confirmed:
            self._complete(total)
    self.push_screen(ConfirmScreen(), after)
'''

CONFIRM_SCREEN = '''\
class ConfirmScreen(ModalScreen):

    def compose(self) -> ComposeResult:
        yield Static('Confirm your purchase?')
        yield Button('Confirm', id='confirm-ok')
        yield Button('Cancel', id='confirm-cancel')

    def on_mount(self) -> None:
        self.app.events.append('gate_shown')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == 'confirm-ok')
'''

#: The fragments, by the edge label the operations navigate. Adding one here and an operation that reaches
#: it is the whole cost of a new feature.
FRAGMENTS = {
    "discount_display": DISCOUNT_DISPLAY,
    "plain_display": PLAIN_DISPLAY,
    "direct_finish": DIRECT_FINISH,
    "gated_finish": GATED_FINISH,
    "confirm_screen": CONFIRM_SCREEN,
}


@dataclass(frozen=True)
class Cart:
    """The knobs. Everything downstream is derived from these four numbers and strings."""
    tier: str = "premium"
    spend: int = 150
    threshold: int = 100
    irreversible: bool = False


# --- setting up the world ------------------------------------------------------------------------------

def declare_types(g) -> None:
    """The preconditions, as types — this is where the derivation's dependency order actually lives.

    ⚠ `build` needs a schema that nothing else satisfies, because `driver.proposals` finds candidates by
    matching schemas over every node in the frame and the frame contains the whole AST. `class_block` and
    `module_node` are edges only a build node has, so they identify it structurally rather than by kind."""
    types.declare_type(g, "build", {"class_block": ("block", 1), "module_node": ("module", 1)})
    types.declare_type(g, "qualified_build", base="build", attrs={"qualifies": True})
    types.declare_type(g, "unqualified_build", base="build", attrs={"qualifies": False})
    types.declare_type(g, "discounting_build", base="build", attrs={"discount": True})
    types.declare_type(g, "irreversible_build", base="build", attrs={"irreversible": True})
    types.declare_type(g, "reversible_build", base="build", attrs={"irreversible": False})
    types.declare_type(g, "displaying_build", base="build", attrs={"displays": True})
    types.declare_type(g, "finishing_build", base="build", attrs={"finishes": True})


def find_class(lib, module):
    return next(n for n in reachable(lib, module) if lib.graph.kind(n) == "class_def")


def find_class_constant(lib, class_node, name: str):
    """The `constant` node behind a class-level `NAME = value`, so an operation can rewrite it.

    Located by reading the AST rather than by remembering where it was written — the same reason
    `strider_repair` navigates to the comparison's right operand instead of holding onto it."""
    g = lib.graph
    for stmt in g.targets(g.target(class_node, "does"), "stmt"):
        if g.kind(stmt) != "assign":
            continue
        target = g.target(stmt, "target")
        if target is not None and g.attr(target, "id") == name:
            return g.target(stmt, "value")
    raise LookupError(f"no class-level assignment to {name!r}")


def setup(cart: Cart = Cart()):
    """Intake the skeleton and every fragment, then mint the build node that ties them together."""
    lib = strider.load()
    g = lib.graph
    declare_types(g)

    skeleton = strider.intake(lib, SKELETON, origin="app skeleton")
    if not skeleton.complete:
        raise AssertionError(f"the skeleton is not fully modelled: {skeleton.unmodelled}")
    app_class = find_class(lib, skeleton.module)

    build = g.mint("build", tier=cart.tier, spend=cart.spend, threshold=cart.threshold,
                   irreversible=cart.irreversible)
    g.link(build, "module_node", skeleton.module)
    g.link(build, "class_block", g.target(app_class, "does"))
    g.link(build, "applies_constant", find_class_constant(lib, app_class, "APPLIES"))

    for label, source in FRAGMENTS.items():
        got = strider.intake(lib, source, origin=f"fragment {label}")
        if not got.complete:
            raise AssertionError(f"fragment {label} is not fully modelled: {got.unmodelled}")
        # ⚠ The DEFINITION, not the module. A module node would drag a second `module` into the frame and
        # `build`'s own schema says it has exactly one.
        g.link(build, label, g.targets(got.module, "defines")[0])

    return lib, build, skeleton.module


def build_goal(g, build):
    """Both seams must be filled. Nothing here mentions discounts, gates or Textual.

    ⚠ THE GOAL IS THE SAME FOR EVERY CART, and that is the whole point — if it named the features it
    wanted, the knobs would be decorative and the derivation would be a lookup. It says only that the app
    must display something and must finish; *what* it takes to satisfy that is what the types decide."""
    goal = G.open_goal(g, about=build, label="the app displays a result and completes a checkout")
    G.require_attr(g, goal, build, "displays", True)
    G.require_attr(g, goal, build, "finishes", True)
    return goal


# --- the derivation ------------------------------------------------------------------------------------

def derive(cart: Cart = Cart(), **kw) -> dict:
    """Pursue the goal by imagining, then replay the winning plan against the real graph and emit."""
    from microfunctions import execution as E, thread as T

    lib, build, module = setup(cart)
    g = lib.graph
    goal = build_goal(g, build)
    report = driver.pursue(g, goal, T.open_thread(g, "build app"), build, **kw)
    if not report.get("found"):
        return {"lib": lib, "build": build, "module": module, "cart": cart, "report": report,
                "plan": (), "source": None}

    E.execute(g, report["workbench"], report["frame"])
    return {"lib": lib, "build": build, "module": module, "cart": cart, "report": report,
            "plan": driver.plan_steps(g, report), "source": emit(lib, module)}


def decisions(out: dict) -> dict:
    """What the build node ended up believing — the derivation's verdict, read off the real graph."""
    g = out["lib"].graph
    b = out["build"]
    return {k: g.attr(b, k) for k in ("qualifies", "discount", "displays", "shows_discount",
                                      "finishes", "gated")}


# --- reality: DRIVE the emitted app ---------------------------------------------------------------------

@dataclass
class Driven:
    """What driving the emitted app OBSERVED, against the three contracts the plan derived.

    * `safe`  — an irreversible checkout never `completed` without a prior `gate_shown`.
    * `live`  — driving the happy path, the purchase actually completed.
    * `shown` — when the discount was granted, it was shown AND highlighted before completion."""
    events: list
    completed: bool
    gated: bool
    safe: bool
    live: bool
    shown: bool

    @property
    def works(self) -> bool:
        return self.safe and self.live and self.shown


async def _drive(app, amount: str, choice: str) -> None:
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


def run_events(source: str, amount: str, choice: str = "confirm-ok") -> list:
    """Exec the emitted source and drive it once, returning the observed event trace."""
    namespace: dict = {}
    exec(compile(source, "<emitted-app>", "exec"), namespace)   # noqa: S102 — the point of the gate
    app = namespace["CheckoutApp"]()
    asyncio.run(_drive(app, amount, choice))
    return list(app.events)


def drive(out: dict, choice: str = "confirm-ok") -> Driven:
    """⭐ THE INDEPENDENT GATE. Run the emitted app under Textual's headless Pilot and read what happened.

    ⚠ The contracts are checked against the CART, never against the plan. Grading the emitted app by what
    the derivation intended would make this a re-run of the derivation with extra steps; the question is
    whether the derivation was right about the real toolkit, and only the cart can say what right was."""
    cart = out["cart"]
    events = run_events(out["source"], str(cart.spend), choice)

    def first(prefix):
        return next((i for i, e in enumerate(events) if e.startswith(prefix)), None)

    completed_at, gate_at, shown_at = first("completed"), first("gate_shown"), first("discount_shown")
    completed = completed_at is not None
    gated = gate_at is not None and (completed_at is None or gate_at < completed_at)

    entitled = cart.tier == "premium" and cart.spend >= cart.threshold
    safe = (not cart.irreversible) or (not completed) or gated
    shown = (not entitled) or (shown_at is not None and "highlighted" in events
                               and (completed_at is None or shown_at < completed_at))
    return Driven(events=events, completed=completed, gated=gated, safe=safe, live=completed, shown=shown)


# --- the control: what makes the safety green non-vacuous ------------------------------------------------

def unsafe_without_the_type(cart: Cart = Cart(irreversible=True)) -> dict:
    """⭐ Break the parameter type that carries safety, and watch the drive catch what it no longer prevents.

    `install_direct_finish(b: reversible_build)` is the entire safety argument: an irreversible build
    cannot be bound to it, so the ungated app is unbuildable. That is only as true as the type, so this
    RELAXES `reversible_build` to demand nothing, rebuilds, and forces the direct finish.

    Without this, "the app was safe" would be a claim about a system that was never given the chance to be
    unsafe — and the Pilot drive would be decoration on a guarantee it never tested."""
    lib, build, module = setup(cart)
    g = lib.graph

    # The relaxation: drop `irreversible = false` from the type, so an irreversible build now fits it.
    t = types.find_type(g, "reversible_build")
    for r in list(g.targets(t, "requires_attr")):
        g.unlink(t, "requires_attr", index=0)
    assert types.is_a(g, build, "reversible_build"), "the relaxation did not take"

    function.invoke(g, "qualify", {"b": build})
    function.invoke(g, "install_discount_display" if g.attr(build, "qualifies") else
                    "install_plain_display", {"b": build}) if _grant(g, build) else None
    function.invoke(g, "install_direct_finish", {"b": build})

    out = {"lib": lib, "build": build, "module": module, "cart": cart,
           "report": None, "plan": ("<type relaxed: direct finish forced>",),
           "source": emit(lib, module)}
    return {"out": out, "driven": drive(out)}


def _grant(g, build) -> bool:
    """Take the discount decision the same way the planner would, for the control path."""
    if g.attr(build, "qualifies"):
        function.invoke(g, "grant_discount", {"b": build})
    return True


# --- narration -------------------------------------------------------------------------------------------

CARTS = (
    ("premium, 150, reversible  ", Cart("premium", 150, 100, False)),
    ("premium, 150, IRREVERSIBLE", Cart("premium", 150, 100, True)),
    ("basic,   150, reversible  ", Cart("basic", 150, 100, False)),
    ("premium,  50, IRREVERSIBLE", Cart("premium", 50, 100, True)),
)


def main() -> None:
    print("=" * 96)
    print("ONE goal, ONE library, four carts — the plan is the derivation, the drive is the trust")
    print("=" * 96)

    first = None
    for label, cart in CARTS:
        out = derive(cart)
        driven = drive(out)
        if first is None:
            first = out
        print(f"\n{label}  ->  plan: {' -> '.join(out['plan'])}")
        print(f"{'':28}decided: {decisions(out)}")
        print(f"{'':28}drove:   {driven.events}")
        print(f"{'':28}safe={driven.safe}  live={driven.live}  shown={driven.shown}"
              f"   => {'WORKS' if driven.works else 'BROKEN'}")

    print("\n" + "=" * 96)
    print("The emitted app for the FIRST cart — parsed fragments spliced, rendered by ast.unparse")
    print("=" * 96)
    print(first["source"])

    print("=" * 96)
    print("THE CONTROL: relax the type that carries safety, and the drive catches the unsafe app")
    print("=" * 96)
    broken = unsafe_without_the_type()
    print("  events:", broken["driven"].events)
    print("  safe  :", broken["driven"].safe, " <- the ungated irreversible checkout completed")


if __name__ == "__main__":
    main()
