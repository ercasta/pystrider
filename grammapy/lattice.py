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

from grammapy._cnl import derive

__all__ = ["Lattice", "FoldItem", "UnknownVerdict", "fold_unknowns", "fold_winner"]


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


# The fold as a CNL rule-module (the closure-shaped combinator). The chain is authored as adjacency
# (`?hi above ?lo`); a transitive closure gives `outranks`; the winner is the present verdict NO present
# verdict outranks (`not beaten`) — a set query, so ORDER-INDEPENDENCE is structural, not a proof
# obligation. Domain membership (`fold_unknowns`) is the same negation shape as a Choice gap.
_ORDER_RULES = """
?a outranks ?b when ?a above ?b
?a outranks ?b when ?a above ?m and ?m outranks ?b
"""
_WINNER_RULES = _ORDER_RULES + """
?v beaten yes when ?v present yes and ?w present yes and ?w outranks ?v
?v winner yes when ?v present yes and not ?v beaten yes
"""
_DOMAIN_RULES = "?v out_of_domain yes when ?v voted yes and not ?v in_domain yes"


def _order_facts(order: tuple[str, ...]) -> list[tuple[str, str, str]]:
    return [(order[i + 1], "above", order[i]) for i in range(len(order) - 1)]


def fold_unknowns(lattice: "Lattice", items: Iterable["FoldItem"]) -> list["UnknownVerdict"]:
    """Contributions whose verdict is outside the lattice domain — the fold's well-formedness check, as
    a CNL negation (`voted` but `not in_domain`). Reconstructed per contribution for the message."""
    items = list(items)
    facts = [(v, "in_domain", "yes") for v in lattice.order]
    facts += [(it.value, "voted", "yes") for it in items]
    domain = set(lattice.order)
    bad = {a.split(" ", 1)[0] for a in derive(facts, _DOMAIN_RULES, "who out_of_domain yes")
           if a.split(" ", 1)[0] not in domain}
    return [UnknownVerdict(it.value, it.label) for it in items if it.value in bad]


def fold_winner(lattice: "Lattice", items: Iterable["FoldItem"]) -> str:
    """Combine the contributions through the declared chain, order-independently: the highest-ranked
    verdict present, computed as the CNL winner (`not beaten`). Empty ⇒ the chain bottom (the identity).
    Assumes the verdicts are in domain (run `fold_unknowns` first)."""
    items = list(items)
    if not items:
        return lattice.bottom()
    facts = _order_facts(lattice.order)
    facts += [(it.value, "present", "yes") for it in items]
    domain = set(lattice.order)
    winners = {a.split(" ", 1)[0] for a in derive(facts, _WINNER_RULES, "who winner yes")
               if a.split(" ", 1)[0] in domain}
    return next(iter(winners), lattice.bottom())
