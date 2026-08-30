"""Where things are — the observed/derived split, and one place to ask.

`intake.py`'s `node()` stamps a `Span` on every entity minted straight from a
real AST node — OBSERVED directly off `lineno`/`end_lineno`, nothing computed.
`Block` (intake's own synthetic body-of-statements entity, minted by `block()`)
has no AST node of its own, so it has no `Span` to observe one from.

⭐ This is `effects.py`'s recipe again: a forward fixpoint rule reading
structure `intake.py` already produced, same shape as `contains`. `block_span`
below derives a `Block`'s span from its `Stmt` children's own `Span`s — exact,
because it is a deterministic aggregate of already-observed data, but kept a
SEPARATE component (`DerivedSpan`, not `Span`) on purpose: a caller should
always be able to tell which kind of claim it is looking at, the same
discipline `SourceLine`'s docstring names for attribution generally.

`span_of` is the one place that distinction collapses back down for a caller
that just wants an answer — *where is this entity* — without needing to know
in advance whether it was observed or derived.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .intake import Block, Span, Stmt


@dataclass(frozen=True)
class DerivedSpan:
    """A `Block`'s span, DERIVED from its `Stmt` children — never itself
    observed off an AST node. See the module note on why this stays a
    separate component from `Span`."""

    start: int
    end: int


def block_span(w) -> None:
    """Every `Block`'s span, as the bracket of its `Stmt` children's spans.

    ⚠ Abstains (not `Partial` — silently absent) if any statement lacks a
    `Span` of its own, or the block is empty. An empty block has no lines to
    derive a span FROM; approximating one would be inventing a location no
    statement actually occupies.
    """
    for entity, _block in w.each(Block, without=DerivedSpan):
        stmts = w.get_all(entity, Stmt)
        if not stmts:
            continue
        child_spans = [w.get(s.entity, Span) for s in stmts]
        if any(span is None for span in child_spans):
            continue
        w.attach(entity, DerivedSpan(min(s.start for s in child_spans),
                                     max(s.end for s in child_spans)))


def span_of(w, entity: int) -> Optional[Union[Span, DerivedSpan]]:
    """Where `entity` is, whichever kind of claim answers it — `Span` if
    `intake.py` observed one directly, `DerivedSpan` if `block_span` computed
    one instead, `None` if neither rule has (yet, or ever will)."""
    observed = w.get(entity, Span)
    return observed if observed is not None else w.get(entity, DerivedSpan)


DESCRIPTIONS = {"block_span": block_span}


def install(loop, only=None) -> None:
    """Register the descriptions. `only` names a subset, for a control."""
    for name, make in DESCRIPTIONS.items():
        if only is None or name in only:
            loop.rule(make, name=f"spans.{name}")
