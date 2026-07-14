"""Feasibility probe — RE-DERIVATION DIFF: a policy change re-derives the code, WITH the derivation of why.

`docs/roadmap.md` Phase 3 (the generation wedge, mode-1 derivational spec->code): *"change one spec
sentence, re-derive, and present what changed in the code with the derivation of why — the 'policy
change -> verified code change' artifact, which no LLM regeneration can produce."* This is the piece that
makes deterministic generation legible as a PRODUCT: an LLM asked to regenerate an app from a changed
prompt gives you a fresh blob and a shrug; a KB-derived generator gives you the exact source delta AND a
proof that ties each changed line back to the spec sentence and the obligation it fired.

The move reuses the whole app-synthesis loop (`experiments/app_synthesis.py`) unchanged: `synthesize`
already turns a spec into a resolved `DeviationSpec` (every decision point resolved by its grammapy
combinator) + emitted source + a Pilot-verified app. Re-derivation is just running it on the BEFORE and
AFTER spec and diffing three things in lockstep:

  1. the SPEC delta      — which succinct sentence changed (here: `irreversible` False -> True);
  2. the DECISION delta   — which resolved decision points moved, and to what (screen, buttons, policy,
                            effect-handling), each still forced/defaulted/surfaced, never guessed;
  3. the SOURCE delta     — the unified diff of the emitted code, every changed line traceable to (2).

And the differentiator over a text diff: each changed decision carries its WHY — the RECORD derivation
that explains it (the screen flipped to `confirm_screen` *because* `withdrawal is_irreversible` fired the
deontic obligation, reached the framework through the bridge). Both the before and after apps are driven
green by the Pilot, so it is a *verified* code change, not just a re-emission.

Run it: `python -m experiments.rederivation`  (requires `textual`).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from experiments.app_synthesis import (
    Spec, Synthesis, Decision, synthesize,
    requirement_trace, confirm_button_trace, _ordered_buttons,
)


# --- the spec delta: which succinct sentence changed -------------------------------------------

_SPEC_FIELDS = ("procedure", "irreversible", "buttons", "trusted")


def _spec_changes(before: Spec, after: Spec) -> list[str]:
    """The human-readable diff of the succinct spec — which business sentence(s) changed. The spec is
    terse (it states only what differs from the defaults), so this delta is usually a single line."""
    out: list[str] = []
    for f in _SPEC_FIELDS:
        b, a = getattr(before, f), getattr(after, f)
        if b != a:
            out.append(f"{f}: {b!r} -> {a!r}")
    return out


# --- the decision delta: which resolved decision points moved, and WHY -------------------------

@dataclass
class DecisionChange:
    """One decision point that resolved differently after the spec change: its before/after values and
    the WHY — the derivation that explains the after-state (the artifact a text diff cannot give)."""
    point: str
    before: str
    after: str
    why: list[str] = field(default_factory=list)


def _why_after(point: str, after: Spec, decision: Decision | None) -> list[str]:
    """The RECORD derivation explaining a changed decision's AFTER-state. The screen and button changes
    render their real provenance trace (business -> deontic -> framework bridge); the rest cite the
    decision's own detail (the combinator's resolution summary)."""
    if decision is None:
        return ["(decision no longer present)"]
    if point == "screen" and decision.value == "confirm_screen":
        return requirement_trace(after, "confirmation_step")           # why confirmation became required
    if point == "confirm_buttons":
        lines: list[str] = []
        for b in _ordered_buttons(after):
            lines += confirm_button_trace(after, b)
        return lines
    return [decision.detail]                                           # the combinator's own why-summary


# --- the whole re-derivation -------------------------------------------------------------------

@dataclass
class ReDerivation:
    """A spec change re-derived: the spec delta, the decision delta (each with its why), the two
    synthesized apps (source + Pilot verdict), and the emitted-source unified diff. `verified` iff both
    the before and after apps drove green — so this is a *verified* code change, not a bare re-emission."""
    spec_changes: list[str]
    decision_changes: list[DecisionChange]
    before: Synthesis
    after: Synthesis
    source_diff: list[str]

    @property
    def changed(self) -> bool:
        return bool(self.spec_changes) and (bool(self.decision_changes) or bool(self.source_diff))

    @property
    def verified(self) -> bool:
        vb, va = self.before.verify, self.after.verify
        return bool(vb and vb.ok and vb.live and va and va.ok and va.live)


def rederive(before: Spec, after: Spec) -> ReDerivation:
    """Synthesize BEFORE and AFTER, then diff the spec, the resolved decisions, and the emitted source in
    lockstep — each source hunk traceable to a decision change, each decision change to its derivation."""
    sb, sa = synthesize(before), synthesize(after)
    dec_b = {d.point: d for d in sb.deviation.decisions}
    dec_a = {d.point: d for d in sa.deviation.decisions}
    points = list(dec_a) + [p for p in dec_b if p not in dec_a]        # after's order, then dropped points
    changes: list[DecisionChange] = []
    for pt in points:
        b, a = dec_b.get(pt), dec_a.get(pt)
        bv = b.value if b else "—"
        av = a.value if a else "—"
        if bv != av:
            changes.append(DecisionChange(pt, bv, av, _why_after(pt, after, a)))
    diff = list(difflib.unified_diff(sb.source.splitlines(), sa.source.splitlines(),
                                     "before.py", "after.py", lineterm=""))
    return ReDerivation(_spec_changes(before, after), changes, sb, sa, diff)


# --- live walkthrough --------------------------------------------------------------------------

def _show(before: Spec, after: Spec, headline: str) -> None:
    rd = rederive(before, after)
    print(f"=== {headline} ===")
    print(f"  spec delta: {rd.spec_changes}")
    print(f"  decisions re-resolved:")
    for c in rd.decision_changes:
        print(f"    {c.point:<16} {c.before}  ->  {c.after}")
    print(f"  both apps Pilot-verified: {rd.verified}   (a VERIFIED code change, not a re-emission)\n")


def main() -> None:
    print("RE-DERIVATION DIFF — a policy change re-derives the code, with the derivation of WHY\n")

    reversible = Spec(name="withdraw_spec", irreversible=False)
    irreversible = Spec(name="withdraw_spec", irreversible=True)

    print("PART 1 — the headline: one policy sentence flips, the code re-derives\n")
    _show(reversible, irreversible, "policy change: the withdrawal becomes IRREVERSIBLE")

    rd = rederive(reversible, irreversible)
    screen = next(c for c in rd.decision_changes if c.point == "screen")
    print("  WHY the screen changed (the derivation a text diff cannot give):")
    print(f"    screen {screen.before} -> {screen.after}, because:")
    for line in screen.why:
        print(f"      {line}")

    print("\n  the SOURCE delta (every changed line traces to the decision above):")
    for line in rd.source_diff:
        print(f"    {line}")

    print("\nPART 2 — a defeasible-preference change: override the confirm buttons\n")
    default = Spec(name="withdraw_spec", irreversible=True)
    override = Spec(name="withdraw_spec", irreversible=True, buttons=("ok",))
    _show(default, override, "policy change: the confirm screen drops the Cancel button")
    rd2 = rederive(default, override)
    btn = next((c for c in rd2.decision_changes if c.point == "confirm_buttons"), None)
    if btn:
        print(f"  confirm_buttons {btn.before} -> {btn.after}; the source diff removes the Cancel widget:")
        for line in rd2.source_diff:
            if "cancel" in line.lower():
                print(f"    {line}")

    print("\nPART 3 — a no-op change re-derives to nothing (determinism: same spec, same code)\n")
    rd3 = rederive(irreversible, Spec(name="withdraw_spec", irreversible=True))
    print(f"  spec delta: {rd3.spec_changes or '[]'}   decision changes: {len(rd3.decision_changes)}   "
          f"source diff: {len(rd3.source_diff)} lines")
    print("\n  This is the 'policy change -> verified code change' artifact: the delta is explained by a")
    print("  derivation, not a regeneration — the audit trail no LLM re-prompt can produce.")


if __name__ == "__main__":
    main()
