"""Pins for footprint synthesis (experiments/footprint_synthesis.py).

The load-bearing gap: grammapy's checks reason over footprints, and a hand-DECLARED footprint is a
trusted input nothing checks. Deriving the footprint from the code closes it. These pins hold: (1) the
headline — a "footprint liar" is ADMITTED by declared-footprint Accumulate but REJECTED by
derived-footprint Accumulate; (2) static synthesis is branch-complete; (3) dynamic synthesis resolves
a computed key static cannot; (4) the two oracles' union is the sound footprint (each covers the
other's blind spot); and (5) `derived_item` is a drop-in grammapy Item built from the code.
"""
from grammapy import Accumulate, Item, Footprint, Channel, CompositionError

from experiments.footprint_synthesis import (
    static_writes, dynamic_writes, footprint_of, derived_item,
)


def _admits(items):
    try:
        Accumulate.check(items)
        return True
    except CompositionError:
        return False


def test_the_liar_is_admitted_by_declared_but_rejected_by_derived():
    # scale writes out.scaled; the liar DECLARES out.shifted but its code writes out.scaled too.
    scale_src, liar_src = "out['scaled'] = x * 2", "out['scaled'] = x + 10"
    declared = [Item("scale", Footprint.of(writes=[Channel("out.scaled")])),
                Item("liar", Footprint.of(writes=[Channel("out.shifted")]))]   # the human's claim
    derived = [derived_item("scale", scale_src), derived_item("liar", liar_src)]
    assert _admits(declared)             # declared footprints look disjoint -> WRONGLY admitted
    assert not _admits(derived)          # derived from the code -> the real collision is caught


def test_a_whole_container_write_that_clobbers_a_keyed_one_is_caught_end_to_end():
    """The wildcard leg of the same gap, derived from CODE and checked by the real Accumulate.

    Both fragments are perfectly honest and both are `modelable` — nothing here is a liar, and nothing
    abstains. The unsoundness was purely in the READING of the derived channels: `out.update(d)` derives
    the coarse `out.<items>`, which does not string-match the `out.total` the other fragment writes. The
    two compose "disjointly" and the second silently overwrites the first.
    """
    keyed, whole = "out['total'] = x", "data = {'total': 99}\nout.update(data)"
    assert footprint_of(whole).writes == frozenset({"out.<items>"})   # no key to name
    assert not footprint_of(keyed).unknown and not footprint_of(whole).unknown  # neither abstains

    # the collision is REAL: run them in sequence against one store and the keyed write is gone.
    store: dict = {}
    exec(keyed, {"out": store, "x": 1})
    exec(whole, {"out": store, "x": 1})
    assert store["total"] == 99                                      # `keyed` lost its write

    assert not _admits([derived_item("keyed", keyed), derived_item("whole", whole)])


def test_static_synthesis_is_branch_complete():
    src = "if x < 0:\n    out['neg'] = 1\nelse:\n    out['pos'] = 1"
    assert static_writes(src) == {"out.neg", "out.pos"}   # both arms, even the untaken one


def test_dynamic_synthesis_resolves_a_computed_key():
    src = "out['k' + str(x)] = 1"                         # the key DEPENDS on the input
    assert static_writes(src) == {"out.<computed>"}       # static can't name the key
    assert dynamic_writes(src, x=5) == {"out.k5"}         # execution resolves it — for THIS input


def test_union_is_the_sound_footprint_each_oracle_covers_the_other():
    branch = footprint_of("if x < 0:\n    out['neg'] = 1\nelse:\n    out['pos'] = 1", x=5)
    assert branch.dynamic_missed == frozenset({"out.neg"})     # dynamic missed the untaken branch
    assert branch.writes == frozenset({"out.neg", "out.pos"})  # union recovers it
    computed = footprint_of("out['k' + str(x)] = 1", x=5)
    assert computed.static_unresolved == frozenset({"out.<computed>"})
    # the run named the key it produced; the placeholder SURVIVES, because another input names another
    # key. Dropping it here would be the one under-approximating step in the derivation.
    assert computed.writes == frozenset({"out.<computed>", "out.k5"})


def test_honest_fragment_static_and_dynamic_agree():
    fp = footprint_of("out['scaled'] = x * 2")
    assert fp.agree and fp.writes == frozenset({"out.scaled"})


def test_derived_item_is_a_grammapy_item_over_the_real_writes():
    it = derived_item("scale", "out['scaled'] = x * 2")
    assert isinstance(it, Item)
    assert {str(c) for c in it.footprint.writes} == {"out.scaled"}
