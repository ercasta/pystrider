"""STRIDER — pystrider rewritten on `../ugm`'s microfunctions engine.

A new folder beside `pystrider/`, mirroring what ugm itself did when `microfunctions/` superseded `ugm/`:
nothing is deleted, and both run side by side until the new one has earned the old one's ground.

**Why a rewrite rather than a port.** The old engine's execution model was pattern matching, and
pystrider's central bet rode on it — one authored description read as a rule BODY recognizes a construct,
read as a rule HEAD constructs one. The new engine deletes pattern matching: a microfunction is an
imperative program *pointed at* its arguments, and a pointed program cannot be run backwards. So the bet
needed a new home rather than a translation.

**It has one.** `experiments/microfunction_pattern.py` (slice 0) established that `driver.establishes` —
which reads what a function could make true *off its stored body* — carries the shared-variable join the
bet needs. The duality moves from `body/head of a rule` to `body/effects of a function`, and gains
something on the way: an authored description can no longer drift from what it does, because it *is* what
it does.

**The bar for deleting `pystrider/`.** Not "the tests pass" — the old suite is the only oracle for whether
this does what that did, so it stays. The bar is the reach measurement: 21/21 in-closure specs shipped and
15/15 out-of-closure refused BY NAME, predicted in advance. A raw pass rate measures only which specs we
chose.

**Two findings from slice 0 that constrain everything here** (pinned in
`tests/test_microfunction_pattern.py`, reasoned in that module's docstring):

1. **Patterns are authored as CASTS, never as minting functions — and the REASON changed on 2026-07-31.**

   Originally this was forced: `NEW` put the subject in a register, a register was not a parameter, so a
   minting pattern's effects came back with no subject at all. We reported it, and ugm fixed it — a
   minted register is now a `$`-prefixed local subject, so the join survives either way. Their note: it
   *"forced patterns to be authored as casts, which is a real expressive loss"*. Correct, and the loss is
   now optional.

   **We keep casts anyway, for a different and better reason: a cast can be applied to a node that
   ALREADY EXISTS.** That is precisely what lifting needs. `strider.intake` mints a `for_stmt` carrying
   `from_code`, `origin` and `source_line`; a bridge casts *that very node* into the neutral vocabulary,
   so what gets recognized afterwards is the artifact. A minting pattern would build a fresh node and the
   provenance would be left behind on the original — and provenance is the whole reason a check about
   code is stronger than a check about our intentions.

   So: readability no longer decides this; **applicability to existing nodes does.** Recorded because the
   old reason is now wrong, and a rule kept for a reason that has evaporated is a rule that gets deleted
   by the next person who checks.

2. **Recognition abstains where ranking over-approximates.** `establishes` is built to order candidates
   and is conservative by design; an incomplete effect set is safe there and a false-positive generator
   here. Same value, opposite safety.

3. **⚠ The neutral labels live in two files, and that is checked rather than trusted.** `patterns.mf`
   declares them; `python.mf`'s bridges write them. A bridge *ought* to delegate — `INVOKE` the pattern
   instead of restating its labels — but `INVOKE` takes a dict of parameter bindings and the `.mf`
   surface has no dict literal, so it cannot say which pattern parameter each register fills. Until it
   can, `strider.lift.vocabulary_drift` derives both sides from the stored bodies and names any label a
   bridge writes that no pattern reads. Pinned empty.
"""
from .intake import Intaken, intake
from .library import Library, load
from .emit import CannotEmit, emit
from .lift import bridges, lift, lower
from .patterns import Abstained, construct, pattern_of, recognize, recognizes

__all__ = ["Library", "load", "intake", "Intaken", "lift", "lower", "bridges", "emit", "CannotEmit",
           "Abstained", "construct", "pattern_of", "recognize", "recognizes"]
