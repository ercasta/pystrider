"""The seam between a DURABLE, stable-keyed fact and a live entity id.

    entity = resolve_function(w, "demo.py", "classify")   # -> Entity, or None

Nothing durable may hold a raw entity id minted by `intake.py` — see that
module's own transient-marking block, and `loopingrules.world.transient`'s
docstring for the full argument: an id from one `intake()` means nothing
once the file is re-read, and "thinking about" a rewritten version of a
program has ids that were never real to begin with. What a durable fact
holds instead is a STABLE KEY. For code, that is `(origin path, function
name)` here — the first concrete instance, per this project's own "do one
concretely first" rule (`docs/TODO.md`, thread 1) — resolved back to a
live entity ONLY where the actual work happens, through this module.

⚠ The key is `(path, name)`, not `(path, qualname)` — `intake.py` does not
compute a dotted qualified name for a nested `def` yet, so two functions
sharing a name in different scopes of the SAME file are not disambiguated
here; `_find_function` answers whichever sorts first (entity id order).
Named honestly rather than silently papered over: extending the key to a
real qualname, once something needs one, is new work in `intake.py`
(attaching a component alongside `Function` with the dotted path) — not a
change to the shape below.

⚠ No staleness detection. `resolve_function` treats "this path already has
SOME entities in `w`" as "trust it, don't reread" — it has no way to tell
an intake that is merely OLD from one that is simply true, because nothing
here checks the file's mtime or hash against what `w` holds. A caller who
knows the file changed calls `reread`/`forget` explicitly; this only fills
in a path nothing has ever read (or that was explicitly forgotten). Real,
separate work if a rule ever needs "notice the file moved under me" for
itself.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from loopingrules.world import Entity, World

from .intake import Function, Intaken, Origin, intake


def forget(w: World, path: str) -> int:
    """Destroy every entity this world knows from `path` — every entity
    `intake()` ever mints carries `Origin(path)` (see `intake.py`'s own
    transient-marking block), so that is the whole of what "everything
    about this file" means today. Returns how many entities were
    destroyed. Safe to call on a path nothing has read yet — `0`, then.

    ⚠ This is `docs/TODO.md` thread 2's `forget(w, path)`, in its
    scoped-down form: it only ever touches entities `Origin` names, which
    is everything there is right now, because nothing durable exists yet
    that would ALSO need sweeping when a file goes away. The day some
    domain's own durable, stable-keyed fact needs to react to a forget
    too, that domain writes its own sweep — this function still isn't the
    place for it, the same way it was never `loopingrules.World`'s to
    know either (see `loopingrules.world.transient`'s own docstring).
    """
    path = os.path.expanduser(path)
    stale = [entity for entity, origin in w.each(Origin) if origin.value == path]
    for entity in stale:
        w.destroy(entity)
    return len(stale)


def reread(w: World, path: str) -> Tuple[Intaken, str]:
    """Forget everything this world knows from `path`, then `intake()` it
    again — the whole of what "stale" means for code-derived facts today.
    Returns `(Intaken, source)` — the source text too, so a caller that
    also wants it (a round-trip check, say) does not read the file twice.

    `OSError` propagates uncaught, same as `open()`'s own — a caller that
    wants to report "cannot read X" rather than crash catches it itself,
    the same as `pystrider.domain._read` already does.
    """
    path = os.path.expanduser(path)
    forget(w, path)
    source = open(path, encoding="utf-8").read()
    return intake(source, w, path), source


def resolve_function(w: World, path: str, name: str) -> Optional[Entity]:
    """The live `Function` entity currently answering to the stable key
    `(path, name)`.

    Re-`intake()`s `path` first, exactly once, if `w` holds NOTHING from
    it yet (see the module docstring's ⚠ on why "nothing yet" is the only
    case this rereads for, not "no function of that name yet either" —
    the second is a real, stable answer, not staleness, and rereading on
    every miss would turn a rule that calls this every tick into a disk-
    read storm that never settles). `None` if `path` genuinely has no
    function of that name, even once read. `OSError` propagates if `path`
    cannot be read at all — same as `reread`'s.
    """
    path = os.path.expanduser(path)
    found = _find_function(w, path, name)
    if found is not None:
        return found
    if not any(origin.value == path for _entity, origin in w.each(Origin)):
        reread(w, path)
        found = _find_function(w, path, name)
    return found


def _find_function(w: World, path: str, name: str) -> Optional[Entity]:
    for entity, origin, fn in w.each(Origin, Function):
        if origin.value == path and fn.name == name:
            return entity
    return None
