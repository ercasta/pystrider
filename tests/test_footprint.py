"""Pins for the productized footprint synthesis (pystrider.footprint).

This is the package-level test of the analysis↔composition join: deriving a fragment's write footprint
from its code, so grammapy's checks reason over the code, not a hand-declared label. These pins hold the
module's public contract: (1) an honest fragment's static and dynamic oracles agree; (2) static is
branch-complete; (3) dynamic resolves a computed key static cannot; (4) the union is the sound footprint,
each oracle covering the other's blind spot; (5) a bare local is not a channel; and (6) the derivation is
importable straight off the package (`pystrider.footprint_of`).
"""
import pystrider
from pystrider.footprint import footprint_of, static_writes, dynamic_writes, CodeFootprint


def test_honest_fragment_oracles_agree():
    fp = footprint_of("out['scaled'] = x * 2")
    assert isinstance(fp, CodeFootprint)
    assert fp.agree and fp.writes == frozenset({"out.scaled"})


def test_static_is_branch_complete():
    assert static_writes("if x < 0:\n    out['neg'] = 1\nelse:\n    out['pos'] = 1") == frozenset(
        {"out.neg", "out.pos"})


def test_dynamic_resolves_a_computed_key():
    src = "k = 'total'\nout[k] = x"
    assert static_writes(src) == frozenset({"out.<computed>"})   # static can't name it
    assert dynamic_writes(src) == frozenset({"out.total"})       # execution resolves it


def test_union_is_sound_each_oracle_covers_the_other():
    branch = footprint_of("if x < 0:\n    out['neg'] = 1\nelse:\n    out['pos'] = 1", x=5)
    assert branch.dynamic_missed == frozenset({"out.neg"})       # dynamic missed the untaken arm
    assert branch.writes == frozenset({"out.neg", "out.pos"})    # union recovers it
    computed = footprint_of("k = 'total'\nout[k] = x")
    assert computed.static_unresolved == frozenset({"out.<computed>"})
    assert computed.writes == frozenset({"out.total"})           # resolved; placeholder dropped


def test_a_bare_local_is_not_a_channel():
    # only shared-store subscript writes are channels; a local binding is not a footprint write.
    assert footprint_of("y = x * 2\nout['scaled'] = y").writes == frozenset({"out.scaled"})


def test_importable_off_the_package():
    assert pystrider.footprint_of("out['a'] = 1").writes == frozenset({"out.a"})
