"""Pins for the footprint scalability sweep (experiments/footprint_scalability.py).

The highest-information scalability finding: the derivation stays sound on self-contained subscript
fragments but SILENTLY MISSES writes on common real-code constructs (method mutation, aliasing/helpers
across untaken branches) — and an abstention detector (`modelable`) converts every silent miss into an
honest-unknown. These pins hold the finding so a regression (a construct newly silently-unsound, or the
abstention no longer catching one) is caught. Scalability = derive-what-you-can + know-when-you-can't.
"""
from experiments.footprint_scalability import CASES, classify, modelable, abstaining_verdict

_BY_LABEL = {c.label: c for c in CASES}
# the constructs that escape BOTH oracles with no uncertainty signal — the fatal class.
SILENT = {"alias_untaken", "helper_untaken", "update_method", "setdefault"}


def test_clean_subscript_fragments_are_sound():
    for label in ("subscript", "two_keys", "aug_assign", "branch", "computed_key", "loop_computed"):
        verdict = classify(_BY_LABEL[label])[0]
        assert verdict in {"EXACT", "SOUND(over)"}, (label, verdict)


def test_the_four_killer_constructs_are_silently_unsound_naively():
    # the load-bearing finding: without abstention, these confidently miss real writes.
    for label in SILENT:
        verdict, missed, signalled = classify(_BY_LABEL[label])
        assert verdict == "UNSOUND-SILENT", (label, verdict)
        assert missed and not signalled                  # a real miss, with NO uncertainty signal


def test_no_other_construct_is_silently_unsound():
    silent_found = {c.label for c in CASES if classify(c)[0] == "UNSOUND-SILENT"}
    assert silent_found == SILENT                        # exactly these four, no more (regression guard)


def test_modelable_flags_exactly_the_unanalyzable_constructs():
    assert not modelable("out.update({'a': 1})")         # store method call
    assert not modelable("out.setdefault('a', 1)")       # store method call
    assert not modelable("h(out)")                       # store passed to a callee
    assert not modelable("d = out\nd['a'] = 1")          # store aliased
    assert modelable("out['a'] = x")                     # a plain subscript write is analyzable
    assert modelable("if x < 0:\n    out['a'] = 1\nelse:\n    out['b'] = 2")


def test_abstention_removes_every_silent_miss():
    for c in CASES:
        naive = classify(c)[0]
        abst = abstaining_verdict(c)
        if naive == "UNSOUND-SILENT":
            assert "UNKNOWN" in abst                      # silent miss -> honest unknown
    # and after abstention, no case is UNSOUND-SILENT anymore
    assert all("UNSOUND-SILENT" != abstaining_verdict(c) for c in CASES)
