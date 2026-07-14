"""Feasibility probe — APP SYNTHESIS: synthesize a *runnable Textual app* across three bridged
knowledge domains, trusted because it is DRIVEN (docs/api_absorption_design.md §4b; the synthesis
axis, `experiments/spec_synthesis.py` / `codegen_understand.py`, pointed at an application target).

For the first time the emitted artifact is not a pure `def f(...): return` but a runnable **app** — a
Textual `App`/`Screen` with event handlers — and it fuses THREE vocabularies joined by bridges:

    business (a cash-withdrawal procedure)   read the amount -> validate -> perform -> report
    framework (the Textual API)              Input.value, Button.Pressed, push_screen(ModalScreen)
    UX (a confirmation pattern)              an IRREVERSIBLE action must be gated by a confirm step

Everything but the verifier REUSES what is already built:

  * SELECTION is the productized `pystrider.emit.select` (realize -> CHOOSE -> trace) — the same loop
    the five synthesis probes share, here choosing among app-shaped SKELETONS instead of function
    templates. Rules only select a pre-minted candidate; the emit tool owns the source.
  * The REQUIRED features are DERIVED across the three domains by a small refinement bank (the mirror
    of `codegen_understand`'s `requires named_steps`): a business fact (`withdrawal is_irreversible`)
    fires a UX rule (`requires confirmation_step`) that is admitted only because the framework SUPPORTS
    it (an absorbed `modal_confirm supported_by textual` fact, reached through a bridge). The
    `why <spec> needs confirmation_step` trace interleaves all three — business, UX, and the framework
    bridge — in one journal, exactly as `conformance_strider`'s two-world proof names its bridge.

The ONE genuinely new piece — the feasibility crux — is VERIFICATION. Every other axis verifies by
re-execution of a pure function on a sentinel. An app has no return value; its correctness IS
interactive behaviour. So `verify_by_pilot` DRIVES the emitted app headlessly through Textual's
`App.run_test()` Pilot — types an amount, presses OK, completes any confirmation gate — and OBSERVES
what happened. That is the design's concrete-exec tool scaled from "call a function" to "drive a UI".

**The finding — a winner-flip under one fact, verified by driving both.** With a lenient spec CHOOSE
prefers the compact ONE-SCREEN app (input -> OK -> withdrawn) and the Pilot drives it green. Mark the
withdrawal `irreversible` and the winner FLIPS to the CONFIRM-SCREEN app — the same shape as
`readable`->`named_steps` and `preserves_input`->the explicit ifexp. And the flip is not merely
*declared*: driving the confirm app OBSERVES a confirmation screen gate the withdrawal (`gate_shown`
before `withdrawn`), while driving the one-screen app performs immediately with NO gate — so execution
CONFIRMS exactly what selection claimed. The generator proposes; the Pilot disposes.

**Toward productization — the two primitives it needs, and the property it must keep.** The step
beyond the flip adds the reasoning a productized synthesizer runs on: a DEONTIC layer (an irreversible
action carries a firm OBLIGATION to confirm — a modality, not a flag) and a DEFEASIBLE PREFERENCE layer
(a confirmation screen's buttons DEFAULT to ok+cancel *unless the spec expresses otherwise* — the
"default unless overridden" primitive, as stratified negation). The clean split: obligations are firm,
preferences defeasible. Both are authored as SEPARABLE fragments joined only by bridges, and the
feasibility property to watch is *scaling via composition* — fragments must concatenate additively as
their count grows, with bridges the sole cross-vocabulary join. The Cancel default is itself
execution-checked: driving it ABORTS the withdrawal, so the preference is real, not declared.

Run it: `python -m experiments.app_synthesis`  (requires `textual`; see requirements.txt).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import ugm as h
from ugm import load_machine_rules, ask_goal

from pystrider.emit import Candidate, select, Selection


# --- the succinct business spec (DATA) --------------------------------------------------------

@dataclass(frozen=True)
class Spec:
    """A terse specification of the withdrawal app. `irreversible` is the one business fact whose
    deontic expansion flips CHOOSE's winner; `buttons`, when set, is an explicit OVERRIDE of the
    confirmation screen's defeasible default button set (`None` == take the default). The spec only
    ever says what DIFFERS from the defaults — "default unless the specification expresses a different
    requirement" — so a terse spec leans on the preference layer for everything it stays silent on."""
    name: str                     # graph id, e.g. "withdraw_spec"
    procedure: str = "withdrawal" # the business procedure this app performs
    irreversible: bool = False    # business fact: the action cannot be undone -> OBLIGES a confirm step
    buttons: tuple[str, ...] | None = None  # override the default confirm buttons (None => default ok+cancel)


