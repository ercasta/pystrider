"""`Evaluation` — a timestamped RECEIPT that some analysis derived some
value about a `Denotation`, at some wall-clock moment. Durable on purpose
(unlike everything `intake.py` mints): it refers to its subject through a
`Denotation`, never a raw entity id (`pystrider.denotation`'s own codec —
`encode`/`decode` — is what makes that storable at all), so it survives a
reread/forget the way any other tier-1 fact does (`pystrider.resolve`'s own
tier split, `docs/TODO.md`).

⭐⭐ **A RECEIPT, NEVER A CACHE — THIS IS THE TMS ANSWER.** Nothing here is
ever trusted without re-deriving fresh first: `current`, below, is the ONLY
thing in this module that certifies a stored `Evaluation` still holds, and
it does so by calling the analysis AGAIN, against `denotation`'s LIVE
entity, and comparing — never by trusting the stored `value` on its own. A
stale `Evaluation` is not a bug to catch; it is an accurate historical
record of what WAS true, stamped with WHEN. This sidesteps the alternative
(the standing-annotation cache in `pystrider.symbolic`, which had to be
taught to rebuild every tick once `repair.py`'s in-place `w.replace` was
found to leave it stale — see that module's own note) by simply never
caching in the first place: a receipt costs nothing to leave lying around
once wrong, because reading one always re-checks.

⚠ Compare `evaluator.Evaluated`, which took the opposite, accumulate-forever
answer to a related-looking problem (a repair's before-and-after both have
to stand as evidence) for a reason specific to ITS use, not this one. This
module generalizes the RECEIPT half only; nothing stops a caller from
minting many `Evaluation`s for one denotation over time and reading the
whole history (`w.each(Evaluation)`, filtered by `denotation`/`kind`), but
nothing here optimizes for that either — it is one `record`/`current` pair,
not a history API.

⚠ `at` is a plain wall-clock `float` (`time.time()`), not `world.revision` —
`revision` is GLOBAL, moving on every change anywhere in `w`, so comparing
it to one subject's own last change is not answerable without a per-entity
stamp nothing in `loopingrules.World` keeps today. A wall clock needs no new
engine primitive to mean "when."
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from loopingrules.world import Entity

from .denotation import Denotation, decode, encode, locate
from .intake import encode_literal


@dataclass(frozen=True)
class Evaluation:
    """`kind` names WHICH analysis produced this (`"known_value"`, so far)
    — one denotation may accumulate readings from several analyses over
    time, and a reader must not have to guess which one wrote a given row.
    `denotation` is the ENCODED form (`denotation.encode`) — a component
    field cannot hold a `Root`/`Step` object directly, see that module's
    own ⚠. `value` is `repr`-encoded, same codec as `intake.Constant.literal`.
    """

    denotation: tuple
    kind: str
    value: str
    at: float


def record(w, denotation: Denotation, kind: str, value: Any) -> Entity:
    """Mint a receipt: `kind` derived `value` about `denotation`, as of
    right now. Does NOT check whether `denotation` currently resolves, or
    whether `value` is what a fresh derivation would produce — a receipt
    RECORDS a claim, it does not vouch for it; `current` is the only thing
    here that vouches for anything."""
    return w.spawn(Evaluation(encode(denotation), kind, encode_literal(value), time.time()))


def current(w, evaluation: Evaluation,
           deriver: Callable[[Any, int], Optional[Any]]) -> bool:
    """Is this receipt STILL what a fresh derivation says, right now?

    `deriver(w, entity)` — `pystrider.symbolic.fold`, so far — is called
    against `evaluation.denotation`'s LIVE entity, never against the
    receipt's own stored `value`. `False` covers every way a receipt can be
    out of date, deliberately without distinguishing them here: the
    denotation no longer resolves (the file was edited out from under it,
    the path was forgotten), the deriver now abstains (`None`), or it
    disagrees. A caller that needs to tell those apart calls `locate`/
    `deriver` directly instead of this.
    """
    subject = locate(w, decode(evaluation.denotation))
    if subject is None:
        return False
    fresh = deriver(w, subject)
    if fresh is None:
        return False
    return encode_literal(fresh) == evaluation.value
