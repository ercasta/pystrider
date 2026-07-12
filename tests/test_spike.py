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


def test_scope_is_represented_structurally():
    # function membership is a graph EDGE (in_function), not a name prefix — the ugm-idiomatic
    # representation and the anchor for focus / inter-procedural links later.
    ik = intake_function(NONE_DEREF)
    facts = set(ik.facts)
    assert ("x", "is_a", "variable") in facts and ("y", "is_a", "variable") in facts
    # every function-local entity links to the function node
    entities = {s for (s, p, _o) in facts if p == "in_function"}
    assert {"x", "y", ik.attributes[0]} <= entities
    assert all(o == "f" for (_s, p, o) in facts if p == "in_function")


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


# --- slice A (state-threading in the MAIN analyzer): reassignment is correct, not SSA-wrong ---

REASSIGN = """
def f(x, z):
    y = x
    y = z
    return y.bar()
"""


def test_reassignment_threads_through_the_main_analyzer():
    # y is bound to None (x) then REASSIGNED to a non-None object (z); the deref must NOT raise.
    # The old SSA-per-variable model got this wrong (y held both None and obj at once); value now
    # lives in per-state cells threaded across the two assignments.
    ik = intake_function(REASSIGN)
    assert ik.states == ["p0", "p1", "p2"]                # one program point per assignment + entry
    assert analyze(ik, {"x": "none", "z": "object"}) == []


def test_reassignment_to_none_still_raises():
    # if the reassigned value is also None, the deref still raises — threading is sound both ways
    ik = intake_function(REASSIGN)
    assert analyze(ik, {"x": "none", "z": "none"}) != []


def test_deref_before_reassignment_still_raises():
    # control: a deref that happens BEFORE the safe reassignment reads the None value and raises
    ik = intake_function(
        "def f(x, z):\n    y = x\n    w = y.bar()\n    y = z\n    return w\n")
    outs = analyze(ik, {"x": "none", "z": "object"})
    assert len(outs) == 1 and outs[0].label == "y.bar"


# --- slice A' (branch-merge): value at a merge point is the UNION of the branches -------------

BRANCH = """
def f(c, x, z):
    if c:
        y = x
    else:
        y = z
    return y.bar()
"""


def test_branch_forks_and_merges_into_states():
    # an if/else forks p0 into two entry points and merges into a fresh point: 6 states total
    ik = intake_function(BRANCH)
    assert ik.states == ["p0", "p1", "p2", "p3", "p4", "p5"]


def test_merge_unions_a_none_from_the_then_branch():
    # y = x on the then-path; x=None makes y possibly-None at the merge -> a sound may-None-deref
    ik = intake_function(BRANCH)
    assert analyze(ik, {"c": "object", "x": "none", "z": "object"}) != []


def test_merge_unions_a_none_from_the_else_branch():
    # y = z on the else-path; z=None makes y possibly-None at the merge, via the OTHER edge
    ik = intake_function(BRANCH)
    assert analyze(ik, {"c": "object", "x": "object", "z": "none"}) != []


def test_no_raise_when_both_branches_are_non_none():
    # neither path can bind y to None -> the merged value is non-None on every edge, no raise
    ik = intake_function(BRANCH)
    assert analyze(ik, {"c": "object", "x": "object", "z": "object"}) == []


def test_merged_value_is_derived_by_a_rule_not_a_python_join():
    # the DISTINGUISHING claim: the value union at the merge is ugm provenance (the frame rule
    # firing across a merge edge), not a Python-computed lattice meet. The trace must show the
    # merge cell's None threaded back through a branch assignment.
    ik = intake_function(BRANCH)
    o = analyze(ik, {"c": "object", "x": "object", "z": "none"})[0]
    joined = "\n".join(o.trace)
    assert "has_value none  <- rule" in joined      # the merged value is RULE-derived, not given
    assert "reads z" in joined                       # ... threaded back through the else branch (y = z)


# --- slice A' (loop unrolling): the pre-materialized state pool is the fuel budget -----------

MAY_SKIP = """
def f(x, z):
    y = x
    while c:
        y = z
    return y.bar()
"""

LOOP_MAY_NULL = """
def f(x, z):
    y = z
    while c:
        y = x
    return y.bar()
"""

# b becomes None only after the loop's body runs TWICE (b <- a, a <- x): a depth-2 dependency
DEPTH2 = """
def f(x, z):
    a = z
    b = z
    while c:
        b = a
        a = x
    return b.bar()
"""


def test_loop_may_be_skipped_so_pre_loop_none_survives():
    # the loop might run 0 times; y is None before it -> a sound possible None-deref at the merge
    assert analyze(intake_function(MAY_SKIP), {"x": "none", "z": "object"}) != []


def test_loop_body_may_introduce_none():
    # y is non-None before the loop, but the body may set it to None -> possible None-deref
    assert analyze(intake_function(LOOP_MAY_NULL), {"x": "none", "z": "object"}) != []


def test_loop_safe_when_no_path_binds_none():
    # nothing on any iteration count can make y None -> no raise
    assert analyze(intake_function(MAY_SKIP), {"x": "object", "z": "object"}) == []


def test_unroll_depth_is_the_fuel_budget():
    # THE fuel-budget claim: a bug that only manifests on the 2nd iteration is FOUND at unroll>=2
    # and MISSED at unroll=1 — the pre-materialized state-pool size bounds what is reachable.
    assert analyze(intake_function(DEPTH2, loop_unroll=2), {"x": "none", "z": "object"}) != []
    assert analyze(intake_function(DEPTH2, loop_unroll=1), {"x": "none", "z": "object"}) == []


# --- the ugm/Python boundary, as a CHECKED INVARIANT ----------------------------------------

def test_intake_emits_only_structure_never_reasoning():
    # The load-bearing design claim: intake materializes STRUCTURE; every value/outcome fact is
    # DERIVED by a ugm rule, never written by Python. If a reasoning predicate ever leaks into
    # intake, the analysis has silently migrated out of the engine — this pin catches that.
    REASONING = {"has_value", "eval_to", "guard_open", "reached", "raises"}
    for src in (NONE_DEREF, REASSIGN, BRANCH, MAY_SKIP, DEPTH2,
                "def f(x):\n    y = x\n    if y is not None:\n        return y.bar()\n"):
        emitted = {p for _, p, _ in intake_function(src).facts}
        assert emitted.isdisjoint(REASONING), emitted & REASONING
