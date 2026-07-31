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
from .mf import driver, function

_PREFIX, _INFIX = "as_", "_from_"


def _arity(lib: Library, name: str) -> int:
    return len(function.load(lib.graph, name)[0])


def bridges(lib: Library, *, lowering: bool = False) -> dict:
    """`{source_kind: bridge_name}`, derived from the bridge names themselves.

    ⚠ **Lifts and lowerings are told apart by ARITY, not by name.** A lift reads what is already on a node
    and casts that same node, so it takes one parameter. A lowering constructs a Python-shaped node that
    did not exist, so it takes the fresh subject *plus* the description to read from. That is a structural
    difference, and keying on it means a new bridge lands in the right pass by virtue of what it is."""
    out = {}
    for name in lib.bridge_names:
        if not (name.startswith(_PREFIX) and _INFIX in name):
            continue
        if (_arity(lib, name) == 2) == lowering:
            out[name.split(_INFIX, 1)[1]] = name
    return out


def vocabulary_drift(lib: Library) -> dict:
    """Labels a lift-bridge WRITES that no pattern READS. Empty means the two vocabularies still meet.

    **⚠ Why this check has to exist.** The neutral labels appear in two files: `patterns.mf` declares
    them, and `python.mf`'s bridges write them. Ideally a bridge would *delegate* — `INVOKE` the pattern
    rather than restate its labels — and then there would be one place and nothing to drift. That is not
    expressible today: `INVOKE` takes a dict of parameter bindings and the `.mf` surface has no dict
    literal, so a bridge has no way to say which pattern parameter each register fills.

    Given that, the duplication is forced. What is NOT forced is it drifting silently: rename a label in
    `patterns.mf` and the bridges keep writing the old one, so lifted code simply stops being recognized —
    no error, just less understanding than yesterday. This turns that into a fact anyone can ask for, and
    a pin asserts it is empty.

    Derived, never declared: both sides are read from the stored bodies, so it cannot itself go stale."""
    from .patterns import Abstained, pattern_of

    wanted = set()
    for name in lib.patterns:
        try:
            wanted |= {label for _kind, label, _s, _o in pattern_of(lib, name)[1]}
        except Abstained:
            continue

    out = {}
    for name in bridges(lib).values():                     # lifts only; lowerings write Python's names
        effects, _unknown = driver.establishes(lib.graph, name)
        stray = {label for _kind, label, _s, _o in effects} - wanted
        if stray:
            out[name] = sorted(stray)
    return out


def lower(lib: Library, description: str, pattern: str):
    """Construct the Python-shaped node for a neutral `description`. Returns the new node.

    The write half reaching an artifact: a description that was CONSTRUCTED (not read from code) becomes
    a node `strider.emit` can render. The subject is minted here for the same reason `construct` mints
    one — a lowering must stay a cast to stay readable."""
    table = bridges(lib, lowering=True)
    kind = pattern.removeprefix(_PREFIX)
    name = next((n for k, n in table.items() if n.endswith(_INFIX + kind)), None)
    if name is None:
        raise KeyError(f"no lowering for {pattern!r}; have: {sorted(table.values())}")
    node = lib.graph.mint(function.returns_of(lib.graph, name) or kind)
    function.invoke(lib.graph, name, {function.load(lib.graph, name)[0][0]: node,
                                      function.load(lib.graph, name)[0][1]: description})
    return node


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


__all__ = ["lift", "lower", "bridges", "reachable", "vocabulary_drift"]
