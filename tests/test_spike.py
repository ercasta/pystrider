"""Behaviour pins for the vertical spike (docs/code_reasoning_design.md §"Vertical spike").

Each test corresponds to one feasibility claim the spike set out to answer.
"""
import ast

from pystrider import intake_function, analyze, guarded_variant, repair, choose_repair
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

def test_guard_effect_clears_the_outcome():
    # the semantic-effect path: add the guard's facts and re-run (no source produced)
    ik = intake_function(NONE_DEREF)
    site = ik.attributes[0]
    assert analyze(ik, {"x": "none"}) != []                 # V1: bug present
    guard = guarded_variant(ik, "x", site)
    assert analyze(ik, {"x": "none"}, extra_facts=guard) == []


# --- claim 6b (materialize a REAL edit): produce V2 source, verify by re-execution ---

def test_repair_materializes_edited_source_and_clears():
    ik = intake_function(NONE_DEREF)
    outcome = analyze(ik, {"x": "none"})[0]
    rep = repair(ik, {"x": "none"}, outcome)
    # the operator produced actual, parseable Python with the guard inserted ...
    ast.parse(rep.v2_source)                                 # valid source
    assert "if y is not None:" in rep.v2_source
    assert "y.bar()" in rep.v2_source
    # ... and the outcome is gone when the EDITED source is re-intaken and re-analyzed
    assert rep.cleared is True
    assert rep.residual == []


def test_repair_guards_the_dereferenced_variable():
    ik = intake_function(NONE_DEREF)
    outcome = analyze(ik, {"x": "none"})[0]
    assert outcome.base_var == "y"                           # the deref is on y
    assert repair(ik, {"x": "none"}, outcome).var == "y"     # so the guard tests y


def test_intake_reads_guarded_source():
    # the round-trip's second leg: intake of guarded source derives the guard facts (not hand-authored)
    guarded = "def f(x):\n    y = x\n    if y is not None:\n        return y.bar()\n"
    ik = intake_function(guarded)
    facts = set(ik.facts)
    assert any(r == "is_a" and o == "guard" for (_, r, o) in facts)
    assert any(r == "tests" and o == "y" for (_, r, o) in facts)
    assert any(r == "within_guard" for (_, r, _o) in facts)
    assert analyze(ik, {"x": "none"}) == []                  # guarded code is clean under x=None


# --- claim 7 (means-ends selection): propose several verified edits, CHOOSE the graded-best ---

def test_choose_repair_prefers_the_most_local_edit():
    ik = intake_function(NONE_DEREF)
    outcome = analyze(ik, {"x": "none"})[0]
    sel = choose_repair(ik, {"x": "none"}, outcome)
    # several distinct candidates were proposed ...
    names = {c.name for c in sel.candidates}
    assert {"guard_base", "guard_param"} <= names
    # ... every one materialized real source that actually clears the outcome ...
    assert all(c.cleared for c in sel.candidates)
    # ... and CHOOSE picked the most-local / smallest edit (guard the deref's own base var)
    assert sel.winner is not None and sel.winner.name == "guard_base"
    assert sel.winner.var == "y"


def test_choose_repair_trace_retains_beaten_alternatives():
    ik = intake_function(NONE_DEREF)
    outcome = analyze(ik, {"x": "none"})[0]
    sel = choose_repair(ik, {"x": "none"}, outcome)
    joined = "\n".join(sel.trace)
    assert "satisfied_by guard_base" in joined          # the winner
    assert "beaten" in joined                            # losers retained + auditable (monotone)


def test_operator_retrieval_discriminates_on_precondition():
    # a DIRECT param deref (`return x.bar()`) has no root-param chain, so the root-guard
    # operators are not retrieved by backward-CHAIN — only the local guard applies.
    ik = intake_function("def f(x):\n    return x.bar()\n")
    outcome = analyze(ik, {"x": "none"})[0]
    sel = choose_repair(ik, {"x": "none"}, outcome)
    assert {c.name for c in sel.candidates} == {"guard_base"}
    assert sel.winner.name == "guard_base" and sel.winner.var == "x"


def test_operators_are_retrieved_by_effect_from_the_library():
    from pystrider import operators as ops
    # all three ops prevent attribute_error when the site provides both preconditions ...
    both = ops.retrieve("attr5", "attribute_error", {"deref_base_known", "root_param_known"})
    assert {op.name for op in both} == {"guard_base", "guard_param", "guard_param_wide"}
    # ... but an operator for a DIFFERENT effect is never retrieved
    none = ops.retrieve("attr5", "some_other_error", {"deref_base_known", "root_param_known"})
    assert none == []


def test_candidate_fit_is_zero_when_unverified():
    # fit is gated on verification: an edit that doesn't clear the outcome is ineligible
    from pystrider.analysis import Candidate
    c = Candidate(name="x", var="x", description="", v2_source="", cleared=False,
                  locality=1.0, compactness=1.0)
    assert c.fit == 0.0


def test_value_kinds_are_the_declared_minimum_domain():
    # the spike's abstract domain is deliberately concrete-or-None first
    assert set(VALUE_KINDS) == {"none", "object"}
