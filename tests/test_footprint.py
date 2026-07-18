"""Pins for the productized footprint synthesis (pystrider.footprint).

This is the package-level test of the analysis↔composition join: deriving a fragment's write footprint
from its code, so grammapy's checks reason over the code, not a hand-declared label. These pins hold the
module's public contract: (1) an honest fragment's static and dynamic oracles agree; (2) static is
branch-complete; (3) dynamic resolves a computed key static cannot; (4) the union is the sound footprint,
each oracle covering the other's blind spot; (5) a bare local is not a channel; and (6) the derivation is
importable straight off the package (`pystrider.footprint_of`).
"""
import pystrider
from pystrider.footprint import footprint_of, static_writes, dynamic_writes, CodeFootprint, modelable


def test_honest_fragment_oracles_agree():
    fp = footprint_of("out['scaled'] = x * 2")
    assert isinstance(fp, CodeFootprint)
    assert fp.agree and fp.writes == frozenset({"out.scaled"})


def test_static_is_branch_complete():
    assert static_writes("if x < 0:\n    out['neg'] = 1\nelse:\n    out['pos'] = 1") == frozenset(
        {"out.neg", "out.pos"})


def test_dynamic_resolves_a_computed_key():
    src = "out['k' + str(x)] = 1"                                # the key DEPENDS on the input
    assert static_writes(src) == frozenset({"out.<computed>"})   # static can't name it
    assert dynamic_writes(src, x=5) == frozenset({"out.k5"})     # execution resolves it — for THIS input


def test_union_is_sound_each_oracle_covers_the_other():
    branch = footprint_of("if x < 0:\n    out['neg'] = 1\nelse:\n    out['pos'] = 1", x=5)
    assert branch.dynamic_missed == frozenset({"out.neg"})       # dynamic missed the untaken arm
    assert branch.writes == frozenset({"out.neg", "out.pos"})    # union recovers it
    computed = footprint_of("out['k' + str(x)] = 1", x=5)
    assert computed.static_unresolved == frozenset({"out.<computed>"})
    # the placeholder SURVIVES the resolved key: this run named `out.k5`, another input names another
    # key, so the wildcard is the only sound thing to carry forward.
    assert computed.writes == frozenset({"out.<computed>", "out.k5"})


def test_a_key_bound_to_a_literal_is_resolved_statically_not_guessed_from_a_run():
    # precision is recovered where it can be PROVEN: `k = 'total'` makes the key statically known, so it
    # never becomes a wildcard and the two oracles agree without the dynamic run licensing anything.
    fp = footprint_of("k = 'total'\nout[k] = x")
    assert fp.static == frozenset({"out.total"}) and fp.agree
    assert fp.static_unresolved == frozenset()
    # EVERY constant a name can hold is kept — a branch-complete over-approximation, never a pick.
    both = static_writes("if x < 0:\n    k = 'neg'\nelse:\n    k = 'pos'\nout[k] = 1")
    assert both == frozenset({"out.neg", "out.pos"})
    # one non-constant binding poisons the name back to the honest wildcard.
    assert static_writes("k = 'total'\nk = str(x)\nout[k] = 1") == frozenset({"out.<computed>"})
    assert static_writes("def f(k):\n    out[k] = 1") == frozenset({"out.<computed>"})   # a parameter
    assert static_writes("for k in ks:\n    out[k] = 1") == frozenset({"out.<computed>"})  # a loop target


def test_a_bare_local_is_not_a_channel():
    # only shared-store subscript writes are channels; a local binding is not a footprint write.
    assert footprint_of("y = x * 2\nout['scaled'] = y").writes == frozenset({"out.scaled"})


def test_importable_off_the_package():
    assert pystrider.footprint_of("out['a'] = 1").writes == frozenset({"out.a"})
    assert pystrider.modelable("out['a'] = 1")


def test_modelable_covers_subscripts_reads_and_known_methods():
    # analyzable: subscripts, reads, and KNOWN container methods (mutators + readers).
    assert modelable("out['a'] = x")
    assert modelable("out['a'] = 0\nout['a'] += x")
    assert modelable("if x < 0:\n    out['a'] = 1\nelse:\n    out['b'] = 2")
    assert modelable("out['a'] = out['b'] + 1")             # a read-modify-write is fine
    assert modelable("out.update({'a': 1})")               # a modeled dict mutator (literal keys -> out.a)
    assert modelable("out.setdefault('a', 1)")             # modeled
    assert modelable("lst = []\nlst.append(x)\nreturn lst")  # a modeled list mutator (-> lst.<items>)
    assert modelable("out['a'] = 1\nreturn out.get('a')")  # a reader is a safe read
    # un-analyzable store-escapes — each abstains (the honest-unknown membrane):
    assert not modelable("out.custom_mutate(x)")           # an UNKNOWN method — might mutate out of the model
    assert not modelable("out |= {'a': 1}")                # operator-mutation on the bare name
    assert not modelable("h(out)")                         # store passed to a callee
    assert not modelable("d = out\nd['a'] = 1")            # aliased
    assert not modelable("box = [out]\nbox[0]['a'] = 1")   # aliased through a container
    assert not modelable("out['a']['b'] = 1")              # chained subscript (writes the inner object)


def test_store_passed_to_a_local_helper_is_followed_exactly():
    # the inter-procedural slice: a store handed to an IN-VIEW helper is not an escape — it is followed
    # into the callee, mapping the store onto the callee's parameter (the write-side of session.link_calls).
    fp = footprint_of("def add_total(o):\n    o['total'] = x\nadd_total(out)")
    assert fp.modelable and not fp.unknown
    assert fp.writes == frozenset({"out.total"})


def test_following_a_helper_is_branch_complete_where_a_run_is_not():
    # a branch INSIDE the callee: the static follow sees BOTH arms; this input's run sees only one.
    fp = footprint_of("def fill(o):\n    if x < 0:\n        o['neg'] = 1\n    else:\n        o['pos'] = 1\nfill(out)", x=5)
    assert fp.dynamic == frozenset({"out.pos"})              # the taken arm only
    assert fp.writes == frozenset({"out.neg", "out.pos"})    # the follow recovers the untaken arm


def test_helper_following_chains_and_renames_through_each_hop():
    # out -> mid(y) -> leaf(z): the deep write is renamed z->y->out, no intermediate-param phantom leaks.
    fp = footprint_of("def leaf(z):\n    z['deep'] = 1\ndef mid(y):\n    leaf(y)\nmid(out)")
    assert fp.modelable and fp.writes == frozenset({"out.deep"})


def test_a_callee_that_itself_escapes_abstains():
    # following is EXACT, not blind: if the callee hands the store to an OPAQUE callee, the unknown
    # propagates back out as an honest abstention.
    assert not modelable("def bad(o):\n    h(o)\nbad(out)")   # inner h is opaque
    assert not modelable("h(out)")                            # a callee with no local def, unchanged


def test_helper_recursion_is_cycle_guarded():
    assert modelable("def rec(o):\n    o['a'] = 1\n    rec(o)\nrec(out)")


def test_unknown_footprint_is_flagged_and_refuses_trust():
    clean = footprint_of("out['scaled'] = x * 2")
    assert clean.modelable and not clean.unknown           # a plain subscript write is trusted

    opaque = footprint_of("d = out\nd['a'] = 1")           # the store written through an alias
    assert opaque.unknown and not opaque.modelable         # -> honest unknown
    # the raw writes may be an under-approximation, which is exactly why `unknown` must gate trust.
