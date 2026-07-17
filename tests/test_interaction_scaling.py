"""Pins for feature-interaction SCALING (experiments/interaction_scaling.py).

The §8 "understates the win" bullet, demonstrated on grammapy's real Accumulate frame rule and by running
the emitted programs. These pins hold: (1) the ledger diverges — author effort linear, interaction-audit
quadratic; (2) a disjoint library is clean at scale (no false positives); (3) an injected collision is
CAUGHT structurally regardless of F, and the author wrote no interaction code; (4) the naive additive
program silently CLOBBERS the shared slot at runtime; (5) a semantic interaction on disjoint slots is the
named boundary — invisible to Accumulate, owned by the second (execution) layer.
"""
from math import comb

from experiments.interaction_scaling import (
    Feature, feature, library, ledger, collisions, additive_dropped, semantic_conflicts,
)


def test_ledger_is_linear_author_quadratic_audit():
    for f in (2, 8, 32):
        L = ledger(f)
        assert L.author_lines == f                 # O(F): one bundle per feature
        assert L.audit_pairs == comb(f, 2)         # O(F^2): pairs that could clobber
    # the ratio strictly grows — the surfaces diverge, they don't track.
    ratios = [ledger(f).audit_pairs / ledger(f).author_lines for f in (4, 8, 16, 32)]
    assert ratios == sorted(ratios) and ratios[-1] > ratios[0]


def test_disjoint_library_is_clean_at_scale():
    # the well-designed library has no false positives, at any size — the check only fires on real sharing.
    assert collisions(library(2)) == []
    assert collisions(library(32)) == []


def test_injected_collision_is_caught_regardless_of_scale():
    for f in (8, 32):
        collider = Feature(f"feat_{f}_collides", ("slot_0",), "screen['slot_0'] = 'INTRUDER'")
        cs = collisions(library(f) + (collider,))
        assert len(cs) == 1                                     # exactly the one real conflict, not F of them
        assert str(cs[0].channel) == "slot_0"
        assert {cs[0].left, cs[0].right} == {"feat_0", f"feat_{f}_collides"}


def test_naive_additive_program_clobbers_at_runtime():
    # the bug additive hand-code ships: the second writer overwrites the first, a slot silently dropped.
    collider = Feature("feat_8_collides", ("slot_0",), "screen['slot_0'] = 'INTRUDER'")
    assert additive_dropped(library(8) + (collider,)) == {"slot_0"}


def test_semantic_interaction_is_the_named_boundary():
    guest = Feature("guest_checkout", ("slot_guest",), "screen['slot_guest'] = 'guest'",
                    incompatible_with=frozenset({"loyalty_account"}))
    loyalty = Feature("loyalty_account", ("slot_loyalty",), "screen['slot_loyalty'] = 'account'")
    pair = (guest, loyalty)
    assert collisions(pair) == []                              # disjoint slots -> Accumulate is blind
    assert semantic_conflicts(pair) == [("guest_checkout", "loyalty_account")]   # the other layer sees it
