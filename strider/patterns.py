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
        raise Abstained(
            f"{name}: nothing is written onto its subject {subject!r}, so there is no description here. "
            "Two ways that happens, and they are different: it MINTS its subject (a `NEW` puts it in a "
            "register — ugm names those `$`-prefixed now, so the join survives upstream and this "
            "refusal is `strider` looking for a PARAMETER), or it writes through a NAVIGATED register "
            "(`GET` then `SET`), whose role `establishes` cannot yet recover at all — the open half of "
            "docs/feedback_microfunctions.md §2. A pattern must be a CAST onto its subject; an "
            "operation need not be a description at all.")
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


def unreadable(lib: Library, *, describing_only: bool = True) -> dict:
    """Which functions cannot be read as descriptions, and why — the honest companion to `recognizes`
    skipping them.

    **⚠ `describing_only` defaults to True, and the default is the point.** A *pattern* that cannot be
    read is a defect: it is a description that describes nothing, and it will look exactly like a node
    that failed to match. A *bridge* likewise has to stay legible, since `vocabulary_drift` reads it. An
    **operation** is neither — `lower_threshold` navigates to the constant and writes there, so nothing
    lands on its declared subject and it has no description to give. That is not a dark corner; it is an
    action, and actions are not descriptions.

    Pass `describing_only=False` to see everything, which is how the distinction was found: the first
    version scanned all three categories, and adding the first operation turned a green pin red for a
    reason that was not a problem."""
    considered = (lib.patterns + lib.bridge_names) if describing_only else lib.names
    out = {}
    for name in considered:
        try:
            pattern_of(lib, name)
        except Abstained as exc:
            out[name] = str(exc)
    return out
