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


def bridges(lib: Library) -> dict:
    """`{source_kind: lift_name}` — the LIFTS, derived from their own names.

    ⚠ **A lift is told from a lowering by ARITY, not by name.** A lift reads what is already on a node and
    casts that same node, so it takes exactly one parameter. A lowering is handed its parts and so takes
    several. Structural, so a new bridge lands in the right pass by virtue of what it is."""
    return {name.split(_INFIX, 1)[1]: name for name in lib.bridge_names
            if name.startswith(_PREFIX) and _INFIX in name and _arity(lib, name) == 1}


def lowering_for(lib: Library, pattern: str) -> str:
    """The lowering that builds the Python shape for `pattern`, derived rather than tabulated.

    The LIFT's name already records the correspondence — `as_iteration_from_for_stmt` says that a
    `for_stmt` is an `iteration` — so the lowering is `as_<that kind>`. No second table, and nothing to
    keep in step."""
    kind = next((k for k, lift in bridges(lib).items()
                 if lift.startswith(pattern + _INFIX)), None)
    if kind is None:
        raise KeyError(f"no bridge relates {pattern!r} to any Python construct; "
                       f"lifts: {sorted(bridges(lib).values())}")
    name = _PREFIX + kind
    if name not in lib.bridge_names:
        raise KeyError(f"{pattern!r} lifts from {kind!r} but there is no lowering {name!r}")
    return name


def lower(lib: Library, description: str, pattern: str):
    """Construct the Python-shaped node for a neutral `description`. Returns the new node.

    The write half reaching an artifact: a description CONSTRUCTED rather than read from code becomes a
    node `strider.emit` can render.

    ⭐ **The parts come from `recognize`, which reads them off the PATTERN.** That is what keeps every
    neutral label in one file: this function does not know what `repeats_over` is called, and neither does
    `python.mf`. The pattern's binding names and the lowering's parameter names line up by construction —
    both describe the same three parts — so a mismatch is a real authoring error and says so."""
    from .patterns import recognize

    name = lowering_for(lib, pattern)
    bound = recognize(lib, description, pattern)
    if bound is None:
        raise ValueError(f"{description} is not a {pattern}, so there is nothing to lower")

    params, _program = function.load(lib.graph, name)
    subject, expected = params[0], set(params[1:])
    if set(bound) != expected:
        raise KeyError(f"{name}() wants {sorted(expected)} but {pattern} binds {sorted(bound)} — the "
                       "pattern and its lowering disagree about the parts")
    node = lib.graph.mint(function.returns_of(lib.graph, name) or name.removeprefix(_PREFIX))
    function.invoke(lib.graph, name, {subject: node, **bound})
    return node


#: The register a bridge leaves its cast in. ⚠ An AUTHORING CONVENTION, not a mechanism ugm enforces:
#: a bridge that cast sets it, a bridge that abstained leaves it unset. See `rules/python.mf`.
_OUT = "out"


def lift(lib: Library, root: str) -> dict:
    """Walk everything reachable from `root` and apply whichever bridge matches each node's kind.

    Returns `{bridge_name: [nodes lifted]}` — a record of what was touched, not a count, because the
    useful question afterwards is *which* nodes now speak the neutral vocabulary.

    ⚠ **A node a bridge ABSTAINED on is not in that record**, and the distinction is not cosmetic. `f()`
    is a `call`, so the bridge is invoked at it, and there is no argument for `as_application` to bind —
    so nothing is cast and the node still speaks only Python. Counting it as lifted would make this record
    a claim about which bridges RAN rather than about which nodes now carry the neutral vocabulary, and
    the second is the only question anybody asks it. Read off `out`, per the convention above."""
    g, table, applied = lib.graph, bridges(lib), {}
    for node in reachable(lib, root):
        name = table.get(g.kind(node))
        if name is None:
            continue
        _focus, regs = function.invoke(g, name, {function.load(g, name)[0][0]: node})
        if regs.get(_OUT) is not None:
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


__all__ = ["lift", "lower", "bridges", "lowering_for", "reachable"]
