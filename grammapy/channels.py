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


# --- WILDCARD channels: a write that names no single key ---------------------------------------------
# A footprint derived from CODE cannot always name the key a write lands on. `pystrider.footprint`
# reports two such channels, and they mean the same thing here: SOME UNKNOWN KEY of that store.
#   * ``<store>.<items>``    — a whole-container mutation (``out.update(d)`` / ``lst.append(x)``): a
#                              list/set has no key to name, and a non-literal dict update could set ANY.
#   * ``<store>.<computed>`` — a subscript whose key the static oracle could not resolve (``out[k] = …``).
# Treating such a channel as an ordinary opaque NAME is silently UNSOUND: `out.<items>` would not
# string-match `out.total`, so a composition where one item does `out['total'] = …` and another does
# `out.update({'total': 99})` is certified disjoint while the second CLOBBERS the first at runtime.
# The sound reading is a WILDCARD over its store: it conflicts with any write by a distinct item to the
# SAME store. That over-approximates (the update might not touch `total`) — which is the safe direction
# for a frame rule: it may flag a maybe-collision, it may never miss a real one.
_WILDCARD_KEYS = ("<items>", "<computed>")


def _store_and_key(channel: Channel) -> "tuple[str, str] | None":
    """Split a ``<store>.<key>`` channel NAME into its parts. Returns None for a channel that is not
    store-qualified (a plain channel name owns no store, so store-wildcard reasoning does not apply to
    it). Reads ``.name``, never ``str(ch)`` — the latter carries the type suffix."""
    store, sep, key = channel.name.rpartition(".")
    return (store, key) if sep else None


# The frame rule as a CNL rule-module. TWO ways a channel is in conflict:
#   1. EXACT     — two distinct items write the same channel.
#   2. WILDCARD  — an item writes a wildcard channel of some store, and a distinct item writes ANY
#                  channel of that same store (including the wildcard itself, or another wildcard).
# `?a != ?b` is the distinctness condition honoured by the join (ugm feedback #11) — without it this
# self-joins and over-fires on any single writer. This IS the soundness verdict (the collapse into CNL):
# both readings are rules over the write facts, not Python set arithmetic.
_DISJOINT_WRITES_RULE = (
    "?c write_conflict yes when ?a writes ?c and ?b writes ?c and ?a != ?b\n"
    "?c write_conflict yes when ?a writes ?c and ?c is_wildcard yes and ?c in_store ?s "
    "and ?b writes ?d and ?d in_store ?s and ?a != ?b"
)


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

    A **wildcard** channel (``<store>.<items>`` / ``<store>.<computed>`` — a write whose key is not
    nameable, see `_WILDCARD_KEYS`) conflicts with every write by a distinct item to the same store,
    not just with a string-equal channel. That is the difference between admitting and catching a
    whole-container mutation that clobbers a keyed write.
    """
    items = list(items)
    facts = [(label, "writes", str(ch)) for label, fp in items for ch in fp.writes]
    known = {str(ch) for _, fp in items for ch in fp.writes}
    # structural facts about a channel NAME (mechanism at the fact boundary, not reasoning): which store
    # it belongs to, and whether its key is a wildcard. The rule does the reasoning over them.
    stores: dict[str, str] = {}
    for _, fp in items:
        for ch in fp.writes:
            parts = _store_and_key(ch)
            if parts is None:
                continue
            store, key = parts
            stores[str(ch)] = store
            facts.append((str(ch), "in_store", store))
            if key in _WILDCARD_KEYS:
                facts.append((str(ch), "is_wildcard", "yes"))
    answers = derive(facts, _DISJOINT_WRITES_RULE, "who write_conflict yes")
    conflicted = {a.split(" ", 1)[0] for a in answers if a.split(" ", 1)[0] in known}

    # reconstruct pairwise conflicts (the first writer vs each later one) for the message, preserving
    # input order and the Channel object (which carries the type) — reporting, not the verdict.
    writers: dict[str, list[str]] = {}
    channel_of: dict[str, Channel] = {}
    store_writers: dict[str, list[str]] = {}
    for label, fp in items:
        for ch in fp.writes:
            if str(ch) in stores:
                bucket = store_writers.setdefault(stores[str(ch)], [])
                if label not in bucket:
                    bucket.append(label)
            if str(ch) in conflicted:
                channel_of[str(ch)] = ch
                bucket = writers.setdefault(str(ch), [])
                if label not in bucket:
                    bucket.append(label)
    reported: list[WriteConflict] = []
    for name, ws in writers.items():
        # a conflicted wildcard collides with every distinct writer of its store, which — unlike the
        # exact case — need not write the wildcard channel itself, so the pairing widens to the store.
        others = (store_writers[stores[name]]
                  if channel_of[name].name.rpartition(".")[2] in _WILDCARD_KEYS else ws)
        reported += [WriteConflict(channel_of[name], ws[0], o) for o in others if o != ws[0]]
    return reported
