"""Feasibility probe — the EXTERNAL GENERATOR FRONT-END (grammapy convergence, Phase 5 steps 5–6).

This closes the north-star loop (docs/grammapy_convergence.md). The front of the loop was, until now,
a hand-authored `Spec` fed to pystrider's reasoning. Steps 5–6 put an **external generator** there: an
untrusted front-end that DRAFTS a candidate app design straight from intent — "compose by pattern, skip
the math" — the role a real LLM plays. The bet of the whole convergence is that such a generator can be
*arbitrarily unreliable* and still yield trustworthy software, because every class of mistake it can make
is caught by a specific downstream GATE it does not control:

    intent ─▶ GENERATOR drafts a design ─▶ ┌─ GATE 1  pystrider REASONING  (the derived OBLIGATION)
              (pattern-match, no proof)     ├─ GATE 2  grammapy SCOPE       (no effect escapes)
                                            ├─ GATE 3  grammapy ACCUMULATE  (features don't interfere)
                                            └─ GATE 4  pystrider PILOT      (it actually behaves)
                                                          │
                                       reject ────────────┤ (with the offending gate named)
                                          │               └──▶ accept: emit (AST) + drive green
                                          ▼
                                 REPAIR via pystrider reasoning (assemble) ─▶ re-gate ─▶ accept

The generator PROPOSES; the algebra and the Pilot DISPOSE. Three scripted generators stand in for the
LLM (the front-end is a pluggable `Callable[[Spec], Draft]`; a real model slots in unchanged, gated
identically — the probe validates the GATING CONTRACT, which is provider-agnostic):

  * `sound_generator`   — applies the obligation correctly. Passes every gate, drives green.
  * `lazy_generator`    — pattern-matches "it's just a form" and always proposes the compact one-screen,
                          ignoring irreversibility. Caught at GATE 1 (obligation) — and GATE 2 (Scope)
                          independently, the belt-and-suspenders the two trusted layers give.
  * `sloppy_generator`  — knows a confirm gate is needed but drafts a broken button set (two proceed
                          buttons). Passes 1–2, caught at GATE 3 (Accumulate's frame rule).

And a rejected draft is not the end: `repair` runs pystrider's OWN reasoning (`assemble`) to derive the
sound design, which re-gates clean and drives — the loop's self-correcting back-edge. So an unreliable
front-end + trustworthy gates = trustworthy output, which is the productization thesis made runnable.

Run it: `python -m experiments.generator_frontend`  (requires `textual`).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field, replace
from typing import Callable

from grammapy import Accumulate, CompositionError

from experiments.app_synthesis import (
    Spec, required_capabilities, check_reachability, _build_module, verify_by_pilot,
    _button_atom, assemble, CONFIRM_SIGNAL, _ordered_buttons, _affirmative_of,
)


# --- the intent and the generator's draft ------------------------------------------------------

def parse_intent(text: str) -> Spec:
    """Extract the DOMAIN FACTS from an NL intent — what the app is, and whether the action is
    irreversible (the one business fact that carries a deontic obligation). A keyword scan stands in
    for real parsing; the point of the probe is the GATING of the draft, not the NLP."""
    t = text.lower()
    irreversible = "irreversible" in t or "cannot be undone" in t or "permanent" in t
    return Spec(name="gen_spec", procedure="withdrawal", irreversible=irreversible)


@dataclass(frozen=True)
class Draft:
    """What the external generator PROPOSES: a candidate app design (screen shape + confirm button set)
    drafted by pattern-matching the intent, WITHOUT running the deontic reasoning. `spec` carries the
    domain facts the draft was made from; the gates decide whether the proposal is sound."""
    spec: Spec
    screen: str                       # proposed shape: "one_screen" | "confirm_screen"
    buttons: tuple[str, ...] = ()      # proposed confirm button set (for a confirm_screen)


Generator = Callable[[Spec], Draft]


def sound_generator(spec: Spec) -> Draft:
    """A competent front-end: applies the obligation — an irreversible action gets a confirm gate."""
    if spec.irreversible:
        return Draft(spec, "confirm_screen", ("ok", "cancel"))
    return Draft(spec, "one_screen")


def lazy_generator(spec: Spec) -> Draft:
    """A front-end that pattern-matches 'it's a form' and always drafts the compact one-screen —
    the classic feature-interaction miss: it never applies the irreversibility obligation."""
    return Draft(spec, "one_screen")


def sloppy_generator(spec: Spec) -> Draft:
    """A front-end that gets the gate right but drafts a BROKEN button set — two affirmative (proceed)
    buttons, which collide on the shared submit action. The kind of composition a pattern-matcher misses."""
    if spec.irreversible:
        return Draft(spec, "confirm_screen", ("ok", "yes"))
    return Draft(spec, "one_screen")


def sterile_generator(spec: Spec) -> Draft:
    """A front-end that drafts a confirm screen with NO proceed button (`cancel`, `back` only) — a
    DEAD app: it gates, but the happy path can never complete. It slips past the obligation (a confirm
    screen is present), Scope (the effect is handled), and Accumulate (the writes are disjoint) — and
    is caught ONLY by the Pilot's LIVENESS contract, the gate the safety-only oracle could never fire."""
    if spec.irreversible:
        return Draft(spec, "confirm_screen", ("cancel", "back"))
    return Draft(spec, "one_screen")


