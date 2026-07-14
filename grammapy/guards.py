"""Guards and the coverage check — the substrate the exclusive-choice combinator composes through.

A ``Choice`` decision point is over a single spec **key** with a declared finite **enum** of literal
values (vision.md §4.3). A ``Guard`` admits a set of *states* of that key — a boolean combination, in
the decidable v1 fragment, of key **presence/absence** and **equality** against an enum literal
(``key.absent | key=sql``). Soundness of the choice is decided entirely from the guards: they must be
pairwise **disjoint** and jointly **exhaustive** over the domain ``enum ∪ {absent}``, so exactly one
production fires per spec — checkable as a finite enum-cover analysis (the moding/determinacy analysis
of logic programming), never a search.

Anything richer than presence/absence + enum-equality belongs inside an opaque atom, not a guard whose
disjointness we claim to prove (§4.3) — that restriction is what earns the decidability claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

__all__ = [
    "ABSENT", "Guard", "GuardedProduction",
    "GuardOverlap", "GuardGap", "GuardUnknownValue", "guard_coverage",
]


class _Absent:
    """The key-absent state — a single sentinel, so a spec that stays silent on the key is a first-class
    domain value (Reiter's 'assume the default unless blocked', vision.md §5.3)."""

    _instance: "_Absent | None" = None

    def __new__(cls) -> "_Absent":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "absent"


ABSENT = _Absent()   # the domain state for "spec is silent on this key" — the default branch's atom


@dataclass(frozen=True)
class Guard:
    """What states of the decision key a production admits (vision.md §4.3, decidable fragment).

    ``values`` are enum literals the key may equal; ``absent`` includes the key-absent state. A guard
    is the union (``|``) of those atoms — e.g. ``key.absent | key=sql`` is ``Guard({"sql"}, absent=True)``.
    """

    values: frozenset[str] = frozenset()
    absent: bool = False

    @staticmethod
    def of(*values: str, absent: bool = False) -> "Guard":
        """Build a Guard from enum literals (and optionally the absent atom)."""
        return Guard(frozenset(values), absent)

    def covers(self) -> set:
        """The domain states this guard admits (enum literals plus ABSENT if the absent atom is present)."""
        cov: set = set(self.values)
        if self.absent:
            cov.add(ABSENT)
        return cov


@dataclass(frozen=True)
class GuardedProduction:
    """One guarded branch of a ``Choice``: a labelled production admitted on ``guard``'s states.

    ``label`` is what a rejection message shows the user; ``footprint`` is carried for when a Choice is
    nested inside another combinator (its writes/emits synthesize upward) but is not consulted by the
    guard-coverage check, which reasons over guards and the enum alone.
    """

    label: str
    guard: Guard
    footprint: object = None   # grammapy.channels.Footprint | None — unused by guard_coverage


@dataclass(frozen=True)
class GuardOverlap:
    """Two productions admit the same key-state — the disjointness violation (guards not exclusive)."""

    state: object
    left: str
    right: str

    def __str__(self) -> str:
        return f"state `{self.state}` is admitted by both `{self.left}` and `{self.right}`"


@dataclass(frozen=True)
class GuardGap:
    """A key-state no production admits — the exhaustiveness violation (a spec with no firing branch)."""

    state: object

    def __str__(self) -> str:
        return f"state `{self.state}` is admitted by no production"


@dataclass(frozen=True)
class GuardUnknownValue:
    """A guard equals a literal outside the declared enum — a malformed guard (not in the domain)."""

    value: str
    label: str

    def __str__(self) -> str:
        return f"guard of `{self.label}` admits `{self.value}`, which is not in the declared enum"


def guard_coverage(enum: Iterable[str], productions: Iterable[GuardedProduction]) -> list:
    """The determinacy analysis, made operational (vision.md §4.3).

    Given the decision key's finite ``enum`` and its guarded productions, return every coverage
    conflict: guard **overlaps** (a state admitted twice — not disjoint), **gaps** (a state admitted
    never — not exhaustive), and **unknown values** (a guard literal outside the enum). Empty list ⇒ the
    guards **partition** the domain ``enum ∪ {absent}`` exactly, so exactly one production fires per
    spec. Order-independent by construction (it inspects the unordered state→owner map).
    """
    literals = set(enum)
    domain = literals | {ABSENT}
    owner: dict = {}
    conflicts: list = []
    for p in productions:
        for state in p.guard.covers():
            if state is not ABSENT and state not in literals:
                conflicts.append(GuardUnknownValue(state, p.label))
                continue
            prior = owner.get(state)
            if prior is not None and prior != p.label:
                conflicts.append(GuardOverlap(state, prior, p.label))
            else:
                owner.setdefault(state, p.label)
    conflicts += [GuardGap(s) for s in sorted(domain - owner.keys(), key=str)]
    return conflicts
