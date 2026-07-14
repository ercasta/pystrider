"""Feasibility probe — the REFUSAL UX: an uncovered spec region becomes a NAMED GAP, not a guess.

`docs/roadmap.md` Phase 3 + held line #3 ("refusal is a feature"): *"an uncovered spec region yields a
named gap — 'no fragment provides X; a KB entry of shape Y would fill it' — engineered as a good
experience (the on-ramp to Track C authoring, and later the hole that mode 2 hands to an LLM), not a
dead end."* The identity the whole stack rests on is **generation breadth = KB coverage**: the rules
select, expand, and compose, they do not invent. So the honest behaviour at the edge of coverage is
neither a crash nor an improvised guess — it is a REFUSAL that names precisely what the KB lacks and the
shape of the entry that would extend it.

The machinery already draws the line: grammapy's §12 `resolve` returns `Rejected` when no production
provides a required capability, and `Surfaced` when several do and no preference tie-breaks. This probe
turns those two "not a clean single production" outcomes into a first-class `Gap` — the actionable
artifact that makes refusal a good experience:

  * an UNPROVIDED gap  — "decision point P requires capability X; no production provides it. To fill:
                         add a Production providing X (a fragment of shape Y)." — the authoring on-ramp.
  * an AMBIGUOUS gap   — "capabilities are satisfied by several productions and no preference declares
                         which. To fill: declare a preference." — surfaced, never silently picked.

And it wires refusal into the generation loop: `synthesize_or_refuse` either emits the verified app OR
returns the named gaps — refusal as a first-class OUTCOME of generation, the alternative to emission,
exactly where mode-2 will later hand the named hole to an LLM.

Run it: `python -m experiments.refusal`  (requires `textual` only for the synthesize path).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from grammapy import DecisionPoint, Production, resolve, Forced, Defaulted, Surfaced, Rejected

from experiments.app_synthesis import Spec, SCREEN_POINT, required_capabilities, synthesize, Synthesis


# --- the named gap: what is uncovered, and the shape of the KB entry that would fill it ---------

@dataclass(frozen=True)
class Gap:
    """An uncovered spec region, NAMED. `kind` is 'unprovided' (no production provides the requirement)
    or 'ambiguous' (several do, no preference tie-breaks). `fill` is the shape of the KB entry that would
    close it — the on-ramp to authoring (Track C), and later the hole mode-2 hands an LLM."""
    point: str
    kind: str
    requirement: frozenset[str] = frozenset()     # 'unprovided': the capability nothing provides
    survivors: tuple[str, ...] = ()                # 'ambiguous': the productions that all satisfy it
    fill: str = ""

    def render(self) -> list[str]:
        """The gap as a good experience: what is missing, and the concrete KB entry that would fill it."""
        if self.kind == "unprovided":
            head = (f"GAP at '{self.point}': the spec requires {set(self.requirement)}, "
                    f"but no production provides it.")
        else:
            head = (f"GAP at '{self.point}': {list(self.survivors)} all satisfy the requirement and no "
                    f"preference declares which.")
        return [head, f"  to fill, add a KB entry of this shape:", f"      {self.fill}"]


def gap_of(point: DecisionPoint, requires: Iterable[str]) -> Gap | None:
    """Resolve `point` against `requires`; return the NAMED GAP if it did not resolve to a single
    production, else None. This is the refusal boundary: a clean Forced/Defaulted proceeds to emission;
    a Rejected/Surfaced refuses with a gap that names the KB entry which would let generation continue."""
    r = resolve(point, requires)
    if isinstance(r, (Forced, Defaulted)):
        return None
    if isinstance(r, Rejected):
        cap = ", ".join(sorted(r.requirement))
        fill = (f"Production(label='<name>', provides=frozenset({{{', '.join(map(repr, sorted(r.requirement)))}}}))"
                f"   # a '{point.name}' production providing {cap!r}")
        return Gap(point.name, "unprovided", requirement=r.requirement, fill=fill)
    # Surfaced
    fill = (f"preference={r.survivors!r} on DecisionPoint('{point.name}', ...)"
            f"   # declare which production wins")
    return Gap(point.name, "ambiguous", survivors=r.survivors, fill=fill)


# --- refusal wired into the generation loop ----------------------------------------------------

@dataclass
class Refusal:
    """The generator REFUSED: the spec region it could not derive, as named gaps. Not a crash — the
    alternative outcome to emission, carrying exactly what authoring (or an LLM) must supply to proceed."""
    gaps: list[Gap]


def synthesize_or_refuse(spec: Spec, requires: Iterable[str] = ()) -> "Synthesis | Refusal":
    """Either emit the verified app, or REFUSE with named gaps. The screen point is resolved against the
    reasoning's derived requirements PLUS any `requires` a richer policy would add (e.g. a high-assurance
    withdrawal demanding `biometric`); if the KB covers them, generation proceeds; if not, it refuses and
    names the gap — 'refusal is a feature', made a first-class return value rather than an exception."""
    demanded = required_capabilities(spec) | frozenset(requires)
    gap = gap_of(SCREEN_POINT, demanded)
    if gap is not None:
        return Refusal([gap])
    return synthesize(spec)


# --- live walkthrough --------------------------------------------------------------------------

def main() -> None:
    print("REFUSAL UX — an uncovered spec region becomes a NAMED GAP, not a guess\n")
    print(f"  screen decision point provides: "
          f"{ {p.label: set(p.provides) for p in SCREEN_POINT.productions} }\n")

    print("PART 1 — a COVERED requirement resolves cleanly, generation proceeds\n")
    covered = required_capabilities(Spec(name="w", irreversible=True))     # {'confirmation'} — provided
    print(f"  reasoning requires {set(covered)} -> {resolve(SCREEN_POINT, covered)}")
    print(f"  gap? {gap_of(SCREEN_POINT, covered)}   (None -> no refusal, the KB covers it)\n")

    print("PART 2 — an UNCOVERED requirement refuses with a named gap (the authoring on-ramp)\n")
    print("  suppose a high-assurance policy derives `requires biometric` for a high-value withdrawal —")
    print("  the KB has no screen production providing it:")
    gap = gap_of(SCREEN_POINT, {"biometric"})
    for line in gap.render():
        print(f"    {line}")
    print("  (the generator refuses what it cannot derive and names the exact entry that would let it —")
    print("   never a silent mis-emission, never an improvised biometric screen it has no fragment for.)\n")

    print("PART 3 — an AMBIGUOUS requirement refuses asking for a declared preference\n")
    two = DecisionPoint("screen", (
        Production("confirm_modal", frozenset({"confirmation"})),
        Production("confirm_inline", frozenset({"confirmation"}))), default="confirm_modal")
    for line in gap_of(two, {"confirmation"}).render():
        print(f"    {line}")

    print("\nPART 4 — refusal as a first-class OUTCOME of the generation loop\n")
    ok = synthesize_or_refuse(Spec(name="w", irreversible=True))
    print(f"  synthesize_or_refuse(irreversible)            -> {type(ok).__name__}"
          f"  (screen={getattr(ok, 'screen', None)}, verified={getattr(getattr(ok,'verify',None),'ok',None)})")
    refused = synthesize_or_refuse(Spec(name="w", irreversible=True), requires={"biometric"})
    print(f"  synthesize_or_refuse(+requires biometric)     -> {type(refused).__name__}")
    for g in refused.gaps:
        print(f"      {g.render()[0]}")
    print("\n  Refusal is a return value, not a crash: the loop emits a verified app OR names the gap that")
    print("  authoring (Track C) — or later an LLM (mode 2) — must fill. Generation breadth = KB coverage,")
    print("  stated honestly at the edge instead of guessed across it.")


if __name__ == "__main__":
    main()
