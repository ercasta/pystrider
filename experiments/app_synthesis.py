"""Feasibility probe — APP SYNTHESIS: synthesize a *runnable Textual app* across three bridged
knowledge domains, trusted because it is DRIVEN (docs/api_absorption_design.md §4b; the synthesis
axis, `experiments/spec_synthesis.py` / `codegen_understand.py`, pointed at an application target).

For the first time the emitted artifact is not a pure `def f(...): return` but a runnable **app** — a
Textual `App`/`Screen` with event handlers — and it fuses THREE vocabularies joined by bridges:

    business (a cash-withdrawal procedure)   read the amount -> validate -> perform -> report
    framework (the Textual API)              Input.value, Button.Pressed, push_screen(ModalScreen)
    UX (a confirmation pattern)              an IRREVERSIBLE action must be gated by a confirm step

Everything but the verifier REUSES what is already built:

  * SELECTION is a grammapy §12 DECISION POINT resolved by cross-cutting constraint (Phase 3): the screen
    productions declare the capabilities they provide, pystrider's reasoning emits one `requires
    confirmation` constraint, and grammapy `resolve` narrows to FORCED / DEFAULTED / SURFACED / REJECTED —
    never a silent pick. (Phase 2a first wired this as a value-guard `Choice`, still a grammapy combinator
    for value-keyed decisions; Phase 3 generalized it to the intensional constraint form.)
  * COMPOSITION of a screen's features is a grammapy `Accumulate` (Phase 1): each button is a
    footprint-declared atom, and `Accumulate.check` (the frame rule) admits the set iff their writes are
    disjoint — rejecting interference (two proceed-buttons) at design time, before any source is emitted.
  * REACHABILITY of the withdrawal effect is a grammapy `Scope` (Phase 2b): the withdrawal EMITS a
    `needs_confirmation` control signal when irreversible, and the confirm screen HANDLES it; `Scope.check`
    (binder-scoped reachability) admits the app iff every emitted signal has a covering handler ancestor —
    so an irreversible withdrawal with no gate is rejected as an escaping effect, however it was selected.
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

import ast
import asyncio
from dataclasses import dataclass, field

import ugm as h
from ugm import load_machine_rules, ask_goal

from grammapy import (Accumulate, Channel, CompositionError, DecisionPoint, Defaulted, Fold, FoldItem,
                      Footprint, Forced, Item, Lattice, Production, Scope, ScopeNode, resolve)


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
    trusted: bool = False         # a trusted session that VOTES to WAIVE the confirmation (a deontic conflict)


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
# Deontic VERDICTS on the confirm act are voted by independent sources (obligation, waiver); a grammapy
# Fold resolves the conflict order-independently under a declared policy (see resolve_confirm below).
_F_DEONTIC = [
    "?spec obliged confirm when ?spec action_irreversible yes",
    "?spec confirm_verdict obligatory when ?spec obliged confirm",     # the irreversibility vote
    "?spec confirm_verdict waived when ?spec trusted yes",             # a trusted session's waiver vote
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
    if spec.trusted:
        facts.append((spec.name, "trusted", "yes"))
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


# --- PHASE 4: AST emission — each production contributes an AST FRAGMENT, grammapy assembles ---
# Rules cannot MINT an app (the existential wall), so the tool still owns emission; but emission is no
# longer a string-concatenating template. Each production (the screen shape, the confirm handler, each
# button) is an `ast` FRAGMENT; `assemble_ast` composes the fragments into one `ast.Module`, unparsed to
# source. This is the structural fix for the candidate cross-product: the module body is BUILT per
# feature (imports + optional ConfirmScreen + WithdrawApp with the chosen handler) rather than selected
# from two whole strings, and the button set composes as AST nodes spliced into `ConfirmScreen.compose`.
#
# The INVARIANT Textual boilerplate that never varies per feature (imports, `_validate`, `_perform`,
# `__init__`, `WithdrawApp.compose`, the two handlers) is authored as canonical, NON-interpolated
# snippets and `ast.parse`d into fragments — real AST, no f-string source-building. Only the genuinely
# per-feature pieces are SYNTHESIZED as AST: the confirm button `yield`s and the affirmative `dismiss`
# comparison. Class names, widget `id`s, and the recorded `events` trace are byte-identical to before,
# so `verify_by_pilot` and its assertions are unchanged; `ast.unparse` normalizes quoting/whitespace.

_IMPORTS_SRC = """\
from textual.app import App, ComposeResult
from textual.widgets import Input, Button
"""
_CONFIRM_IMPORT_SRC = "from textual.screen import ModalScreen"

_WITHDRAW_APP_SRC = '''
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
        try:
            amt = float(raw)
        except ValueError:
            self.events.append("rejected non-numeric")
            return None
        if amt <= 0:
            self.events.append("rejected non-positive")
            return None
        return raw
'''

_HANDLER_DIRECT_SRC = '''
def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id != "ok":
        return
    amount = self._validate(self.query_one("#amount", Input).value)
    if amount is not None:
        self._perform(amount)
'''

_HANDLER_CONFIRM_SRC = '''
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

# The ConfirmScreen shell carries the invariant methods (`on_mount` records `gate_shown`, the
# `on_button_pressed` dismiss shell); `compose`'s body and the dismiss argument are filled per feature.
_CONFIRM_SCREEN_SRC = '''
class ConfirmScreen(ModalScreen):
    """UX confirmation gate for the irreversible withdrawal."""

    def compose(self) -> ComposeResult:
        pass

    def on_mount(self) -> None:
        self.app.events.append("gate_shown")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(False)
'''


def _parse_one(src: str) -> ast.stmt:
    """Parse a single-statement snippet into its AST node (a class/def/import fragment)."""
    return ast.parse(src).body[0]


def _method(cls: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _button_yield(label: str, widget_id: str) -> ast.stmt:
    """AST for `yield Button("<label>", id="<widget_id>")` — one confirm-screen compose fragment."""
    call = ast.Call(func=ast.Name(id="Button", ctx=ast.Load()),
                    args=[ast.Constant(value=label)],
                    keywords=[ast.keyword(arg="id", value=ast.Constant(value=widget_id))])
    return ast.Expr(value=ast.Yield(value=call))


def _affirmative_compare(affirmative: str) -> ast.expr:
    """AST for `event.button.id == "confirm-<affirmative>"` — the proceed test the screen dismisses on."""
    button_id = ast.Attribute(
        value=ast.Attribute(value=ast.Name(id="event", ctx=ast.Load()), attr="button", ctx=ast.Load()),
        attr="id", ctx=ast.Load())
    return ast.Compare(left=button_id, ops=[ast.Eq()],
                       comparators=[ast.Constant(value=f"confirm-{affirmative}")])


def _withdraw_app(handler: ast.FunctionDef) -> ast.ClassDef:
    """The WithdrawApp class fragment with the chosen `on_button_pressed` handler appended as a method."""
    cls = _parse_one(_WITHDRAW_APP_SRC)
    cls.body.append(handler)
    return cls


def _confirm_screen(buttons: list[str], affirmative: str) -> ast.ClassDef:
    """The ConfirmScreen class fragment: splice one `yield Button(...)` per DERIVED button into
    `compose`, and set the dismiss to proceed on the affirmative id. The button set composes as AST
    nodes (the defeasible preference, materialized), not a string join."""
    cls = _parse_one(_CONFIRM_SCREEN_SRC)
    _method(cls, "compose").body = [_button_yield(b.title(), f"confirm-{b}") for b in buttons]
    dismiss_call = _method(cls, "on_button_pressed").body[-1].value   # Expr -> self.dismiss(...) Call
    dismiss_call.args = [_affirmative_compare(affirmative)]
    return cls


def _build_module(spec: Spec, screen: str) -> ast.Module:
    """Assemble the app as an `ast.Module` from per-feature fragments: imports, an optional ConfirmScreen
    (with the composed button set), and WithdrawApp carrying the screen's handler. The compositional
    replacement for two whole-string skeletons."""
    body: list[ast.stmt] = list(ast.parse(_IMPORTS_SRC).body)
    if screen == "confirm_screen":
        body.append(_parse_one(_CONFIRM_IMPORT_SRC))
        body.append(_confirm_screen(_ordered_buttons(spec), _affirmative_of(spec)))
        body.append(_withdraw_app(_parse_one(_HANDLER_CONFIRM_SRC)))
    else:
        body.append(_withdraw_app(_parse_one(_HANDLER_DIRECT_SRC)))
    mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(mod)
    return mod


def assemble_ast(dev: "DeviationSpec") -> ast.Module:
    """Build the emitted module from a RESOLVED deviation spec — the AST-emission seam. Every design-time
    gate (Accumulate/Scope/§12/Fold) already ran in `assemble`; this only materializes the admitted shape."""
    return _build_module(dev.spec, dev.screen)


def _emit_one_screen(spec: Spec) -> str:
    """The compact app: input -> OK -> validate -> withdraw. No confirmation gate. AST-built."""
    return ast.unparse(_build_module(spec, "one_screen"))


def _emit_confirm_screen(spec: Spec) -> str:
    """The gated app: input -> OK -> validate -> push a ModalScreen (with the grammapy-COMPOSED buttons)
    -> proceed/abort -> withdraw. `compose_confirm_screen` is the design-time gate: it raises
    `CompositionError` on a malformed button set, so emission only ever runs on an admitted composition."""
    compose_confirm_screen(spec)      # grammapy Accumulate gate — raises before any AST is produced
    return ast.unparse(_build_module(spec, "confirm_screen"))


# --- PHASE 3: the screen shape as a grammapy DECISION POINT, resolved by cross-cutting constraint (§12) ---
# Phase 2a wired this as a value-guard Choice; Phase 3 GENERALIZES it to the intensional form and unifies
# the reasoning->grammapy interface. The screen is a decision point whose productions declare the
# capabilities they PROVIDE; pystrider's deontic reasoning emits ONE cross-cutting CONSTRAINT (`requires
# confirmation` iff the folded verdict is obligatory — a deviation spec, not four hand-wired combinator
# calls), and grammapy's §12 `resolve` narrows the productions: FORCED where a requirement leaves one,
# DEFAULTED where the spec is silent, SURFACED where ambiguous, REJECTED where unsatisfiable — never a
# silent inferred pick. (The value-guard Choice combinator remains in grammapy for value-keyed decisions.)
SCREEN_POINT = DecisionPoint(
    "screen",
    productions=(
        Production("one_screen", frozenset()),                         # the compact default
        Production("confirm_screen", frozenset({"confirmation"})),     # provides the confirmation capability
    ),
    default="one_screen",
)


# --- PHASE 2c: resolve conflicting deontic verdicts with a grammapy FOLD (declared, order-independent) ---
# The confirm act can draw CONFLICTING deontic votes: irreversibility votes `obligatory`, a trusted
# session votes `waived`, and there is always a `optional` baseline. A grammapy Fold combines them under a
# DECLARED policy (a lattice = the reviewable choice). The safety policy `obligation_overrides` makes an
# obligation beat a waiver — so a trusted session CANNOT silence a safety confirmation — and the fold is
# order-independent, so it does not matter which rule fired first. Flip the lattice and the policy flips.
CONFIRM_SAFETY = Lattice("obligation_overrides", ("waived", "optional", "obligatory"))
CONFIRM_LENIENT = Lattice("waiver_overrides", ("obligatory", "optional", "waived"))


def _confirm_verdicts(spec: Spec) -> list[FoldItem]:
    """The deontic votes on the confirm act, from pystrider's reasoning: a `optional` baseline plus each
    verdict the REFINE bank derives (`obligatory` from irreversibility, `waived` from a trusted session)."""
    g, rules = _refine_graph(spec), load_machine_rules(REFINE)
    items = [FoldItem("baseline", "optional")]
    for source, verdict in (("irreversibility", "obligatory"), ("trusted_session", "waived")):
        if ask_goal(g, f"is {spec.name} confirm_verdict {verdict}", rules) == ["yes"]:
            items.append(FoldItem(source, verdict))
    return items


def resolve_confirm(spec: Spec, policy: Lattice = CONFIRM_SAFETY) -> str:
    """Resolve the conflicting deontic verdicts into one via the grammapy Fold under `policy` (default:
    safety — obligation overrides waiver). Order-independent by construction of the lattice."""
    verdicts = _confirm_verdicts(spec)
    Fold.check(policy, verdicts)               # every verdict must be in the lattice domain
    return Fold.combine(policy, verdicts)


def required_capabilities(spec: Spec) -> frozenset:
    """The cross-cutting CONSTRAINT pystrider's reasoning addresses to the app's decision points: the app
    `requires confirmation` iff the FOLDED deontic verdict is obligatory (under the safety policy). One
    constraint set — the intensional deviation spec — instead of a per-combinator imperative call."""
    return frozenset({"confirmation"}) if resolve_confirm(spec) == "obligatory" else frozenset()


def resolve_screen(spec: Spec):
    """Resolve the screen decision point against the reasoning's constraint via grammapy §12 —
    Forced / Defaulted / Surfaced / Rejected."""
    return resolve(SCREEN_POINT, required_capabilities(spec))


def choose_screen(spec: Spec) -> str:
    """The app's screen shape from the §12 resolution. For the base app the resolution is always Forced
    (a confirmation requirement narrows to the confirm screen) or Defaulted (silent -> compact); a
    Surfaced or Rejected resolution is a non-determinate app and raises (shown in the walkthrough)."""
    r = resolve_screen(spec)
    if isinstance(r, (Forced, Defaulted)):
        return r.production
    raise CompositionError("screen", [r], reason="the screen decision did not resolve to one production")


# --- PHASE 2b: the confirmation gate as a grammapy SCOPE (reachability of the withdrawal effect) ------
# The confirmation is not just a selected feature — it is a HANDLER. Model the withdrawal as a leaf that
# EMITS the control signal `needs_confirmation` when the action is irreversible; the confirm screen is a
# handler that HANDLES it over its sub-tree. `Scope.check` (binder-scoped reachability) admits the app iff
# every emitted signal has a covering handler ANCESTOR — so an irreversible withdrawal with no confirm
# gate is rejected at design time (the effect escapes), independently of how the screen was chosen. This
# is the tacit human rule "no destructive effect goes unconfirmed", made a structural, checkable property.
CONFIRM_SIGNAL = "needs_confirmation"


def app_scope_tree(spec: Spec, screen: str) -> ScopeNode:
    """The app's control tree: the withdrawal leaf EMITS `needs_confirmation` iff irreversible; the
    confirm screen (when present) HANDLES it over its sub-tree. The structure `Scope.check` reasons over."""
    perform = ScopeNode.of("perform_withdrawal",
                           emits=[CONFIRM_SIGNAL] if spec.irreversible else [])
    if screen == "confirm_screen":
        gate = ScopeNode.of("confirm_screen", handles=[CONFIRM_SIGNAL], children=[perform])
        return ScopeNode.of("WithdrawApp", children=[gate])
    return ScopeNode.of("WithdrawApp", children=[perform])


def check_reachability(spec: Spec, screen: str) -> None:
    """grammapy Scope gate: raise `CompositionError` unless every control effect the app emits has a
    covering handler — the irreversible withdrawal's `needs_confirmation` must be gated by a confirm
    handler. Certifies the STRUCTURE handles the effect, independently of the Choice that selected it."""
    Scope.check(app_scope_tree(spec, screen))


# --- VERIFY by DRIVING the app (the feasibility crux — concrete-exec scaled to a UI) -----------

@dataclass
class VerifyResult:
    """What DRIVING the emitted app OBSERVED, under TWO independent contracts (Phase 0 hardening):

    * `ok` — the SAFETY contract on the driven path: an irreversible action never performs WITHOUT a
      prior gate (`¬irreversible ∨ ¬performed ∨ gated`). An aborted run is still safe: it did not
      perform. `performed`/`gated` are the observations this verdict reads.
    * `live` — the LIVENESS contract: driving the HAPPY path (pressing the affirmative/proceed button)
      the withdrawal actually COMPLETES. Safety alone is vacuously satisfied by a dead app that never
      performs — a confirm screen with no proceed button passes `ok` while withdrawing nothing — so
      liveness is what makes "it works" a checked property, not an assumption.

    A trustworthy app needs BOTH: `ok` (never does the wrong thing) AND `live` (does the right thing)."""
    events: list[str]
    performed: bool
    gated: bool
    ok: bool
    live: bool


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


def _run_events(source: str, choice: str) -> list[str]:
    """Exec the emitted app source and DRIVE it once (pressing `choice` at any gate), returning the
    observed event trace. Safe: our own pre-minted, self-contained app source."""
    ns: dict[str, object] = {}
    exec(compile(source, "<emitted-app>", "exec"), ns)
    app = ns["WithdrawApp"]()
    asyncio.run(_drive(app, choice))
    return list(app.events)


def verify_by_pilot(source: str, spec: Spec, confirm_choice: str = "ok") -> VerifyResult:
    """RUN the emitted app under Textual's headless Pilot and OBSERVE its event trace — trust by
    execution, never by the skeleton's `provides` claim. Drive the gate with `confirm_choice` (`ok`
    proceeds, `cancel` aborts). Reports BOTH contracts (see `VerifyResult`): `ok` (SAFETY — for an
    irreversible action, any withdrawal was gated) and `live` (LIVENESS — driving the HAPPY path, the
    affirmative/proceed button, the withdrawal COMPLETES). Liveness is measured on its own affirmative
    drive so it is meaningful even when the caller drives an abort path (`confirm_choice='cancel'`)."""
    events = _run_events(source, confirm_choice)
    withdrawn_at = next((i for i, e in enumerate(events) if e.startswith("withdrawn")), None)
    performed = withdrawn_at is not None
    gated = "gate_shown" in events and (withdrawn_at is None or events.index("gate_shown") < withdrawn_at)
    ok = (not spec.irreversible) or (not performed) or gated     # irreversible => performing requires a gate

    # LIVENESS — drive the HAPPY path (press the affirmative proceed button) and require completion. A
    # dead confirm screen with no proceed button never withdraws, so this rejects it where safety cannot.
    affirmative = _affirmative_of(spec)
    if confirm_choice == affirmative:
        live = performed                                          # this drive already IS the happy path
    else:
        live = any(e.startswith("withdrawn") for e in _run_events(source, affirmative))
    return VerifyResult(events=events, performed=performed, gated=gated, ok=ok, live=live)


# --- PHASE 3 (finish): ONE deviation spec — the app as its resolved decision points ------------
# The four decision points no longer have four scattered call sites. `assemble` resolves them all in one
# place, each by its grammapy combinator, into one uniform record: policy (Fold), screen (§12 resolve),
# buttons (Accumulate), effect-handling (Scope). This IS the deviation spec — the single reasoning->
# grammapy artifact — and it is `admitted` iff every point resolved cleanly.

@dataclass
class Decision:
    """One decision point's resolved outcome, uniformly: the combinator that resolved it, the chosen
    value, a human-readable detail, and whether grammapy admitted it (else the rejection message)."""
    point: str
    combinator: str
    value: str
    detail: str
    admitted: bool
    error: str | None = None


@dataclass
class DeviationSpec:
    """The app as its resolved decision points — the single reasoning->grammapy artifact. `screen` is the
    emitted shape (None if the screen did not resolve determinately); `admitted` iff every point is clean."""
    spec: Spec
    decisions: list[Decision]
    screen: str | None

    @property
    def admitted(self) -> bool:
        return all(d.admitted for d in self.decisions)

    @property
    def rejection(self) -> str | None:
        return next((d.error for d in self.decisions if not d.admitted), None)


def assemble(spec: Spec) -> DeviationSpec:
    """Resolve every decision point through its grammapy combinator, into one deviation spec. Short-
    circuits the downstream points if the screen does not resolve determinately (nothing to build)."""
    decisions: list[Decision] = []

    verdict = resolve_confirm(spec)                                   # 1. deontic policy — grammapy Fold
    decisions.append(Decision("confirm_policy", "Fold", verdict,
                              f"votes {[it.value for it in _confirm_verdicts(spec)]} -> {verdict}", True))

    res = resolve_screen(spec)                                        # 2. screen — grammapy §12 resolve
    screen = res.production if isinstance(res, (Forced, Defaulted)) else None
    decisions.append(Decision("screen", "resolve", screen or "unresolved", str(res),
                              screen is not None, None if screen else str(res)))
    if screen is None:
        return DeviationSpec(spec, decisions, None)

    if screen == "confirm_screen":                                   # 3. buttons — grammapy Accumulate
        try:
            atoms = compose_confirm_screen(spec)
            decisions.append(Decision("confirm_buttons", "Accumulate", ",".join(_ordered_buttons(spec)),
                                      f"{len(atoms)} atoms, writes disjoint", True))
        except CompositionError as e:
            decisions.append(Decision("confirm_buttons", "Accumulate", "rejected", str(e), False, str(e)))

    try:                                                             # 4. effect handling — grammapy Scope
        check_reachability(spec, screen)
        decisions.append(Decision("effect_handling", "Scope", "reachable",
                                  f"{CONFIRM_SIGNAL} handled" if spec.irreversible else "no effect", True))
    except CompositionError as e:
        decisions.append(Decision("effect_handling", "Scope", "rejected", str(e), False, str(e)))

    return DeviationSpec(spec, decisions, screen)


# --- the whole synthesis loop -----------------------------------------------------------------

@dataclass
class Synthesis:
    spec: Spec
    required: set[str]
    screen: str                          # the screen shape the §12 resolution selected (the winner)
    source: str
    verify: VerifyResult | None
    composed: bool                       # grammapy admitted every decision point in the deviation spec
    composition_error: str | None        # the first design-time rejection message, if any point failed
    deviation: DeviationSpec

    @property
    def winner(self) -> str:
        return self.screen


def synthesize(spec: Spec) -> Synthesis:
    """spec -> DERIVE required features -> ASSEMBLE the deviation spec (resolve every decision point
    through its grammapy combinator: Fold / §12-resolve / Accumulate / Scope) -> EMIT real Textual source
    iff every point was admitted -> VERIFY by DRIVING it. pystrider reasons what deviates; grammapy's
    sound-composition algebra resolves and gates every point in one place; one repo."""
    required = required_features(spec)
    dev = assemble(spec)
    if dev.admitted and dev.screen:
        source, composed, comp_err = ast.unparse(assemble_ast(dev)), True, None
    else:
        source, composed, comp_err = "", False, dev.rejection
    vr = verify_by_pilot(source, spec) if source else None
    return Synthesis(spec=spec, required=required, screen=dev.screen or "unresolved", source=source,
                     verify=vr, composed=composed, composition_error=comp_err, deviation=dev)


# --- live walkthrough -------------------------------------------------------------------------

def _show(spec: Spec) -> None:
    r = synthesize(spec)
    flag = "IRREVERSIBLE (UX demands a confirm step)" if spec.irreversible else "lenient (compact allowed)"
    print(f"=== spec: {spec.procedure} app - {flag} ===")
    print(f"  refine (business -> deontic -> framework) -> required features: {sorted(r.required) or '[]'}")
    print(f"  resolve -> requires {set(required_capabilities(spec)) or '{}'} -> {resolve_screen(spec)}")
    vr = r.verify
    print(f"  drive  -> events: {vr.events}")
    print(f"           performed={vr.performed}  gated={vr.gated}  "
          f"=> {'SPEC HOLDS' if vr.ok else 'SPEC VIOLATED'}\n")


def main() -> None:
    print("APP SYNTHESIS - a runnable Textual app across three bridged domains, verified by DRIVING\n")

    print("PART 1 - the winner-flip under one UX fact\n")
    _show(Spec(name="withdraw_spec"))                       # lenient: compact one-screen wins
    _show(Spec(name="withdraw_spec", irreversible=True))    # irreversible: the FLIP -> confirm-screen

    print("Why the flip: the screen is a grammapy exclusive-Choice whose guards partition {required,\n"
          "absent}. pystrider's deontic reasoning sets the `confirmation` state: silent -> absent (the\n"
          "default branch, one_screen); `withdrawal is_irreversible` -> `obliged confirm` -> required ->\n"
          "the confirm_screen branch fires. Determinacy, not a graded pick - exactly one branch, proven.\n")

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

    print("\nPART 5 - grammapy SCOPE: the withdrawal EFFECT must be handled (reachability)\n")
    strict = Spec(name="withdraw_spec", irreversible=True)
    print(f"  irreversible withdrawal EMITS the control signal {CONFIRM_SIGNAL!r}.")
    print(f"  chosen structure (confirm_screen handles it):")
    check_reachability(strict, "confirm_screen")
    print(f"      Scope.check -> admitted (the effect has a covering handler ancestor)\n")
    print(f"  force the ONE-screen structure on the SAME irreversible spec (a mis-built app):")
    try:
        check_reachability(strict, "one_screen")
    except CompositionError as e:
        for line in str(e).splitlines():
            print(f"      {line}")
    print("\n  Scope catches the escaping effect INDEPENDENTLY of the Choice that selected the screen -")
    print("  the tacit human rule 'no destructive action goes unconfirmed', made a structural guarantee.")

    print("\nPART 6 - grammapy FOLD: resolve conflicting deontic verdicts by a DECLARED policy\n")
    conflict = Spec(name="withdraw_spec", irreversible=True, trusted=True)
    print(f"  irreversible + trusted session -> conflicting votes on `confirm`:")
    print(f"      {[(it.label, it.value) for it in _confirm_verdicts(conflict)]}")
    print(f"  fold under SAFETY policy {CONFIRM_SAFETY.order}:")
    print(f"      -> {resolve_confirm(conflict, CONFIRM_SAFETY)}  (obligation overrides the waiver: a trusted")
    print(f"         session CANNOT silence a safety confirmation) -> screen: {choose_screen(conflict)}")
    print(f"  fold under LENIENT policy {CONFIRM_LENIENT.order}:")
    print(f"      -> {resolve_confirm(conflict, CONFIRM_LENIENT)}  (same votes, a different DECLARED policy -> the waiver wins)")
    print("\n  The fold is order-independent (the semilattice law), so it does not matter which rule voted")
    print("  first; and WHICH verdict wins is a reviewable DECLARATION (the lattice), never inferred.")

    print("\nPART 7 - grammapy constraint resolution: reasoning emits ONE constraint; the point resolves it\n")
    print(f"  screen decision point: productions {[p.label for p in SCREEN_POINT.productions]}, "
          f"default {SCREEN_POINT.default!r}")
    for label, spec in [("reversible", Spec(name="s")),
                        ("irreversible", Spec(name="s", irreversible=True))]:
        req = required_capabilities(spec)
        print(f"    reasoning `requires {set(req) or '{}'}` ({label}) -> {resolve_screen(spec)}")
    print(f"  a requirement no production provides (`biometric`) -> {resolve(SCREEN_POINT, ['biometric'])}")
    ambiguous = DecisionPoint("screen2", (
        Production("confirm_modal", frozenset({"confirmation"})),
        Production("confirm_inline", frozenset({"confirmation"}))), default="confirm_modal")
    print(f"  two productions both providing `confirmation`, no preference ->\n      "
          f"{resolve(ambiguous, ['confirmation'])}")
    print("\n  Forced where unique, defaulted where silent, surfaced where ambiguous, rejected where")
    print("  unsatisfiable - never an inferred pick. The reasoning emits ONE constraint set (a deviation")
    print("  spec); the four combinators consume it, replacing four hand-wired call sites.")

    print("\n  the whole app as ONE deviation spec (each point resolved by its grammapy combinator):")
    dev = assemble(Spec(name="withdraw_spec", irreversible=True))
    for d in dev.decisions:
        print(f"      {d.point:<16} [{d.combinator:<10}] {d.value:<14} - {d.detail}")
    print(f"      => admitted: {dev.admitted}")

    print("\nCOMPOSITION - every line above came from a SEPARATE knowledge fragment (business, deontic,")
    print("bridge, preference), and the feature set is admitted by grammapy's proven combinators, not")
    print("ad-hoc glue. That additivity is the property productization must keep as fragments grow.")


if __name__ == "__main__":
    main()
