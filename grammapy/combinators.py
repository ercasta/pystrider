"""The combination shapes (vision.md §3.4).

The four combinators are the *entire* built-in nonterminal vocabulary; a domain adds
atoms and wiring, never new combinators (§11.2). Each carries its soundness check.

Only ``Accumulate`` is implemented so far — it hosts REST decision points 4, 5, 7, 9
(docs/rest-domain.md) and its check is the shared disjoint-writes rule. ``Choice``,
``Fold``, and ``Scope`` are declared as the next roadmap steps and raise until then, so
the vocabulary is visible and the gaps are explicit rather than silent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from grammapy.channels import Footprint, WriteConflict, disjoint_writes
from grammapy.guards import GuardedProduction, guard_coverage
from grammapy.scope import ScopeNode, unhandled_emissions
from grammapy.lattice import Lattice, FoldItem, UnknownVerdict

__all__ = ["Item", "CompositionError", "Accumulate", "Choice", "Scope", "Fold"]


@dataclass(frozen=True)
class Item:
    """A labelled footprint — one candidate member of a combinator.

    ``label`` is what a rejection message shows the user (a deviation's source text,
    e.g. ``"range(age, 0, 120)"``); ``footprint`` is what the check reasons over.
    """

    label: str
    footprint: Footprint


class CompositionError(Exception):
    """A combinator's soundness check failed — refused admission at design time.

    Carries the structured cause so callers can render it however they like; ``str``
    gives the human-facing rejection (roadmap step 3: name the conflicting deviations
    and the shared channel, never a combinator soundness trace).
    """

    def __init__(self, shape: str, conflicts: list, reason: str = "writes are not disjoint"):
        self.shape = shape
        self.conflicts = conflicts
        self.reason = reason
        lines = [f"{shape} rejected: {reason}"]
        for c in conflicts:
            lines.append(f"  - {c}")
        super().__init__("\n".join(lines))


class Accumulate:
    """Disjoint-footprint accumulation (vision.md §3.4).

    Each item is independently applicable; the shape is sound iff the items' ``writes``
    are pairwise disjoint. Reading and emitting are unconstrained here (they are the
    concern of the frame rule's read-side and of reachability, respectively).
    """

    @staticmethod
    def check(items: Iterable[Item]) -> None:
        """Raise ``CompositionError`` if any two items write the same channel."""
        conflicts = disjoint_writes((it.label, it.footprint) for it in items)
        if conflicts:
            raise CompositionError("Accumulate", conflicts)


class Choice:
    """Exclusive-choice (vision.md §3.4, §4.3).

    Guards over a single spec key partition the domain ``enum ∪ {absent}``; exactly one production
    fires per spec. The shape is sound iff the guards are pairwise **disjoint** and jointly
    **exhaustive** — a static enum-cover analysis (the moding/determinacy analysis of logic
    programming), never a search. Selection is then a direct lookup, not a constraint solve.
    """

    @staticmethod
    def check(enum: Iterable[str], productions: Iterable[GuardedProduction]) -> None:
        """Raise ``CompositionError`` unless the guards partition the domain (disjoint AND exhaustive)."""
        conflicts = guard_coverage(enum, productions)
        if conflicts:
            raise CompositionError("Choice", conflicts,
                                   reason="guards do not partition the spec space")

    @staticmethod
    def select(productions: Iterable[GuardedProduction], state) -> GuardedProduction:
        """The production admitting ``state`` (an enum literal or ``ABSENT``). For a checked Choice
        exactly one matches; raises ``KeyError`` if none does (an unchecked or malformed choice)."""
        for p in productions:
            if state in p.guard.covers():
                return p
        raise KeyError(f"no production admits state {state!r}")


class Scope:
    """Binder-scoped reachability (vision.md §3.2, §3.4).

    Control flow is effects: a leaf ``emits`` a control signal, a handler node ``handles`` signals over
    its sub-tree. The shape is sound iff **every emitted signal has a covering handler ancestor** — no
    effect escapes its scope. The algebraic-effects/handlers model, checked statically: an unhandled
    emission is refused at design time, not discovered as an unhandled path at runtime.
    """

    @staticmethod
    def check(root: ScopeNode) -> None:
        """Raise ``CompositionError`` if any control signal is emitted with no covering handler ancestor."""
        conflicts = unhandled_emissions(root)
        if conflicts:
            raise CompositionError("Scope", conflicts,
                                   reason="control signals escape their scope (no covering handler)")


class Fold:
    """Semilattice fold (vision.md §3.4, §7.3).

    Combine many contributions into one verdict through a declared ``Lattice`` join. The shape is sound
    iff every contribution's value is in the lattice domain (the join is then defined and, because the
    lattice is a total order, order-independent by construction). ``combine`` folds the contributions;
    the result does not depend on their order — the property that lets independent rules vote safely.
    """

    @staticmethod
    def check(lattice: Lattice, items: Iterable[FoldItem]) -> None:
        """Raise ``CompositionError`` if any contribution's verdict is outside the lattice domain."""
        domain = lattice.domain()
        bad = [UnknownVerdict(it.value, it.label) for it in items if it.value not in domain]
        if bad:
            raise CompositionError("Fold", bad, reason="a contribution's verdict is not in the lattice domain")

    @staticmethod
    def combine(lattice: Lattice, items: Iterable[FoldItem]) -> str:
        """Fold the contributions through the declared join (order-independent). Empty ⇒ the lattice
        bottom (the join identity). Assumes ``check`` passed (all verdicts in domain)."""
        result = lattice.bottom()
        for it in items:
            result = lattice.join(result, it.value)
        return result
