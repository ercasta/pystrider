"""The bidirectional pattern layer — one authored description, both halves.

This is slice 0 promoted from probe to product. The reasoning lives in
`experiments/microfunction_pattern.py`'s docstring; what follows is what a consumer needs to know.

**WRITE** — `construct(lib, "as_iteration", seq=..., var=..., body=...)` calls the stored function.
**READ** — `recognize(lib, node)` derives the description from that same stored body and matches it.

Neither half names a predicate. `repeats_over` appears in `strider/rules/patterns.mf` and nowhere else in
this package, which is the property that makes it one library instead of two that agree.

**Recognition returns BINDINGS, not a verdict** — *which* sequence, *which* variable, *which* body. That
is `experiments/understand_partial.py`'s result carried across: the useful unit is the partial
description, because a verdict tells a consumer nothing it can act on. `None` is an honest refusal.

**⚠ The contract inversion, and why `Abstained` exists.** `driver.establishes` is built to RANK candidate
actions: it over-approximates on purpose and its own docstring says it "orders but never rules out". For
ranking, an incomplete effect set is safe — it loses no candidates. For recognition it is a false-positive
generator, because a node can satisfy every readable effect while failing the one nobody could read. Same
value, opposite safety. So recognition refuses where the driver would shrug.
"""
from __future__ import annotations

from .library import Library
from .mf import driver, function


class Abstained(Exception):
    """Recognition refused: the description could not be read completely, so it must not be matched."""


def pattern_of(lib: Library, name: str) -> tuple:
    """The description, read off the stored body. Returns `(subject_param, required_effects)`.

    The subject is the FIRST parameter — not a convention invented here, but the engine's own rule that a
    cast returns its subject and `run` falls back to the first argument when a function sets no `result`.
    Effects that do not hang off the subject are not part of what makes a node an instance."""
    if name not in lib.names:
        raise Abstained(f"{name!r} is not in the library; in repertoire: {', '.join(lib.names)}")
    effects, unknown = driver.establishes(lib.graph, name)
    if unknown:
        raise Abstained(f"{name}: the body writes something that cannot be read statically (a label or "
                        "key from a register), so the description is incomplete and matching it would "
                        "admit nodes that fail a requirement nobody could read")
    params, _program = function.load(lib.graph, name)
    if not params:
        raise Abstained(f"{name}: no parameters, so no subject to recognize")
    subject = params[0]
    required = tuple(sorted(e for e in effects if e[2] == subject))
    if not required:
        raise Abstained(f"{name}: nothing is written onto its subject {subject!r}. This looks like a "
                        "minting function, whose subject is a register. ugm now names a minted register "
                        "as a '$'-prefixed subject, so the join is NOT lost upstream — but `strider` "
                        "looks for its subject among the PARAMETERS, so this refusal is our restriction "
                        "rather than the engine's. Author a pattern as a CAST "
                        "(see strider/rules/patterns.mf), or lift that restriction deliberately.")
    return subject, required


def construct(lib: Library, name: str, **parts):
    """Build an instance by CALLING the pattern. Returns the new node.

    The subject is minted here rather than by the pattern, which is finding #1 turned into an API: the
    pattern must be a cast to stay readable, so somebody has to supply its subject, and that somebody is
    the consumer. The minted node's kind is the pattern's declared return type."""
    subject, _required = pattern_of(lib, name)
    params, _program = function.load(lib.graph, name)
    expected = set(params) - {subject}
    if set(parts) != expected:
        raise TypeError(f"{name}() wants {sorted(expected)}, got {sorted(parts)}")
    node = lib.graph.mint(function.returns_of(lib.graph, name) or name)
    function.invoke(lib.graph, name, {subject: node, **parts})
    return node


def recognize(lib: Library, node, name: str) -> dict | None:
    """Is `node` an instance of this pattern? Returns the bindings, or `None` for an honest refusal."""
    _subject, required = pattern_of(lib, name)
    g = lib.graph
    # ⚠ THE ONE PLACE the partial rule is enforced. `strider.intake` marks a node partial when it contains
    # a construct we could not model. Recognizing one would hand a consumer a description that is missing
    # something it has no way to ask about — a `for` loop understood by two-thirds of its body, presented
    # as a complete iteration. Same shape as abstaining on an incomplete effect set: an incomplete
    # description must not be matched, whichever end the incompleteness came from.
    if g.attr(node, "partial"):
        return None
    bindings: dict = {}
    for kind, label, _subj, obj in required:
        if kind == "link":
            targets = g.targets(node, label)
            if not targets:
                return None
            if obj is not None:
                bindings[obj] = targets[0]
        elif kind == "attr":
            if g.attr(node, label) is None:
                return None
    return bindings


def recognizes(lib: Library, node) -> dict:
    """⭐ **What IS this?** — every pattern the node satisfies, with its bindings.

    The bottom-up direction, and it mirrors `types.recognize`, which ugm added for the same reason on the
    same day: every entry point was top-down. The two are complementary rather than redundant, and the
    difference is worth stating because it is the whole reason this layer exists. `types.recognize` asks
    which declared SCHEMAS a node satisfies — and a schema is `{label: (kind, count)}`, flat, with no way
    to say that two of its edges land on related nodes. This asks which authored DESCRIPTIONS it
    satisfies, and a description carries the join.

    **Multi-pattern falls out**, the same way multi-type does for them: these are independent structural
    predicates, so of course a node can be several things at once.

    ⚠ A pattern that cannot be read is SKIPPED, not silently treated as unmatched — the two are different
    answers and conflating them would hide a broken pattern behind a plausible negative."""
    # ⚠ `lib.patterns`, NOT `lib.names`. A bridge writes the edges it would then match, so recognizing a
    # node as one reports our own intention back to us — no information, and actively misleading next to
    # the real recognitions. See `strider/library.py` for why the file is what draws the line.
    out = {}
    for name in lib.patterns:
        try:
            got = recognize(lib, node, name)
        except Abstained:
            continue
        if got is not None:
            out[name] = got
    return out


def unreadable(lib: Library) -> dict:
    """Which patterns cannot be read, and why. The honest companion to `recognizes` skipping them.

    A library where this is non-empty is not broken — `establishes` is conservative and some legitimate
    body will defeat it — but it IS a library with dark corners, and a consumer deserves to be told which
    rather than discovering it as a silent non-match."""
    out = {}
    for name in lib.names:                      # bridges included: a dark bridge matters just as much
        try:
            pattern_of(lib, name)
        except Abstained as exc:
            out[name] = str(exc)
    return out
