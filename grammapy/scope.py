"""Binder-scoped reachability — the substrate the Scope combinator composes through (vision.md §3.2, §3.4).

Control flow enters as **effects**: a leaf may `emit` a control signal (an error, a `needs_confirmation`,
a transaction demand), and a **handler** node (a binder) `handles` a set of signals over its sub-tree.
The Scope shape is sound iff **every emitted signal has a covering handler ancestor** — the reachability
obligation, the formal statement of the tacit engineering rule "no effect escapes unhandled". This is the
algebraic-effects/handlers model (Plotkin–Pretnar): an emitted signal with no enclosing handler is a
control leak, refused at design time rather than discovered as an unhandled path at runtime.

A handler covers effects performed *within* it (its descendants), not its own emissions — so the covering
handler must be a strict ancestor, exactly as an algebraic handler scopes the computation it wraps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

__all__ = ["ScopeNode", "Unhandled", "unhandled_emissions"]


@dataclass(frozen=True)
class ScopeNode:
    """A node in the control tree. ``emits`` are the control signals it raises (a leaf effect —
    corresponds to a ``channels.Footprint.emits``); ``handles`` are the signals it, as a handler/binder,
    covers over its descendants; ``children`` are the nodes in its scope."""

    label: str
    emits: frozenset[str] = frozenset()
    handles: frozenset[str] = frozenset()
    children: tuple["ScopeNode", ...] = ()

    @staticmethod
    def of(label: str, *, emits: Iterable[str] = (), handles: Iterable[str] = (),
           children: Iterable["ScopeNode"] = ()) -> "ScopeNode":
        return ScopeNode(label, frozenset(emits), frozenset(handles), tuple(children))


@dataclass(frozen=True)
class Unhandled:
    """A control signal emitted with no covering handler ancestor — the reachability violation."""

    signal: str
    leaf: str

    def __str__(self) -> str:
        return f"control signal `{self.signal}` emitted by `{self.leaf}` has no covering handler in scope"


def unhandled_emissions(node: ScopeNode, handled_above: frozenset[str] = frozenset()) -> list[Unhandled]:
    """Walk the control tree; return every emission that escapes its scope (no handler ancestor covers
    it). ``handled_above`` is the set of signals handled by strict ancestors — a node's own ``handles``
    covers its descendants, never its own ``emits``. Empty list ⇒ every effect is reachably handled."""
    conflicts = [Unhandled(s, node.label) for s in node.emits if s not in handled_above]
    handled = handled_above | node.handles
    for child in node.children:
        conflicts += unhandled_emissions(child, handled)
    return conflicts
