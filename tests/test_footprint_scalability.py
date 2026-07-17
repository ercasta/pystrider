"""Pins for the footprint scalability sweep (experiments/footprint_scalability.py).

The highest-information scalability finding: the derivation stays sound on self-contained subscript
fragments but SILENTLY MISSES writes on common real-code constructs (method mutation, aliasing) — and an
abstention detector (`modelable`) converts every silent miss into an honest-unknown. These pins hold the
finding so a regression (a construct newly silently-unsound, or the abstention no longer catching one) is
caught. Scalability = derive-what-you-can + know-when-you-can't.

A store passed to a LOCAL helper is no longer a silent miss NOR an abstention: it is FOLLOWED into the
callee exactly (the inter-procedural slice), so `helper_taken`/`helper_untaken` derive EXACTLY — including
the helper called on an UNTAKEN branch, which static following catches (branch-complete) where a runtime
observation never would.
"""
from experiments.footprint_scalability import CASES, classify, modelable, abstaining_verdict

_BY_LABEL = {c.label: c for c in CASES}
# the constructs that escape BOTH oracles with no uncertainty signal — the fatal class. (update/setdefault
# are MODELED as dict writes; the helper cases are now FOLLOWED into the local callee — so only aliasing,
# genuinely out of the subscript model, remains silently-unsound naively.)
SILENT = {"alias_untaken"}


def test_clean_subscript_fragments_are_sound():
    for label in ("subscript", "two_keys", "aug_assign", "branch", "computed_key", "loop_computed"):
        verdict = classify(_BY_LABEL[label])[0]
        assert verdict in {"EXACT", "SOUND(over)"}, (label, verdict)


def test_a_store_passed_to_a_local_helper_is_followed_exactly():
    # the inter-procedural slice: the store handed to an in-view helper is modelled, not abstained —
    # on the taken AND the untaken branch (static following is branch-complete).
    for label in ("helper_taken", "helper_untaken"):
        assert classify(_BY_LABEL[label])[0] == "EXACT", label


def test_the_killer_constructs_are_silently_unsound_naively():
    # the load-bearing finding: without abstention, these confidently miss real writes (aliasing/helper
    # across an untaken branch — genuinely out of the model, unlike the now-modeled dict methods).
    for label in SILENT:
        verdict, missed, signalled = classify(_BY_LABEL[label])
        assert verdict == "UNSOUND-SILENT", (label, verdict)
        assert missed and not signalled                  # a real miss, with NO uncertainty signal


def test_no_other_construct_is_silently_unsound():
    silent_found = {c.label for c in CASES if classify(c)[0] == "UNSOUND-SILENT"}
    assert silent_found == SILENT                        # exactly these four, no more (regression guard)


def test_modelable_flags_exactly_the_unanalyzable_constructs():
    assert not modelable("h(out)")                       # store passed to a callee
    assert not modelable("d = out\nd['a'] = 1")          # store aliased
    assert not modelable("out.custom_mutate(x)")         # an UNKNOWN method
    assert modelable("out['a'] = x")                     # a plain subscript write is analyzable
    assert modelable("out.update({'a': 1})")             # a modeled dict mutator
    assert modelable("lst = []\nlst.append(x)")          # a modeled list mutator
    assert modelable("if x < 0:\n    out['a'] = 1\nelse:\n    out['b'] = 2")


def test_abstention_removes_every_silent_miss():
    for c in CASES:
        naive = classify(c)[0]
        abst = abstaining_verdict(c)
        if naive == "UNSOUND-SILENT":
            assert "UNKNOWN" in abst                      # silent miss -> honest unknown
    # and after abstention, no case is UNSOUND-SILENT anymore
    assert all("UNSOUND-SILENT" != abstaining_verdict(c) for c in CASES)