# --- the ABSORBED framework surface + the cross-domain BRIDGE (DATA) ---------------------------
# The Textual API enters as absorbed FACTS (the `api_absorption` shape), not authored rules. A UX
# feature is admitted only if some framework CAPABILITY realizes it and Textual SUPPORTS that
# capability — the bridge is the only link between the UX vocabulary and the framework vocabulary.
FRAMEWORK_FACTS: list[tuple[str, str, str]] = [
    ("modal_confirm", "supported_by", "textual"),   # absorbed: Textual has push_screen(ModalScreen)
    ("input_value", "supported_by", "textual"),     # absorbed: Textual has Input.value
]
BRIDGE: list[tuple[str, str, str]] = [
    ("confirmation_step", "realized_by", "modal_confirm"),  # UX feature -> framework capability
    ("read_amount", "realized_by", "input_value"),
]

# the DEONTIC->feature link (which feature an obligation needs) — a separable knowledge fragment.
DEONTIC_FACTS: list[tuple[str, str, str]] = [
    ("confirm", "deontic_needs", "confirmation_step"),
]

# the defeasible PREFERENCE defaults — "a confirmation screen usually has OK and Cancel". Authored as
# plain facts the preference rules consult; the spec overrides them by naming its own button set.
DEFAULT_FACTS: list[tuple[str, str, str]] = [
    ("confirmation_step", "default_button", "ok"),
    ("confirmation_step", "default_button", "cancel"),
]
BUTTON_ORDER = ("ok", "cancel")   # stable emission order; unknown buttons sort after, alphabetically


# --- the refinement bank (CNL) — authored as SEPARABLE, ADDITIVELY-COMPOSED fragments -----------
# The productization bet is *scaling via composition*: knowledge arrives as small independent
# fragments (a deontic rule, a preference default, a bridge fact) that CONCATENATE without rewiring,
# and BRIDGES are the only cross-vocabulary join. Each fragment below is authored in isolation; the
# bank is their sum. Stratified, pure Datalog — binds pre-authored nodes, mints nothing.

# fragment 1 — BUSINESS: a procedure is irreversible iff the business says so (business vocabulary).
_F_BUSINESS = [
    "?spec action_irreversible yes when ?spec procedure ?proc and ?proc is_irreversible yes",
]
# fragment 2 — DEONTIC (firm): an irreversible action carries an OBLIGATION to confirm. Obligations
# are not defeasible by preference — this is the modality layer, distinct from a mere feature flag.
_F_DEONTIC = [
    "?spec obliged confirm when ?spec action_irreversible yes",
]
# fragment 3 — the DEONTIC->FEATURE BRIDGE, gated by absorbed framework support: an obligation is
# NEEDED as a feature only if a capability realizes it and the framework supports that capability.
_F_REQUIRE = [
    "?feat needed_by ?spec when ?spec obliged ?act and ?act deontic_needs ?feat "
    "and ?feat realized_by ?cap and ?cap supported_by textual",
]
# fragment 4 — PREFERENCE (defeasible): a needed confirmation screen's buttons DEFAULT to the default
# set, UNLESS the spec expresses its own button requirement (specificity override). This is the
# "default unless the specification says otherwise" primitive, as stratified negation.
_F_PREFERENCE = [
    "?spec overrides_confirm_buttons yes when ?spec requires_confirm_button ?b",
    "?b is_confirm_button_of ?spec when confirmation_step default_button ?b "
    "and confirmation_step needed_by ?spec and not ?spec overrides_confirm_buttons yes",
    "?b is_confirm_button_of ?spec when ?spec requires_confirm_button ?b",
]
REFINE = "\n".join(_F_BUSINESS + _F_DEONTIC + _F_REQUIRE + _F_PREFERENCE)


def _refine_facts(spec: Spec) -> list[tuple[str, str, str]]:
    """The spec facts + every separable knowledge fragment, concatenated (the reverse of intake). The
    business `is_irreversible` fact appears only when the spec declares it, and `requires_confirm_button`
    only when the spec OVERRIDES the default set — the spec states only what differs from the defaults."""
    facts = [(spec.name, "is_a", "spec"), (spec.name, "procedure", spec.procedure)]
    if spec.irreversible:
        facts.append((spec.procedure, "is_irreversible", "yes"))
    for b in (spec.buttons or ()):                      # explicit override of the default button set
        facts.append((spec.name, "requires_confirm_button", b))
    return (facts + list(FRAMEWORK_FACTS) + list(BRIDGE)
            + list(DEONTIC_FACTS) + list(DEFAULT_FACTS))


