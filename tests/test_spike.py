"""Behaviour pins for the vertical spike (docs/code_reasoning_design.md §"Vertical spike").

Each test corresponds to one feasibility claim the spike set out to answer.
"""
from pystrider import intake_function, analyze, guarded_variant
from pystrider.analysis import VALUE_KINDS


NONE_DEREF = """
def f(x):
    y = x
    return y.bar()
"""

SAFE = """
def g(x):
    y = x
    return y
"""


# --- claim 1: intake materializes AST+CFG facts from real source (no hand-authoring) ---

def test_intake_produces_expected_frame():
    ik = intake_function(NONE_DEREF)
    assert ik.func == "f" and ik.params == ["x"]
    facts = set(ik.facts)
    assert ("none", "is_a", "none_value") in facts          # value lattice shipped
    # exactly one attribute-access site, and it is `y.bar`
    assert len(ik.attributes) == 1
    site = ik.attributes[0]
    assert ("f", "has_param", "x") in facts
    assert any(p == "attribute" for (_, r, p) in facts if r == "is_a")
    assert ik.label_of[site] == "y.bar"


# --- claim 2+3+4: SUPPOSE(x=None) reaches the AttributeError outcome, with a trace ---

def test_none_hypothesis_confirms_attribute_error():
    ik = intake_function(NONE_DEREF)
    outcomes = analyze(ik, {"x": "none"})
    assert len(outcomes) == 1
    o = outcomes[0]
    assert o.kind == "attribute_error"
    assert o.label == "y.bar"
    assert "AttributeError" in o.headline()
    # the RECORD trace is a real derivation, threading the hypothesis to the outcome
    joined = "\n".join(o.trace)
    assert "raises attribute_error" in joined
    assert "has_value none" in joined            # y (and x) bound to None along the way


# --- claim 5 (soundness / no over-fire): a non-None hypothesis raises nothing ---

def test_object_hypothesis_does_not_fire():
    ik = intake_function(NONE_DEREF)
    assert analyze(ik, {"x": "object"}) == []


def test_no_attribute_access_no_outcome():
    ik = intake_function(SAFE)
    assert ik.attributes == []
    assert analyze(ik, {"x": "none"}) == []


# --- claim 6 (modification closes the loop): inserting a guard clears the outcome ---

def test_guard_insertion_clears_the_outcome():
    ik = intake_function(NONE_DEREF)
    site = ik.attributes[0]
    # V1: the bug is present
    assert analyze(ik, {"x": "none"}) != []
    # V2: `if x is not None:` around the deref -> re-run -> outcome gone (verify-by-re-execution)
    guard = guarded_variant(ik, "x", site)
    assert analyze(ik, {"x": "none"}, extra_facts=guard) == []


def test_value_kinds_are_the_declared_minimum_domain():
    # the spike's abstract domain is deliberately concrete-or-None first
    assert set(VALUE_KINDS) == {"none", "object"}
