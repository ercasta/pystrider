"""Pins for partial/aspect recognition (experiments/understand_partial.py).

The user's idea: recognize a loop by the ASPECTS it has, not as one whole idiom — the footprint discipline
(describe what you can, name the residual) applied to understanding. Over the stdlib this lifts loop
coverage from ~4% holistic to ~52% (a value-aspect in half of all real loops). These pins hold the
per-statement aspect classifier that makes it work, on synthetic loops (stable, corpus-independent):
accumulate / collect / index-set are recognized value-aspects; a compound body yields several aspects
(including inside control flow); side-effects and scalar state stay explicit residual.
"""
import ast

from experiments.understand_partial import _aspect, leaf_aspects, VALUE_ASPECTS


def _body(src: str):
    return ast.parse(src).body[0].body          # the For's body statements


def test_single_aspects_are_classified():
    assert leaf_aspects(_body("for e in xs:\n    s += e")) == ["accumulate"]
    assert leaf_aspects(_body("for e in xs:\n    s = s + e")) == ["accumulate"]      # long form
    assert leaf_aspects(_body("for e in xs:\n    out.append(e)")) == ["collect"]
    assert leaf_aspects(_body("for e in xs:\n    d[e] = 1")) == ["index-set"]
    assert leaf_aspects(_body("for e in xs:\n    log(e)")) == ["side-effect"]
    assert leaf_aspects(_body("for e in xs:\n    y = f(e)")) == ["scalar-assign"]


def test_a_compound_loop_yields_several_independent_aspects():
    aspects = leaf_aspects(_body("for e in xs:\n    s += e\n    out.append(e)\n    log(e)"))
    assert aspects == ["accumulate", "collect", "side-effect"]   # holistic scores 0; partial names all three


def test_aspects_are_found_inside_control_flow():
    # a filter-in-an-if — holistic misses it (multi-shaped), partial descends and names the collect.
    assert leaf_aspects(_body("for e in xs:\n    if e > 0:\n        out.append(e)")) == ["collect"]


def test_value_aspects_are_the_recognized_ones():
    assert VALUE_ASPECTS == {"accumulate", "collect", "index-set"}
    assert _aspect(ast.parse("out.append(e)").body[0]) == "collect"
    assert _aspect(ast.parse("x += 1").body[0]) == "accumulate"
    assert _aspect(ast.parse("log(e)").body[0]) == "side-effect"     # residual, named honestly