def _refine_graph(spec: Spec) -> "h.Graph":
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    for s, p, o in _refine_facts(spec):
        g.add_relation(n(s), p, n(o))
    return g


def required_features(spec: Spec) -> set[str]:
    """DERIVE which features the app must provide by composing the fragments: the business fact fires
    the DEONTIC obligation, which needs a feature admitted only through the framework support bridge.
    `who needed_by <spec>` — one backward query, not glue (the mirror of a spec's derived `requires`)."""
    g = _refine_graph(spec)
    answers = ask_goal(g, f"who needed_by {spec.name}", load_machine_rules(REFINE))
    known = {"confirmation_step", "read_amount"}
    return {a.split(" ", 1)[0] for a in answers if a.split(" ", 1)[0] in known}


def requirement_trace(spec: Spec, feat: str) -> list[str]:
    """RECORD the composed proof for WHY the app needs `feat` — one journal interleaving the business
    fact, the deontic obligation, and the framework bridge (the mirror of `conformance_strider`'s
    two-world proof naming its bridge)."""
    return ask_goal(_refine_graph(spec), f"why {feat} needed_by {spec.name}", load_machine_rules(REFINE))


def confirm_buttons(spec: Spec) -> set[str]:
    """DERIVE the confirmation screen's button set by the DEFEASIBLE preference: the default set unless
    the spec overrides it. `who is_confirm_button_of <spec>` — the "default unless the spec says
    otherwise" primitive, resolved through the public firmware (empty when no confirm screen is needed)."""
    g = _refine_graph(spec)
    answers = ask_goal(g, f"who is_confirm_button_of {spec.name}", load_machine_rules(REFINE))
    known = {"ok", "cancel"} | set(spec.buttons or ())
    return {a.split(" ", 1)[0] for a in answers if a.split(" ", 1)[0] in known}


def _ordered_buttons(spec: Spec) -> list[str]:
    """The derived button set in stable emission order (known buttons first, then the rest sorted)."""
    bs = confirm_buttons(spec)
    return [b for b in BUTTON_ORDER if b in bs] + sorted(b for b in bs if b not in BUTTON_ORDER)


def confirm_button_trace(spec: Spec, button: str) -> list[str]:
    """RECORD why a given button is in the confirmation screen — a DEFAULT (no override) or an explicit
    spec requirement. The provenance of a defeasible decision."""
    return ask_goal(_refine_graph(spec), f"why {button} is_confirm_button_of {spec.name}",
                    load_machine_rules(REFINE))


# --- the emit tool: pre-minted app SKELETONS, each carrying its own source template ------------
# Rules cannot MINT an app (the existential wall). So the tool pre-mints a bounded pool of app
# skeletons; the CNL rules only SELECT the realizing one. Each skeleton emits real Textual source
# that RECORDS its events (`gate_shown`, `withdrawn <amt>`) so the Pilot verifier can OBSERVE them,
# and also `print("withdrawn")` — the user-visible effect the spec asks for.

_APP_HEADER = '''\
from textual.app import App, ComposeResult
from textual.widgets import Input, Button
'''

_APP_BODY = '''\
class WithdrawApp(App):
    """Synthesized cash-withdrawal app. `events` is the observable trace the verifier reads."""
    def __init__(self):
        super().__init__()
        self.events = []

    def compose(self) -> ComposeResult:
        yield Input(id="amount")
        yield Button("OK", id="ok")

    def _perform(self, amount):
        self.events.append("withdrawn " + amount)
        print("withdrawn")

    def _validate(self, raw):
        # business rule: the amount must be a positive number
        try:
            amt = float(raw)
        except ValueError:
            self.events.append("rejected non-numeric"); return None
        if amt <= 0:
            self.events.append("rejected non-positive"); return None
        return raw
'''

_HANDLER_DIRECT = '''\
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "ok":
            return
        amount = self._validate(self.query_one("#amount", Input).value)
        if amount is not None:
            self._perform(amount)
'''

def _confirm_screen_block(buttons: list[str]) -> str:
    """Emit the confirmation ModalScreen with exactly the DERIVED buttons (the defeasible preference,
    materialized). The affirmative button is `confirm-ok` (proceed); any other dismisses as abort — so
    the same one-line `dismiss` handles any button subset the preference layer produces."""
    yields = "\n".join(f'        yield Button("{b.title()}", id="confirm-{b}")' for b in buttons)
    return (
        "from textual.screen import ModalScreen\n\n\n"
        "class ConfirmScreen(ModalScreen):\n"
        '    """UX confirmation gate for the irreversible withdrawal."""\n'
        "    def compose(self) -> ComposeResult:\n"
        f"{yields}\n\n"
        "    def on_mount(self) -> None:\n"
        '        self.app.events.append("gate_shown")\n\n'
        "    def on_button_pressed(self, event: Button.Pressed) -> None:\n"
        "        event.stop()\n"
        '        self.dismiss(event.button.id == "confirm-ok")\n'
    )


