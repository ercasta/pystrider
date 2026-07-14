"""Typed channels and footprints — the substrate every combinator composes through.

A ``Channel`` is a ``(name, type)`` pair (vision.md §3.1). A ``Footprint`` is the set
of channels a nonterminal or atom ``reads``/``writes`` plus the control signals it
``emits`` (§3.2). Composition safety is decided entirely from footprints, so this is
the load-bearing declaration in the system.

Types are placeholders for now: the type/channel-compatibility rules are deliberately
deferred (docs/language.md §9), so ``type`` is a free-form string and channel identity
is ``(name, type)``. When the type system lands, only ``Channel`` changes here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from grammapy._cnl import derive

__all__ = ["Channel", "Footprint", "WriteConflict", "disjoint_writes"]


@dataclass(frozen=True)
class Channel:
    """A named, typed unit of data interaction. Identity is ``(name, type)``."""

    name: str
    type: str = "?"  # placeholder until the type system lands (language.md §9)

    def __str__(self) -> str:
        return self.name if self.type == "?" else f"{self.name}:{self.type}"


@dataclass(frozen=True)
class Footprint:
    """What a piece of the derivation reads, writes, and emits (vision.md §3.1–§3.2).

    ``reads``/``writes`` are channels; ``emits`` are control-signal names ranked in a
    severity order (§3.2). Footprints are *declared* at atom leaves and *synthesized*
    at internal nodes (§11.3) — this class carries the declaration; synthesis lands
    with the derivation engine (roadmap step 4).
    """

    reads: frozenset[Channel] = field(default_factory=frozenset)
    writes: frozenset[Channel] = field(default_factory=frozenset)
    emits: frozenset[str] = field(default_factory=frozenset)

    @staticmethod
    def of(
        *,
        reads: Iterable[Channel] = (),
        writes: Iterable[Channel] = (),
        emits: Iterable[str] = (),
    ) -> "Footprint":
        """Build a Footprint from any iterables (convenience over frozenset() calls)."""
        return Footprint(frozenset(reads), frozenset(writes), frozenset(emits))


@dataclass(frozen=True)
class WriteConflict:
    """Two items write the same channel — the disjointness violation (vision.md §3.4).

    Carries everything a good rejection message needs (roadmap step 3): the shared
    channel and the labels of both offending items.
    """

    channel: Channel
    left: str
    right: str

    def __str__(self) -> str:
        return (
            f"channel `{self.channel}` is written by both "
            f"`{self.left}` and `{self.right}`"
        )


# The frame rule as a CNL rule-module: a channel is a conflict iff TWO DISTINCT items write it.
# `?a != ?b` is the distinctness condition honoured by the join (ugm feedback #11) — without it this
# self-joins and over-fires on any single writer. This IS the soundness verdict (the collapse into CNL).
_DISJOINT_WRITES_RULE = "?c write_conflict yes when ?a writes ?c and ?b writes ?c and ?a != ?b"


def disjoint_writes(items: Iterable[tuple[str, Footprint]]) -> list[WriteConflict]:
    """The frame rule, made operational (vision.md §3.1, §7.4).

    Given labelled items, return every write-channel collision between distinct items.
    Empty list ⇒ the items compose by disjoint footprint. This is the single check
    shared by REST decision points 4, 5, 7, and 9 (docs/rest-domain.md §10).

    The soundness verdict — *which channels are written by two distinct items* — is a CNL rule
    (`_DISJOINT_WRITES_RULE`) evaluated read-only over the write facts (identity by label: two
    same-labelled items are one writer, so a lone item never self-conflicts). The pairwise
    ``WriteConflict`` list is then reconstructed from the same footprints for the human-facing
    rejection message. Order-independent by construction — the CNL join inspects unordered pairs.
    """
    items = list(items)
    facts = [(label, "writes", str(ch)) for label, fp in items for ch in fp.writes]
    known = {str(ch) for _, fp in items for ch in fp.writes}
    answers = derive(facts, _DISJOINT_WRITES_RULE, "who write_conflict yes")
    conflicted = {a.split(" ", 1)[0] for a in answers if a.split(" ", 1)[0] in known}

    # reconstruct pairwise conflicts (the first writer vs each later one) for the message, preserving
    # input order and the Channel object (which carries the type) — reporting, not the verdict.
    writers: dict[str, list[str]] = {}
    channel_of: dict[str, Channel] = {}
    for label, fp in items:
        for ch in fp.writes:
            if str(ch) in conflicted:
                channel_of[str(ch)] = ch
                bucket = writers.setdefault(str(ch), [])
                if label not in bucket:
                    bucket.append(label)
    return [WriteConflict(channel_of[name], ws[0], later)
            for name, ws in writers.items() for later in ws[1:]]