# --- the gates: pystrider reasoning + grammapy algebra + the Pilot oracle -----------------------

@dataclass
class GateResult:
    """The verdict on a draft. `accepted` iff it survived every gate; `gate`/`reason` name the one that
    rejected it (or the emission+drive that accepted it). `source`/`verify` are set only on acceptance."""
    accepted: bool
    gate: str
    reason: str
    source: str = ""
    verify: object = None


def _emit_spec(draft: Draft) -> Spec:
    """The spec to EMIT from: the domain facts plus the draft's proposed button set (so a confirm screen
    materializes exactly the buttons the generator drafted)."""
    return replace(draft.spec, buttons=draft.buttons or None)


def gate(draft: Draft) -> GateResult:
    """Run the untrusted draft through the four trusted gates, in order. Design-time first (cheap,
    catches whole classes before any code is emitted), then execution (the Pilot). The first gate to
    reject stops the pipeline and names itself; surviving all four emits and drives the app."""
    spec = draft.spec
    emit_spec = _emit_spec(draft)      # the spec that actually SHIPS (preference-resolved button set)
    # the button set that will really be in the emitted screen — gate THIS, not the raw draft, so no
    # gate ever certifies an artifact other than the one emitted (Phase 0: draft-vs-artifact hole).
    emitted_buttons = _ordered_buttons(emit_spec) if draft.screen == "confirm_screen" else []

    # GATE 1 — pystrider REASONING: does the draft satisfy the derived OBLIGATION? (the `re-derive` edge)
    required = set(required_capabilities(spec))
    provides = {"confirmation"} if draft.screen == "confirm_screen" else set()
    missing = required - provides
    if missing:
        return GateResult(False, "reasoning/obligation",
                          f"the derived obligation requires {required}, but the draft "
                          f"({draft.screen}) provides {provides or '{}'} — missing {missing}")

    # GATE 2 — grammapy SCOPE: does the proposed STRUCTURE handle every emitted control effect?
    try:
        check_reachability(spec, draft.screen)
    except CompositionError as e:
        return GateResult(False, "grammapy/Scope", str(e).splitlines()[0])

    # GATE 3 — grammapy ACCUMULATE: does the EMITTED confirm button set compose (disjoint writes)?
    if draft.screen == "confirm_screen":
        try:
            Accumulate.check([_button_atom(b) for b in emitted_buttons])
        except CompositionError as e:
            return GateResult(False, "grammapy/Accumulate", str(e).splitlines()[0])

    # PASSED design-time — grammapy guarantees composition. EMIT (AST) and DRIVE (GATE 4, the oracle).
    # Drive the EMITTED artifact along the HAPPY path (the affirmative button): the Pilot must attest
    # BOTH the SAFETY contract (`ok`) and the LIVENESS contract (`live` — the app actually completes).
    source = ast.unparse(_build_module(emit_spec, draft.screen))
    vr = verify_by_pilot(source, emit_spec, confirm_choice=_affirmative_of(emit_spec))
    if not vr.ok:
        return GateResult(False, "pystrider/Pilot",
                          f"driving violated the UX contract (events={vr.events})", source, vr)
    if not vr.live:
        return GateResult(False, "pystrider/Pilot-liveness",
                          f"the happy path never completed — a dead app: driving the proceed button "
                          f"withdrew nothing (events={vr.events})", source, vr)
    return GateResult(True, "accepted", f"survived every gate; driven green (events={vr.events})", source, vr)