_HANDLER_CONFIRM = '''\
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "ok":
            return
        amount = self._validate(self.query_one("#amount", Input).value)
        if amount is None:
            return
        def after(confirmed):
            if confirmed:
                self._perform(amount)
        self.push_screen(ConfirmScreen(), after)
'''


def _emit_one_screen(spec: Spec) -> str:
    """The compact app: input -> OK -> validate -> withdraw. No confirmation gate."""
    return _APP_HEADER + "\n\n" + _APP_BODY + "\n" + _HANDLER_DIRECT


def _emit_confirm_screen(spec: Spec) -> str:
    """The gated app: input -> OK -> validate -> push a ModalScreen (with the DERIVED buttons) ->
    ok/cancel -> withdraw. The button set comes from the defeasible preference, not the template."""
    return (_APP_HEADER + "\n" + _confirm_screen_block(_ordered_buttons(spec))
            + "\n\n" + _APP_BODY + "\n" + _HANDLER_CONFIRM)


# the pre-minted candidate pool — the rules only SELECT among these (fit: compact wins by default).
CANDIDATES: list[Candidate] = [
    Candidate("one_screen", provides=frozenset(), fit=1.0, emit=_emit_one_screen),
    Candidate("confirm_screen", provides=frozenset({"confirmation_step"}), fit=0.7,
              emit=_emit_confirm_screen),
]


# --- VERIFY by DRIVING the app (the feasibility crux — concrete-exec scaled to a UI) -----------

@dataclass
class VerifyResult:
    """What DRIVING the emitted app OBSERVED. `performed` = the withdrawal happened; `gated` = a
    confirmation screen appeared BEFORE it; `ok` = the observable UX contract holds — an irreversible
    action never performs WITHOUT a prior gate (so an aborted run is still `ok`: it did not perform)."""
    events: list[str]
    performed: bool
    gated: bool
    ok: bool


async def _drive(app, choice: str = "ok") -> None:
    """Type a valid amount, press OK, and resolve any confirmation gate by pressing `choice`
    (`ok` proceeds, `cancel` aborts) — one generic driver that carries EITHER app shape to completion.
    If the chosen button is absent (an overridden button set), it leaves the gate unresolved."""
    async with app.run_test() as pilot:
        await pilot.click("#amount")
        await pilot.press("4", "2")
        await pilot.click("#ok")
        await pilot.pause()
        for _ in range(3):                      # resolve a confirmation gate if one was raised
            if len(app.screen_stack) <= 1:      # no modal screen on top -> nothing to confirm
                break
            try:
                await pilot.click(f"#confirm-{choice}")
            except Exception:                   # chosen button not present -> cannot resolve the gate
                break
            await pilot.pause()


def verify_by_pilot(source: str, spec: Spec, confirm_choice: str = "ok") -> VerifyResult:
    """RUN the emitted app under Textual's headless Pilot and OBSERVE its event trace — trust by
    execution, never by the skeleton's `provides` claim. Drive the gate with `confirm_choice` (`ok`
    proceeds, `cancel` aborts). `ok` = the UX contract holds: for an irreversible action, any
    withdrawal was gated. Safe: our own pre-minted, self-contained app source."""
    ns: dict[str, object] = {}
    exec(compile(source, "<emitted-app>", "exec"), ns)
    app = ns["WithdrawApp"]()
    asyncio.run(_drive(app, confirm_choice))
    events = list(app.events)
    withdrawn_at = next((i for i, e in enumerate(events) if e.startswith("withdrawn")), None)
    performed = withdrawn_at is not None
    gated = "gate_shown" in events and (withdrawn_at is None or events.index("gate_shown") < withdrawn_at)
    ok = (not spec.irreversible) or (not performed) or gated     # irreversible => performing requires a gate
    return VerifyResult(events=events, performed=performed, gated=gated, ok=ok)


# --- the whole synthesis loop -----------------------------------------------------------------

@dataclass
class Synthesis:
    spec: Spec
    required: set[str]
    selection: Selection
    source: str
    verify: VerifyResult | None
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def winner(self) -> str | None:
        return self.selection.winner


