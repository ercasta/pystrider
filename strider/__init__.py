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

1. **Patterns are authored as CASTS, never as minting functions.** A `NEW` puts the subject in a register,
   and a register is not a parameter, so every effect comes back with its subject role lost — three orphan
   facts that no longer claim to describe one node. `as_iteration(it, seq, var, body)` keeps the join.
2. **Recognition abstains where ranking over-approximates.** `establishes` is built to order candidates
   and is conservative by design; an incomplete effect set is safe there and a false-positive generator
   here. Same value, opposite safety.
"""
from .intake import Intaken, intake
from .library import Library, load
from .lift import bridges, lift
from .patterns import Abstained, construct, pattern_of, recognize, recognizes

__all__ = ["Library", "load", "intake", "Intaken", "lift", "bridges",
           "Abstained", "construct", "pattern_of", "recognize", "recognizes"]
