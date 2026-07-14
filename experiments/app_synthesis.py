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
from grammapy import Accumulate, Channel, CompositionError, Footprint, Item


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


# --- PHASE 1: compose the confirmation screen through grammapy's Accumulate (footprint disjointness) ---
# The defeasible preference (above) decides WHICH buttons; grammapy decides whether that set COMPOSES
# without interference — the seam between pystrider's reasoning and grammapy's sound-composition algebra,
# now that grammapy is in-repo. Each button is a footprint-declared ATOM: it writes its own widget slot
# `confirm.button.<id>`, and an AFFIRMATIVE button additionally binds the shared PROCEED action
# `confirm.submit`. The screen is an `Accumulate` of these atoms; `Accumulate.check` (the frame rule,
# `disjoint_writes`) admits the set iff the writes are pairwise disjoint — so it REJECTS, at design time,
# a button set with two proceed-buttons (both claiming `confirm.submit`) instead of emitting an
# ambiguous screen. This is the additive, interaction-safe property the scaling thesis rests on, on a
# real second domain, using grammapy code that already exists and is tested.
AFFIRMATIVE = frozenset({"ok", "yes", "proceed", "confirm"})   # buttons that bind the proceed action


def _button_atom(b: str) -> Item:
    """One confirmation button as a grammapy atom: it writes its own widget slot, and — if it is an
    affirmative (proceed) button — the shared `confirm.submit` action slot, of which exactly one is
    well-formed. `label` is what a rejection message shows the user."""
    writes = [Channel(f"confirm.button.{b}")]
    if b in AFFIRMATIVE:
        writes.append(Channel("confirm.submit"))
    return Item(label=f"button {b}", footprint=Footprint.of(writes=writes))


def compose_confirm_screen(spec: Spec) -> list[Item]:
    """Compose the derived button set through grammapy: build one atom per button and run
    `Accumulate.check`. Raises `CompositionError` (naming the shared channel + both buttons) if two
    buttons collide on a write slot — the design-time non-interference gate. Returns the checked atoms."""
    items = [_button_atom(b) for b in _ordered_buttons(spec)]
    Accumulate.check(items)          # the frame rule: admit iff writes are pairwise disjoint
    return items


def _affirmative_of(spec: Spec) -> str:
    """The single proceed-button of a COMPOSED (checked) button set — the id the emitted screen
    dismisses `True` on. Defaults to `ok` when the set names no affirmative (a degenerate confirm)."""
    return next((b for b in _ordered_buttons(spec) if b in AFFIRMATIVE), "ok")


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

def _confirm_screen_block(buttons: list[str], affirmative: str) -> str:
    """Emit the confirmation ModalScreen with exactly the DERIVED buttons (the defeasible preference,
    materialized). The affirmative button — the single proceed atom grammapy admitted — dismisses
    `True`; any other dismisses as abort, so one `dismiss` line handles any admitted button subset."""
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
        f'        self.dismiss(event.button.id == "confirm-{affirmative}")\n'
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
    """The gated app: input -> OK -> validate -> push a ModalScreen (with the grammapy-COMPOSED buttons)
    -> proceed/abort -> withdraw. `compose_confirm_screen` is the design-time gate: it raises
    `CompositionError` on a malformed button set, so emission only ever runs on an admitted composition."""
    compose_confirm_screen(spec)      # grammapy Accumulate gate — raises before any source is produced
    return (_APP_HEADER + "\n" + _confirm_screen_block(_ordered_buttons(spec), _affirmative_of(spec))
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
    composed: bool                       # grammapy admitted the feature composition (Accumulate check)
    composition_error: str | None        # the design-time rejection message, if it did not
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def winner(self) -> str | None:
        return self.selection.winner


def synthesize(spec: Spec) -> Synthesis:
    """spec -> DERIVE required features -> SELECT the realizing graded-best app (`emit.select`) ->
    COMPOSE its features through grammapy (Accumulate: reject interfering sets at design time) ->
    EMIT real Textual source -> VERIFY by DRIVING it. The synthesis loop with pystrider reasoning as
    the front-end and grammapy's sound-composition algebra as the emit gate, one repo."""
    required = required_features(spec)
    sel = select(spec.name, required, CANDIDATES)
    try:
        source = sel.winner_candidate.emit(spec) if sel.winner_candidate else ""
        composed, comp_err = True, None
    except CompositionError as e:                 # grammapy refused the composition -> no source emitted
        source, composed, comp_err = "", False, str(e)
    vr = verify_by_pilot(source, spec) if source else None
    return Synthesis(spec=spec, required=required, selection=sel, source=source, verify=vr,
                     composed=composed, composition_error=comp_err, candidates=CANDIDATES)


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

    print("\nPART 4 - grammapy composes the feature set, and REJECTS interference at design time\n")
    ok = synthesize(Spec(name="withdraw_spec", irreversible=True))
    print(f"  default confirm set {_ordered_buttons(ok.spec)} -> grammapy Accumulate: composed={ok.composed}"
          f"  (writes {sorted(str(c) for it in compose_confirm_screen(ok.spec) for c in it.footprint.writes)})")
    print(f"      -> emitted + driven: performed={ok.verify.performed}  ok={ok.verify.ok}\n")

    bad = synthesize(Spec(name="withdraw_spec", irreversible=True, buttons=("ok", "yes")))
    print(f"  malformed set {_ordered_buttons(bad.spec)} -> two proceed-buttons both bind `confirm.submit`:")
    print(f"      grammapy Accumulate: composed={bad.composed}  (NO source emitted, NO app driven)")
    for line in (bad.composition_error or "").splitlines():
        print(f"        {line}")
    print("\n  This is the seam: pystrider's preference decides WHICH buttons; grammapy's frame rule")
    print("  (disjoint_writes) admits the set only if they compose - rejecting a broken screen BEFORE")
    print("  emission, naming the shared channel and both features, instead of a silent runtime bug.")

    print("\nCOMPOSITION - every line above came from a SEPARATE knowledge fragment (business, deontic,")
    print("bridge, preference), and the feature set is admitted by grammapy's proven Accumulate, not")
    print("ad-hoc glue. That additivity is the property productization must keep as fragments grow.")


if __name__ == "__main__":
    main()
