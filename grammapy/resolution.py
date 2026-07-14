"""Cross-cutting constraint resolution — the §12 mechanism (vision.md §12).

Two ways a spec fixes a decision point. A **point deviation** is extensional: name the point, set it.
A **cross-cutting constraint** is intensional: state a *property* the system must have (`requires
confirmation`, `requires tx`) addressed to no single point, and the system works out **where it bites** —
narrowing each open point's admissible productions to those that *provide* the required capabilities. The
resolution of one point is then exactly one of:

  * **Forced**    — a requirement narrows the productions to exactly one (deterministic, unique).
  * **Defaulted** — no requirement bites; the point takes its declared default (the spec was silent).
  * **Surfaced**  — several productions survive and no declared preference tie-breaks; a design-time
                    decision, raised, never silently picked.
  * **Rejected**  — no production provides the requirement; named, not silently mis-emitted.

The one rule that keeps this from becoming a hidden optimizing planner: **forced where unique, declared
where preferred, surfaced where ambiguous — never inferred.** A preference may only tie-break among
survivors, and it is itself a declared (reviewable) choice, exactly like `deny_overrides`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Union

__all__ = [
    "Production", "DecisionPoint",
    "Forced", "Defaulted", "Surfaced", "Rejected", "Resolution", "resolve",
]


@dataclass(frozen=True)
class Production:
    """One admissible filling of a decision point, and the capabilities it ``provides`` (the vocabulary a
    cross-cutting constraint narrows against)."""

    label: str
    provides: frozenset[str] = frozenset()


@dataclass(frozen=True)
class DecisionPoint:
    """An open decision: its admissible ``productions``, the ``default`` taken when the spec is silent, and
    an optional declared ``preference`` (labels best-first) that may tie-break among surviving productions."""

    name: str
    productions: tuple[Production, ...]
    default: str
    preference: tuple[str, ...] = ()


@dataclass(frozen=True)
class Forced:
    point: str
    production: str
    by: frozenset[str]
    reason: str = "unique"          # "unique" (a requirement left one) | "preference" (declared tie-break)

    def __str__(self) -> str:
        why = f"required {set(self.by)}" if self.reason == "unique" else f"declared preference among survivors"
        return f"{self.point} := {self.production}  (forced: {why})"


@dataclass(frozen=True)
class Defaulted:
    point: str
    production: str

    def __str__(self) -> str:
        return f"{self.point} := {self.production}  (default: spec silent)"


@dataclass(frozen=True)
class Surfaced:
    point: str
    survivors: tuple[str, ...]

    def __str__(self) -> str:
        return f"{self.point}: ambiguous - {list(self.survivors)} all satisfy; a design-time decision"


@dataclass(frozen=True)
class Rejected:
    point: str
    requirement: frozenset[str]

    def __str__(self) -> str:
        return f"{self.point}: no production provides all of {set(self.requirement)}"


Resolution = Union[Forced, Defaulted, Surfaced, Rejected]


def resolve(point: DecisionPoint, requires: Iterable[str]) -> Resolution:
    """Resolve one decision point against a cross-cutting requirement (a set of required capabilities).

    Forced where a requirement leaves exactly one production; Defaulted where nothing bites; a declared
    preference tie-breaks several survivors (still Forced, reason ``"preference"``); Surfaced where
    several survive with no preference; Rejected where none provides the requirement.
    """
    req = frozenset(requires)
    survivors = [p for p in point.productions if req <= p.provides]
    if not survivors:
        return Rejected(point.name, req)
    if not req:                                         # spec silent on every relevant capability
        return Defaulted(point.name, point.default)
    if len(survivors) == 1:
        return Forced(point.name, survivors[0].label, req, "unique")
    labels = {p.label for p in survivors}
    for pref in point.preference:                       # declared preference, best-first
        if pref in labels:
            return Forced(point.name, pref, req, "preference")
    return Surfaced(point.name, tuple(sorted(labels)))
