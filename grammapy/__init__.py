"""grammapy — generate software from deviations-from-default.

See docs/vision.md for the design and docs/rest-domain.md for the first domain's
decision points. This package is being built following the roadmap in the README;
right now it covers the channel-type substrate and the disjoint-writes check
(roadmap step 3, first slice).
"""

from grammapy.channels import Channel, Footprint, WriteConflict, disjoint_writes
from grammapy.combinators import Accumulate, Choice, Scope, Fold, CompositionError, Item
from grammapy.guards import (
    ABSENT, Guard, GuardedProduction,
    GuardOverlap, GuardGap, GuardUnknownValue, guard_coverage,
)
from grammapy.scope import ScopeNode, Unhandled, unhandled_emissions
from grammapy.lattice import Lattice, FoldItem, UnknownVerdict
from grammapy.resolution import (
    Production, DecisionPoint, Forced, Defaulted, Surfaced, Rejected, resolve,
)

__all__ = [
    "Channel",
    "Footprint",
    "WriteConflict",
    "disjoint_writes",
    "Accumulate",
    "Choice",
    "Scope",
    "CompositionError",
    "Item",
    "ABSENT",
    "Guard",
    "GuardedProduction",
    "GuardOverlap",
    "GuardGap",
    "GuardUnknownValue",
    "guard_coverage",
    "ScopeNode",
    "Unhandled",
    "unhandled_emissions",
    "Fold",
    "Lattice",
    "FoldItem",
    "UnknownVerdict",
    "Production",
    "DecisionPoint",
    "Forced",
    "Defaulted",
    "Surfaced",
    "Rejected",
    "resolve",
]
