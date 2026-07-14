"""Declared joins — the substrate the semilattice-fold combinator composes through (vision.md §3.4, §7.3).

Some decision points combine *many* contributions into one verdict: authorization (grant/deny),
control severity, or — here — a **deontic** verdict on an act, voted by several rules (an obligation, a
waiver, a baseline). The Fold shape combines them through a **declared commutative/associative join**, so
the result is independent of the order the contributions arrived in. v1 fixes the decidable fragment: the
join is a declared **total order** (a chain, bottom→top) with `join = the higher-ranked` — which is a
join-semilattice *by construction of the order* (idempotent, commutative, associative), so the laws hold
without a separate proof (the analogue of Choice's restriction to a decidable guard fragment).

The chain IS the reviewable policy — `deny_overrides` is the chain `grant < deny`; a safety-first
confirmation policy is `waived < optional < obligatory`. Flipping the chain flips the policy, visibly, and
that is a declared choice (never inferred), exactly as §12 requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

__all__ = ["Lattice", "FoldItem", "UnknownVerdict"]


@dataclass(frozen=True)
class Lattice:
    """A declared join over a finite domain, as a total order `order` (bottom → top). `join(a, b)` is the
    higher-ranked element; the fold's identity is `bottom`. A total order is a join-semilattice by
    construction, so commutativity / associativity / idempotence hold without a separate check."""

    name: str
    order: tuple[str, ...]

    def domain(self) -> set:
        return set(self.order)

    def bottom(self) -> str:
        return self.order[0]

    def join(self, a: str, b: str) -> str:
        return a if self.order.index(a) >= self.order.index(b) else b


@dataclass(frozen=True)
class FoldItem:
    """One contribution to a fold: a labelled verdict (a lattice element). `label` is what a rejection
    message shows (e.g. the rule/source that voted); `value` is the element being combined."""

    label: str
    value: str


@dataclass(frozen=True)
class UnknownVerdict:
    """A contribution whose value is not in the lattice's domain — a malformed fold (undefined join)."""

    value: str
    label: str

    def __str__(self) -> str:
        return f"contribution `{self.label}` has verdict `{self.value}`, which is not in the lattice domain"
