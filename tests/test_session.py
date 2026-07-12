"""Behaviour pins for Slice B — several functions in ONE shared graph (docs/implementation_plan.md).

Identity is by `(function, source_name)`: each function is intaken under its own namespace, so
same-named variables across functions are DISTINCT nodes in the shared graph, while the type/value
vocabulary the rules match on stays shared. Analysis is bounded per function by `focus_scope` and is
read-only in the shared graph (`suppose(commit=False)`), so functions and hypotheses never
contaminate one another.
"""
import ugm as h

from pystrider import Session
from pystrider.intake import intake_function


BAD = """
def bad(a):
    b = a
    return b.foo()
"""

SAFE = """
def safe(a):
    if a is not None:
        return a.foo()
"""


def test_same_name_vars_are_distinct_nodes_in_one_graph():
    # two functions each with a param `a` coexist without collapsing: identity is (function, name).
    s = Session()
    s.add_function(BAD)
    s.add_function(SAFE)
    trips = set(h.derived_triples(s.graph))
    a_vars = {t[0] for t in trips if t[1] == "is_a" and t[2] == "variable"
              and t[0].endswith("a")}
    assert a_vars == {"f0_a", "f1_a"}                    # two DISTINCT nodes, one shared graph
    # and the shared type vocabulary is NOT duplicated per function
    assert ("none", "is_a", "none_value") in trips


def test_each_function_analyzes_correctly_under_focus():
    s = Session()
    s.add_function(BAD)
    s.add_function(SAFE)
    bad = s.analyze("bad", {"a": "none"})
    safe = s.analyze("safe", {"a": "none"})
    assert [(o.label, o.base_var, o.line) for o in bad] == [("b.foo", "b", 4)]
    assert safe == []                                    # the guard closes on None -> no deref


def test_shared_graph_is_not_contaminated_across_hypotheses():
    # detection is read-only: analyzing `bad` under a=None must not ink the hypothesis into the
    # shared graph, so a later a=object analysis of the same function is clean.
    s = Session()
    s.add_function(BAD)
    assert s.analyze("bad", {"a": "none"})               # confirms (would-ink under the old contract)
    assert s.analyze("bad", {"a": "object"}) == []       # uncontaminated: object is safe


def test_analysis_matches_the_single_function_result():
    # a function analyzed inside a shared multi-function Session gives the SAME outcome it does
    # analyzed alone — focus bounding does not change the verdict, only the cost.
    from pystrider import analyze
    alone = analyze(intake_function(BAD, namespace="f0_"), {"a": "none"})
    s = Session()
    s.add_function(BAD)
    s.add_function(SAFE)                                  # extra function in the graph is irrelevant
    shared = s.analyze("bad", {"a": "none"})
    assert [o.label for o in alone] == [o.label for o in shared] == ["b.foo"]


def test_trace_renders_from_source_labels():
    s = Session()
    s.add_function(BAD)
    out = s.analyze("bad", {"a": "none"})[0]
    joined = "\n".join(s.render_trace("bad", out))
    assert "b.foo raises attribute_error" in joined      # namespaced ids rendered back to labels
    assert "f0_attr" not in joined                       # no raw namespaced id leaks into the render
    assert "has_value none" in joined                    # value tokens the rules never label: verbatim


# --- Slice B step 4: a value flows across a call boundary ------------------------------------

CALLER = """
def caller(m):
    return callee(m)
"""

CALLEE = """
def callee(p):
    return p.foo()
"""


def test_value_flows_across_a_call_boundary():
    s = Session()
    s.add_function(CALLER)
    s.add_function(CALLEE)
    assert s.link_calls() == [("caller", "callee", "p")]   # caller's arg wired to callee's param

    # hypothesize the CALLER's input is None; the outcome must surface INSIDE the callee
    out = s.analyze_across_call("caller", {"m": "none"}, "callee")
    assert [(o.label, o.base_var) for o in out] == [("p.foo", "p")]

    # the RECORD trace threads the value across the boundary: caller's seeded cell -> the link
    # pseudo-assign -> callee's parameter cell -> the deref.
    joined = "\n".join(out[0].trace)
    assert "p.foo raises attribute_error" in joined
    assert "link" in joined and "assigns p" in joined      # the cross-function link carried the value

    # control: an object argument produces no outcome inside the callee (value flow is sound)
    assert s.analyze_across_call("caller", {"m": "object"}, "callee") == []


def test_call_link_is_inert_without_wiring():
    # before link_calls(), the callee analyzed on its own seed still works, and no phantom flow
    # exists from the caller (the link is what carries the value, not mere co-residence).
    s = Session()
    s.add_function(CALLER)
    s.add_function(CALLEE)
    # no link_calls() yet: seeding the caller cannot reach the callee's deref
    assert s.analyze_across_call("caller", {"m": "none"}, "callee") == []
    # the callee still analyzes correctly under its OWN hypothesis
    assert [o.label for o in s.analyze("callee", {"p": "none"})] == ["p.foo"]