def repair(draft: Draft) -> Draft:
    """The loop's self-correcting back-edge: when a draft is rejected, fall back to pystrider's OWN
    reasoning (`assemble`) to derive the SOUND design, and hand that back as a repaired draft. This is
    the generator being corrected by the reasoning it skipped — 'the generator proposes, the Pilot
    disposes', and when it disposes, the reasoning re-proposes."""
    dev = assemble(draft.spec)
    buttons = ("ok", "cancel") if dev.screen == "confirm_screen" else ()
    return Draft(draft.spec, dev.screen or "one_screen", buttons)


@dataclass
class Outcome:
    intent: str
    generator: str
    draft: Draft
    first: GateResult
    repaired: Draft | None = None
    final: GateResult | None = None

    @property
    def trustworthy(self) -> bool:
        """The app that actually ships — the accepted draft, after repair if the first was rejected."""
        return (self.final or self.first).accepted


def run(intent: str, generator: Generator) -> Outcome:
    """The whole front-end loop: parse intent -> generator drafts -> gate -> (repair via reasoning ->
    re-gate) -> the trustworthy app. An unreliable proposer + trusted gates = trustworthy output."""
    spec = parse_intent(intent)
    draft = generator(spec)
    first = gate(draft)
    if first.accepted:
        return Outcome(intent, generator.__name__, draft, first)
    repaired = repair(draft)
    return Outcome(intent, generator.__name__, draft, first, repaired, gate(repaired))


# --- live walkthrough -------------------------------------------------------------------------

def _show(intent: str, generator: Generator) -> None:
    o = run(intent, generator)
    print(f"  intent {intent!r}  +  {o.generator}")
    print(f"     draft: screen={o.draft.screen} buttons={o.draft.buttons or '()'}")
    if o.first.accepted:
        print(f"     GATE -> ACCEPTED [{o.first.gate}] {o.first.reason}")
    else:
        print(f"     GATE -> REJECTED [{o.first.gate}] {o.first.reason}")
        print(f"     REPAIR (pystrider reasoning) -> screen={o.repaired.screen} buttons={o.repaired.buttons or '()'}")
        tag = "ACCEPTED" if o.final.accepted else "STILL REJECTED"
        print(f"     re-GATE -> {tag} [{o.final.gate}] {o.final.reason}")
    print(f"     => trustworthy app shipped: {o.trustworthy}\n")


def main() -> None:
    print("EXTERNAL GENERATOR FRONT-END — an untrusted drafter, gated by the algebra + the Pilot oracle\n")
    irreversible = "a cash withdrawal app; the withdrawal is irreversible"
    lenient = "a cash withdrawal app"

    print("PART 1 — a SOUND generator on an irreversible intent: passes every gate\n")
    _show(irreversible, sound_generator)

    print("PART 2 — a LAZY generator (ignores the obligation): caught, then repaired by reasoning\n")
    _show(irreversible, lazy_generator)

    print("PART 3 — a SLOPPY generator (broken button set): caught by grammapy's frame rule, then repaired\n")
    _show(irreversible, sloppy_generator)

    print("PART 4 — a STERILE generator (gates, but no proceed button): a DEAD app, caught by LIVENESS\n")
    _show(irreversible, sterile_generator)

    print("PART 5 — a lenient intent: the compact app is correct, and every generator that drafts it passes\n")
    _show(lenient, sound_generator)

    print("The front-end can be arbitrarily unreliable; each mistake it can make maps to a gate it does")
    print("not control — the derived OBLIGATION, grammapy's SCOPE and ACCUMULATE (now CNL rule-modules),")
    print("and the Pilot's SAFETY and LIVENESS contracts. A rejection re-derives the sound design from")
    print("reasoning. Unreliable proposer + trusted disposers = trustworthy software, made runnable.")


if __name__ == "__main__":
    main()
