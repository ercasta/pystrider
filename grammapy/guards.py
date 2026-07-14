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

from grammapy._cnl import derive

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


# The determinacy analysis as a CNL rule-module. States and productions are namespaced (`s:`/`p:`) so a
# production whose label equals an enum literal (the common `sql`-branch-for-`sql` case) never fuses with
# the state node. The three verdicts: a guard literal outside the domain (`guard_unknown`, negation), a
# state admitted by two DISTINCT productions (`state_overlap`, the `?p != ?q` distinctness — not disjoint),
# and a domain state admitted by none (`state_gap`, stratified negation — not exhaustive).
_GUARD_RULES = """
?s is_admitted yes when ?p admits ?s
?v guard_unknown yes when ?p admits ?v and not ?v domain_state yes
?s state_overlap yes when ?p admits ?s and ?q admits ?s and ?p != ?q and ?s domain_state yes
?s state_gap yes when ?s domain_state yes and not ?s is_admitted yes
"""


def _state_node(state) -> str:
    return "s:absent" if state is ABSENT else f"s:{state}"


def _from_state_node(node: str):
    name = node[2:]                                      # strip the "s:" namespace
    return ABSENT if name == "absent" else name


def guard_coverage(enum: Iterable[str], productions: Iterable[GuardedProduction]) -> list:
    """The determinacy analysis, made operational (vision.md §4.3).

    Given the decision key's finite ``enum`` and its guarded productions, return every coverage
    conflict: guard **overlaps** (a state admitted twice — not disjoint), **gaps** (a state admitted
    never — not exhaustive), and **unknown values** (a guard literal outside the enum). Empty list ⇒ the
    guards **partition** the domain ``enum ∪ {absent}`` exactly, so exactly one production fires per spec.

    The verdict is the CNL rule-module ``_GUARD_RULES`` evaluated read-only; the violation objects are
    reconstructed from the same guards for the message. Order-independent by construction (the CNL
    negation/distinctness rules inspect unordered facts)."""
    productions = list(productions)
    literals = set(enum)
    facts: list[tuple[str, str, str]] = [(_state_node(l), "domain_state", "yes") for l in literals]
    facts.append(("s:absent", "domain_state", "yes"))
    for p in productions:
        facts.extend((f"p:{p.label}", "admits", _state_node(s)) for s in p.guard.covers())

    def who(pred: str) -> set[str]:
        return {a.split(" ", 1)[0] for a in derive(facts, _GUARD_RULES, f"who {pred} yes")
                if a.split(" ", 1)[0].startswith("s:")}

    unknown, overlapped, gaps = who("guard_unknown"), who("state_overlap"), who("state_gap")

    conflicts: list = []
    for p in productions:                                # unknown guard literals (production-scan order)
        for state in p.guard.covers():
            if _state_node(state) in unknown:
                conflicts.append(GuardUnknownValue(state, p.label))
    for node in sorted(overlapped):                      # states admitted by two distinct productions
        state = _from_state_node(node)
        admitters = [p.label for p in productions if state in p.guard.covers()]
        conflicts.extend(GuardOverlap(state, admitters[0], later) for later in admitters[1:])
    conflicts += [GuardGap(_from_state_node(n))           # domain states no production admits
                  for n in sorted(gaps, key=lambda n: str(_from_state_node(n)))]
    return conflicts
