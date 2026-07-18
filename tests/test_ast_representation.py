"""Pins for the AST-representation probe (experiments/ast_representation.py).

These hold the facts a spec->AST->code pipeline will be built on, so a ugm change that moves any of
them surfaces here rather than in a half-built pipeline: (1) skolem identity is a function of ALL
the whole MATCH, head or body (the trap); (2) the mint-then-attach idiom yields one parent with N
children;
(3) minted nodes are name-degenerate, so identity is the node id; (4) order is a derived relation;
(5) nesting is the same attach idiom; (6) the sequence head is rule-expressible via a scoped NAC; and
(7) revision under a monotone graph works by minting v2 and moving a `current` pointer.
"""
from experiments.ast_representation import (
    ARGS_FACTS, ORDER_FACTS, NEST_FACTS, HEAD_FACTS, REVISION_FACTS,
    trap_rules, idiom_rules, order_rules, nesting_rules, head_rules, revision_rules,
    build, minted_of_kind, one, many, emit_calls, payload_of,
)


def test_a_skolem_is_a_function_of_all_its_head_anchored_endpoints():
    # THE TRAP: `c?` is anchored on the per-element `?x`, so each arg is a distinct match and mints a
    # distinct parent. Pinning the trap, not just the fix — this is the shape that silently produces
    # two functions where one was meant.
    g = build(ARGS_FACTS, trap_rules)
    calls = minted_of_kind(g, "ast_call")
    assert len(calls) == 2
    assert sorted(sorted(g.name(a) for a in many(g, c, "has_arg")) for c in calls) == [["a"], ["b"]]


def test_mint_then_attach_yields_one_parent_with_many_children():
    # THE IDIOM: mint anchored on invariants only; attach in a second rule with the parent LHS-BOUND
    # (`?c`, an ordinary variable) so the attach mints nothing. This is what makes variable arity work.
    g = build(ARGS_FACTS, idiom_rules)
    calls = minted_of_kind(g, "ast_call")
    assert len(calls) == 1
    assert sorted(g.name(a) for a in many(g, calls[0], "has_arg")) == ["a", "b"]


def test_minted_nodes_are_name_degenerate_so_identity_is_the_node_id():
    # every node a head mints carries that head's literal name: three statements, all named `c`.
    # Anything keying on the name collapses them into one — a silent wrong answer, so it is pinned.
    g = build(ORDER_FACTS, order_rules)
    calls = minted_of_kind(g, "ast_call")
    assert len(calls) == 3
    assert {g.name(c) for c in calls} == {"c"}      # one NAME
    assert len(set(calls)) == 3                     # three IDS


def test_order_is_a_derived_relation_and_emission_only_follows_it():
    g = build(ORDER_FACTS, order_rules)
    calls = minted_of_kind(g, "ast_call")
    # the rule derived the sequence from spec-level `before`; the tool walked it, decided nothing.
    assert emit_calls(g, calls).splitlines() == ["print('hello')", "print('world')", "print('bye')"]


def test_nesting_is_the_same_attach_idiom_one_level_down():
    g = build(NEST_FACTS, nesting_rules)
    loops = minted_of_kind(g, "ast_for")
    assert len(loops) == 1                                    # one loop, not one per body statement
    kids = many(g, loops[0], "body_has")
    assert len(kids) == 2
    assert g.name(one(g, loops[0], "iter_over")) == "names"
    assert emit_calls(g, kids).splitlines() == ["print('hello')", "print('world')"]


def test_the_sequence_head_is_rule_expressible_with_a_scoped_nac():
    # "first in THIS body" = no body-SIBLING precedes me. HEAD_FACTS plants a decoy — `s3` precedes
    # `s1` but lives OUTSIDE the loop — which an unscoped NAC would let disqualify the real head.
    g = build(HEAD_FACTS, head_rules)
    firsts = [(n, t) for n in g.nodes() for r, t in g.relations_from(n) if g.has_key(r, "body_first")]
    assert len(firsts) == 1
    assert g.name(one(g, firsts[0][0], "ast_arg")) == "hello"


def test_revision_mints_a_new_version_and_moves_the_current_pointer():
    # the do -> check -> RECOVER loop on a monotone graph: nothing is deleted, the correction is a
    # rule, and the superseded version survives as provenance.
    g = build(REVISION_FACTS, revision_rules)
    call = minted_of_kind(g, "ast_call")[0]
    assert g.name(one(g, call, "emits_v1")) == "helo"        # the mistake is RETAINED
    assert g.name(one(g, call, "emits_v2")) == "hello"       # the correction was minted
    assert g.name(one(g, call, "current")) == "emits_v2"     # the pointer redirected
    assert payload_of(g, call) == "hello"                    # emission follows the pointer
