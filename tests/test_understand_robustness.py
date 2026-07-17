"""Pins for the understand-half recognition sweep (experiments/understand_robustness.py).

Measures the normalization tax: how much spelling variation survives pattern recognition. Two failure
directions, mirroring the footprint scalability findings: OVER-recognition (a silent mis-ID — the
recognition analog of silent unsoundness) and UNDER-recognition (the tax). These pins hold: (1) the naive
matcher silently mis-identifies `sum(x)/len(y)` as a mean; (2) it misses common variants; (3) hole-
consistency removes the mis-ID; (4) light normalization reclaims the intermediate-variable and library
spellings; and (5) the accumulator loop is an honest CLIFF (abstain -> membrane), never a guess.
"""
from experiments.understand_robustness import (
    naive_recognize, robust_recognize, CASES, _verdict,
)

MEAN = ("average_of", "mean")


def test_naive_silently_mis_identifies_mismatched_args():
    # sum(xs)/len(ys) is not a coherent mean, but independent wildcards accept it — the fatal over-match.
    assert naive_recognize("sum(xs) / len(ys)") == MEAN


def test_naive_misses_common_spellings():
    assert naive_recognize("t = sum(xs)\nt / len(xs)") is None      # multi-statement: not even parsed
    assert naive_recognize("statistics.mean(xs)") is None           # a library alias
    assert naive_recognize("s = 0\nfor e in xs:\n    s += e\ns / len(xs)") is None


def test_hole_consistency_kills_the_over_match():
    assert robust_recognize("sum(xs) / len(xs)") == MEAN            # same arg: still a mean
    assert robust_recognize("sum(xs) / len(ys)") is None           # different args: correctly rejected


def test_normalization_reclaims_temp_and_library_spellings():
    assert robust_recognize("t = sum(xs)\nt / len(xs)") == MEAN    # inline the temp
    assert robust_recognize("statistics.mean(xs)") == MEAN         # de-alias the library call
    assert robust_recognize("mean(xs)") == MEAN


def test_accumulator_loop_is_an_honest_cliff():
    # a hand-rolled sum loop means `sum` semantically, but syntactic normalization can't reach it:
    # recognition abstains (CLIFF) rather than guess — the membrane.
    assert robust_recognize("s = 0\nfor e in xs:\n    s += e\ns / len(xs)") == "CLIFF"


def test_robust_has_zero_mis_identifications():
    wrong = [c.label for c in CASES if _verdict(robust_recognize(c.code), c.truth) == "WRONG"]
    assert wrong == []                                             # no silent mis-ID survives the fixes


def test_naive_has_exactly_one_mis_identification():
    wrong = [c.label for c in CASES if _verdict(naive_recognize(c.code), c.truth) == "WRONG"]
    assert wrong == ["mismatched_args"]                            # the over-match the fixes remove
