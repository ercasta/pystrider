"""`Denotation` — a stable, resolvable PATH to a live entity, carrying no
raw id of its own. The seam `pystrider.evaluation`'s receipts stand on:
nothing durable may hold a raw entity id (`pystrider.resolve`'s own ⚠,
unchanged premise, generalized here past "a whole function" to "any part
of one").

A `Denotation` is one of:

* `Root(path, qualname)` — `pystrider.resolve.resolve_function`'s own
  stable key, unchanged, wrapped so it composes with `Step` below.
* `Step(parent, label, index=None)` — one hop from an already-denoted
  entity, through the SAME label vocabulary `intake.py`'s own `part()`
  calls use (`intake.PARTS` — never a second vocabulary invented here).
  `index=None` reads through `World.get` — fine for a single-valued label,
  or a multi-valued one that HAPPENS to hold exactly one part right now,
  and it raises `ValueError` (uncaught, propagating) the moment two or
  more exist, the SAME "no guessing between several" `World.get` already
  enforces everywhere else — this module invents no separate rule for it.
  `index=N` reads through `World.get_all`, positionally — the only way to
  pick one of several on purpose.

⚠⚠ `locate` NEVER caches, NEVER mutates `w`, and a miss is not an error —
same posture every resolver in this repo takes (`pystrider.resolve`'s
own). Nothing here decides whether a miss means "stale" or "never
existed"; that judgment belongs to whoever asked (`pystrider.evaluation`'s
receipts, so far — see its own module note on why NEITHER a hit nor a
miss is trusted without a fresh re-derivation on top).

⚠ `Denotation` instances are plain, nested Python objects — NOT something
`loopingrules.World` can hold in a component field directly (`world._lower`
only accepts primitives/`Entity`/list/dict/tuple of those; a `Root`/`Step`
is neither). `encode`/`decode` are the codec, the same posture
`intake.encode_literal`/`decode_literal` already takes for `Constant`'s
own payload: a value codec, not an identity table, and nothing about it
needs the world at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

from . import resolve
from .intake import PARTS


@dataclass(frozen=True)
class Root:
    path: str
    qualname: str


@dataclass(frozen=True)
class Step:
    parent: "Denotation"
    label: str
    index: Optional[int] = None


Denotation = Union[Root, Step]


def locate(w, denotation: Denotation) -> Optional[int]:
    """The live entity id `denotation` currently names, or `None` if it
    cannot be reached right now — through a dead parent, an unmodelled
    label, or an out-of-range index. Recurses through `Step.parent`,
    bottoming out at `Root` through `resolve.resolve_function` (which may
    reread the denoted path exactly once, its own rule, unchanged here).

    ⚠ A bare (`index=None`) step into a label currently holding SEVERAL
    parts raises `ValueError`, uncaught — `World.get`'s own refusal to
    guess, not a `None` miss like every other failure here. A caller
    denoting into a multi-valued label always supplies `index`.
    """
    if isinstance(denotation, Root):
        found = resolve.resolve_function(w, denotation.path, denotation.qualname)
        return found.id if found is not None else None
    parent = locate(w, denotation.parent)
    if parent is None:
        return None
    label_cls = PARTS.get(denotation.label)
    if label_cls is None:
        return None
    if denotation.index is None:
        part = w.get(parent, label_cls)
        return part.entity if part is not None else None
    parts = w.get_all(parent, label_cls)
    if denotation.index < 0 or denotation.index >= len(parts):
        return None
    return parts[denotation.index].entity


def encode(denotation: Denotation) -> Tuple:
    """`denotation`, as the nested tuple-of-primitives a component field
    may actually hold — the inverse of `decode`."""
    if isinstance(denotation, Root):
        return ("root", denotation.path, denotation.qualname)
    return ("step", encode(denotation.parent), denotation.label, denotation.index)


def decode(payload: Tuple) -> Denotation:
    """The `Denotation` a `component field`'s stored tuple encodes — the
    inverse of `encode`. `ValueError`, not a crash on a bad index, if the
    tuple's own shape tag is neither — a payload this codec did not write
    is a data problem to name, not a silent guess."""
    kind = payload[0]
    if kind == "root":
        _tag, path, qualname = payload
        return Root(path, qualname)
    if kind == "step":
        _tag, parent_payload, label, index = payload
        return Step(decode(parent_payload), label, index)
    raise ValueError("not a denotation: %r" % (payload,))
