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

from grammapy._cnl import derive

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


# Reachability as a CNL rule-module: a signal a node EMITS is handled iff some STRICT ancestor HANDLES
# it (the `parent_of` closure excludes the node itself, so a node never handles its own emission). The
# closure is recursive Datalog; `not handled` is stratified negation over it — the soundness verdict.
_UNHANDLED_RULES = """
?a ancestor_of ?n when ?a parent_of ?n
?a ancestor_of ?n when ?a parent_of ?m and ?m ancestor_of ?n
?n handled ?sig when ?n emits ?sig and ?a ancestor_of ?n and ?a handles ?sig
?n unhandled ?sig when ?n emits ?sig and not ?n handled ?sig
"""

# a synthetic ancestor above the root, carrying `handled_above` — signals handled by an enclosing scope.
_ROOT_ABOVE = "\x00grammapy.scope.above"


def unhandled_emissions(node: ScopeNode, handled_above: frozenset[str] = frozenset()) -> list[Unhandled]:
    """Walk the control tree; return every emission that escapes its scope (no handler ancestor covers
    it). ``handled_above`` is the set of signals handled by strict ancestors — a node's own ``handles``
    covers its descendants, never its own ``emits``. Empty list ⇒ every effect is reachably handled.

    The verdict is the CNL rule-module ``_UNHANDLED_RULES`` evaluated read-only: a recursive ancestor
    closure + stratified ``not handled``. ``handled_above`` is modelled as a synthetic handler node
    above the root. Results are emitted in tree-walk order (the original traversal order)."""
    facts: list[tuple[str, str, str]] = []
    if handled_above:
        facts.append((_ROOT_ABOVE, "parent_of", node.label))
        facts.extend((_ROOT_ABOVE, "handles", s) for s in handled_above)

    def walk(nd: ScopeNode) -> None:
        facts.extend((nd.label, "emits", s) for s in nd.emits)
        facts.extend((nd.label, "handles", s) for s in nd.handles)
        for child in nd.children:
            facts.append((nd.label, "parent_of", child.label))
            walk(child)
    walk(node)

    signals = {s for (_, p, s) in facts if p == "emits"}
    escaped: set[tuple[str, str]] = set()
    for sig in signals:
        for ans in derive(facts, _UNHANDLED_RULES, f"who unhandled {sig}"):
            parts = ans.split()                         # a real answer is "<leaf> unhandled <sig>"
            if len(parts) == 3 and parts[1] == "unhandled":
                escaped.add((parts[0], parts[2]))

    conflicts: list[Unhandled] = []
    def collect(nd: ScopeNode) -> None:                 # tree-walk order, matching the original
        conflicts.extend(Unhandled(s, nd.label) for s in nd.emits if (nd.label, s) in escaped)
        for child in nd.children:
            collect(child)
    collect(node)
    return conflicts
