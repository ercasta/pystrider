"""Pins for the partial-curve + faithfulness probe (experiments/understand_partial_curve.py).

Measures whether partial coverage keeps climbing with more rules, and whether the aspects are honest
(guards not silently dropped). These pins hold the two new recognizers on synthetic loops: `_minmax`
recognizes a reduce-by-comparison, and the guard-aware `describe` tags a value-aspect found under a
conditional as `(cond)` instead of asserting it unconditionally.
"""
import ast

from experiments.understand_partial_curve import _minmax, describe


def _body(src: str):
    return ast.parse(src).body[0].body


def test_minmax_reduce_is_recognized():
    assert _minmax(ast.parse("if e < best:\n    best = e").body[0]) == "minmax-reduce"
    assert _minmax(ast.parse("if e > hi:\n    hi = e").body[0]) == "minmax-reduce"
    assert _minmax(ast.parse("if e == 0:\n    best = e").body[0]) is None      # not an ordering compare
    assert _minmax(ast.parse("if e < best:\n    best = f(e)\n    log(e)").body[0]) is None  # not a clean reduce


def test_guarded_aspect_is_tagged_not_asserted_flat():
    out: list = []
    describe(_body("for e in xs:\n    if e > 0:\n        acc.append(e)"), False, out)
    assert out == ["collect(cond)"]                        # the guard is carried, not dropped


def test_unguarded_aspect_is_plain():
    out: list = []
    describe(_body("for e in xs:\n    acc.append(e)"), False, out)
    assert out == ["collect"]


def test_reduce_and_mixed_body():
    out: list = []
    describe(_body("for e in xs:\n    total += e\n    if e > 0:\n        seen.append(e)"), False, out)
    assert out == ["accumulate", "collect(cond)"]          # unconditional accumulate + guarded collect

    out2: list = []
    describe(_body("for e in xs:\n    if e < best:\n        best = e"), False, out2)
    assert out2 == ["minmax-reduce"]                       # the whole if is one reduce aspect