def synthesize(spec: Spec) -> Synthesis:
    """spec -> DERIVE required features across three domains -> SELECT the realizing graded-best app
    (productized `emit.select`) -> EMIT real Textual source -> VERIFY by DRIVING it. The synthesis
    loop, one firmware, now with an app as the target and a Pilot as the concrete oracle."""
    required = required_features(spec)
    sel = select(spec.name, required, CANDIDATES)
    source = sel.winner_candidate.emit(spec) if sel.winner_candidate else ""
    vr = verify_by_pilot(source, spec) if source else None
    return Synthesis(spec=spec, required=required, selection=sel, source=source,
                     verify=vr, candidates=CANDIDATES)


# --- live walkthrough -------------------------------------------------------------------------

def _show(spec: Spec) -> None:
    r = synthesize(spec)
    flag = "IRREVERSIBLE (UX demands a confirm step)" if spec.irreversible else "lenient (compact allowed)"
    print(f"=== spec: {spec.procedure} app - {flag} ===")
    print(f"  refine (business -> deontic -> framework) -> required features: {sorted(r.required) or '[]'}")
    print(f"  select -> realizing apps: {r.selection.realizing}  ->  winner: {r.winner}")
    vr = r.verify
    print(f"  drive  -> events: {vr.events}")
    print(f"           performed={vr.performed}  gated={vr.gated}  "
          f"=> {'SPEC HOLDS' if vr.ok else 'SPEC VIOLATED'}\n")


def main() -> None:
    print("APP SYNTHESIS - a runnable Textual app across three bridged domains, verified by DRIVING\n")

    print("PART 1 - the winner-flip under one UX fact\n")
    _show(Spec(name="withdraw_spec"))                       # lenient: compact one-screen wins
    _show(Spec(name="withdraw_spec", irreversible=True))    # irreversible: the FLIP -> confirm-screen

    print("Why the flip: both apps withdraw, so CHOOSE prefers the compact one-screen - until the\n"
          "business fact `withdrawal is_irreversible` fires the deontic obligation `obliged confirm`,\n"
          "which needs `confirmation_step` (through the framework bridge) - only the confirm app provides it.\n")

    print("RECORD -> the composed proof for `needs confirmation_step` (business + deontic + framework):")
    for line in requirement_trace(Spec(name="withdraw_spec", irreversible=True), "confirmation_step"):
        print(f"    {line}")

    print("\nPART 2 - the flip is EXECUTION-verified, not merely declared\n")
    strict = Spec(name="withdraw_spec", irreversible=True)
    confirm_src = _emit_confirm_screen(strict)
    one_src = _emit_one_screen(strict)
    vr_confirm = verify_by_pilot(confirm_src, strict)
    vr_one = verify_by_pilot(one_src, strict)
    print(f"  drive the CONFIRM app (the winner):  gated={vr_confirm.gated}  ok={vr_confirm.ok}"
          f"   <- a confirmation screen gated the withdrawal")
    print(f"  drive the ONE-SCREEN app (rejected):  gated={vr_one.gated}  ok={vr_one.ok}"
          f"   <- it withdrew with NO gate, so execution rejects it for an irreversible action")
    print("\n  So driving CONFIRMS what selection claimed: the confirm app has the UX gate, the")
    print("  one-screen app does not. The generator proposes; the Pilot disposes.\n")

    print("PART 3 - defeasible PREFERENCE: buttons default to ok+cancel, overridable by the spec\n")
    default = Spec(name="withdraw_spec", irreversible=True)
    override = Spec(name="withdraw_spec", irreversible=True, buttons=("ok",))
    print(f"  default spec       -> confirm buttons: {_ordered_buttons(default)}   (the default set)")
    print(f"  spec buttons=(ok,) -> confirm buttons: {_ordered_buttons(override)}          "
          f"(the default is OVERRIDDEN)")
    print("  why 'cancel' is present by default:")
    for line in confirm_button_trace(default, "cancel"):
        print(f"      {line}")

    print("\n  the default Cancel button is REAL - drive it and the withdrawal ABORTS:")
    vr_cancel = verify_by_pilot(_emit_confirm_screen(default), default, confirm_choice="cancel")
    print(f"      drive cancel -> events: {vr_cancel.events}  performed={vr_cancel.performed}  "
          f"ok={vr_cancel.ok}  (gated, aborted safely)")

    print("\nCOMPOSITION - every line above came from a SEPARATE knowledge fragment (business, deontic,")
    print("bridge, preference), concatenated with no cross-edits; the bridges are the only join. That")
    print("additivity is the property the productized version must keep as the fragment count grows.")


if __name__ == "__main__":
    main()
