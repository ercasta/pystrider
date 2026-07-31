"""LIFT — apply the bridges, so intaken Python carries the neutral vocabulary the patterns speak.

A bridge is named `as_<pattern>_from_<kind>`, and **that name IS the mapping**. There is no second table
saying which bridge applies to which node kind, because a table would be a separate thing to keep in step
with the library and would drift the first time somebody added a bridge and forgot the entry. The rule
here is the same one ugm reached for its type cache: do not store what the structure already entails.

**⚠ Bridges are POINTED, and that is the real change from the old engine.** A rule fired wherever the
world matched; a microfunction must be *invoked at* something. So lifting is an explicit pass over
intaken nodes rather than an ambient consequence of the facts existing. This is more code than a rule
bank needed and it is the honest cost of the repoint — but it is also why nothing fires unexpectedly, and
why the set of nodes a bridge touched is a fact rather than an inference.

**Lifting does not skip partial nodes.** Structure is structure, and a partial node's neutral edges are
as true as any other's. Refusal belongs in ONE place — `strider.patterns.recognize` declines a partial
node — because a rule enforced at two sites is a rule that will eventually be enforced at one.
"""
from __future__ import annotations

from .library import Library
from .mf import function

_PREFIX, _INFIX = "as_", "_from_"


def bridges(lib: Library) -> dict:
    """`{node_kind: bridge_name}`, derived from the bridge names themselves."""
    out = {}
    for name in lib.names:
        if name.startswith(_PREFIX) and _INFIX in name:
            out[name.split(_INFIX, 1)[1]] = name
    return out


def lift(lib: Library, root: str) -> dict:
    """Walk everything reachable from `root` and apply whichever bridge matches each node's kind.

    Returns `{bridge_name: [nodes lifted]}` — a record of what was touched, not a count, because the
    useful question afterwards is *which* nodes now speak the neutral vocabulary."""
    g, table, applied = lib.graph, bridges(lib), {}
    for node in reachable(lib, root):
        name = table.get(g.kind(node))
        if name is None:
            continue
        function.invoke(g, name, {function.load(g, name)[0][0]: node})
        applied.setdefault(name, []).append(node)
    return applied


def reachable(lib: Library, root: str) -> list:
    """Every node reachable from `root` by outgoing edges, `root` first, each visited once.

    Outgoing only, which is ugm's direction invariant read from the consumer's side: structure points
    outward and metadata points inward, so following outgoing edges stays inside the artifact and never
    drags in an application, a mapping or a plan that happens to point at it."""
    g, seen, order, stack = lib.graph, {root}, [], [root]
    while stack:
        node = stack.pop()
        order.append(node)
        for label in g.labels(node):
            for target in g.targets(node, label):
                if target not in seen:
                    seen.add(target)
                    stack.append(target)
    return order


__all__ = ["lift", "bridges", "reachable"]
