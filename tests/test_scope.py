"""Tests for the binder-scoped reachability combinator (grammapy vision.md §3.2, §3.4).

Scope is sound iff every emitted control signal has a covering handler ANCESTOR — the algebraic-effects
reachability obligation. A handler covers its descendants' effects, not its own emissions, so the
covering handler must be a strict ancestor.
"""
import pytest

from grammapy import Scope, ScopeNode, CompositionError, unhandled_emissions


def test_a_handled_effect_is_reachable():
    # gate(handles X) > perform(emits X)  -> the effect is covered by its ancestor.
    tree = ScopeNode.of("app", children=[
        ScopeNode.of("gate", handles=["needs_confirmation"], children=[
            ScopeNode.of("perform", emits=["needs_confirmation"]),
        ]),
    ])
    Scope.check(tree)                                   # no raise
    assert unhandled_emissions(tree) == []


def test_an_unhandled_effect_is_rejected():
    # perform(emits X) with NO covering handler -> the effect escapes its scope.
    tree = ScopeNode.of("app", children=[ScopeNode.of("perform", emits=["needs_confirmation"])])
    with pytest.raises(CompositionError) as ctx:
        Scope.check(tree)
    msg = str(ctx.value)
    assert "escape their scope" in msg
    assert "needs_confirmation" in msg and "perform" in msg   # the signal + the emitting leaf named


def test_a_node_does_not_handle_its_own_emission():
    # a handler covers DESCENDANTS, not itself: emit+handle on one node is still unhandled.
    tree = ScopeNode.of("both", emits=["e"], handles=["e"])
    conflicts = unhandled_emissions(tree)
    assert [str(c) for c in conflicts] == [
        "control signal `e` emitted by `both` has no covering handler in scope"]


def test_handler_scope_does_not_leak_to_siblings():
    # gate handles X only within its sub-tree; a sibling emitting X is still unhandled.
    tree = ScopeNode.of("app", children=[
        ScopeNode.of("gate", handles=["x"], children=[ScopeNode.of("inside", emits=["x"])]),
        ScopeNode.of("outside", emits=["x"]),
    ])
    conflicts = unhandled_emissions(tree)
    assert len(conflicts) == 1 and conflicts[0].leaf == "outside"


def test_a_distant_ancestor_still_covers():
    # the covering handler need not be the immediate parent — any ancestor in scope suffices.
    tree = ScopeNode.of("app", handles=["x"], children=[
        ScopeNode.of("mid", children=[ScopeNode.of("deep", emits=["x"])]),
    ])
    Scope.check(tree)                                   # no raise


def test_no_effects_is_trivially_sound():
    Scope.check(ScopeNode.of("app", children=[ScopeNode.of("leaf")]))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
