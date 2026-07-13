"""Pins for the rule-grown vs tool-minted comparison probe.

These lock the four findings of experiments/minting_comparison.py — the head-to-head reopened by
ugm feedback #2 being resolved (genuine per-match minting via the skolem `n?`):

  1. #2's fix is real: a one-line skolem rule GROWS a depth-k successor chain generatively.
  2. Both pools emit byte-identical, verified source — interchangeable as generators.
  3. But rule-minted nodes are name-COLLIDED (id-addressed only), while tool-minted nodes have stable
     unique names — the addressing tax that keeps tool-minting preferable for synthesis.
  4. Minting is not self-limiting: the chain length tracks the external fuel bound (max_rounds).
"""
import ast

import ugm as h

from experiments.minting_comparison import (
    emit_from_chain, verify, tool_minted_pool, rule_grown_pool, _grow_rule, compare,
)


def test_both_pools_emit_identical_verified_source():
    """Finding 2: for the same depth k, the tool-minted and rule-grown pools emit BYTE-IDENTICAL
    Python, and both re-execute correctly (chain(0) == k). Interchangeable as generators."""
    c = compare(4)
    assert c.identical
    assert c.tool_verified and c.rule_verified
    ast.parse(c.tool_source); ast.parse(c.rule_source)
    assert c.tool_source.strip().endswith("return v4")


def test_rule_skolem_actually_mints_a_chain():
    """Finding 1: the skolem rule GENUINELY mints — a single origin slot grows into a k+1-long chain
    under the forward driver. This is the 'mint a successor' case #2 used to make inexpressible."""
    pool = rule_grown_pool(4)
    assert len(pool.slot_ids) == 5                              # origin + 4 minted successors
    # the chain is a real `has_next` path recovered by id-traversal
    g = pool.graph
    origin = pool.slot_ids[0]
    assert g.name(origin) == "origin"
    nxt = [o for r, o in g.relations_from(origin) if g.predicate(r) == "has_next"]
    assert nxt and nxt[0] == pool.slot_ids[1]


def test_rule_minted_nodes_are_name_collided():
    """Finding 3 (the addressing tax): every rule-minted successor shares the name `n` — identity is
    STRUCTURAL, so they cannot be told apart by name. The tool-minted slots, by contrast, are unique."""
    c = compare(4)
    assert c.rule_names == ["origin", "n", "n", "n", "n"]
    assert c.rule_name_collisions == 4 and c.rule_name_addressable is False
    assert c.tool_names == ["slot_0", "slot_1", "slot_2", "slot_3", "slot_4"]
    assert c.tool_name_addressable is True


def test_name_addressing_works_for_tool_pool_and_fails_for_rule_pool():
    """The concrete consequence for emit/verify: a specific slot is pickable by name in the
    tool-minted graph (exactly one node), but ambiguous in the rule-grown graph (many nodes named
    `n`) — so the rule-grown pool MUST be threaded by id (ugm #8)."""
    tool = tool_minted_pool(4)
    rule = rule_grown_pool(4)
    assert len(tool.graph.nodes_named("slot_3")) == 1          # uniquely addressable by name
    assert len(rule.graph.nodes_named("n")) == 4               # 4-way ambiguous -> id-addressing only


def test_minting_is_not_self_limiting_fuel_is_external():
    """Finding 4: the generated chain length tracks the EXTERNAL fuel bound (max_rounds == k), not any
    self-limit in the rule — minting does not retire the fuel discipline."""
    for k in (2, 3, 6):
        assert len(rule_grown_pool(k).slot_ids) == k + 1       # grows exactly to the budget
        assert verify(emit_from_chain(k + 1), k)


def test_grow_rule_is_a_single_skolem_rule():
    """The generative power is one rule: an RHS-only skolem `n?` anchored to the LHS-bound `?p`. This
    is the primitive #2's resolution added — not a tool enumerating the pool."""
    r = _grow_rule()
    heads = {(p.s, p.p, p.o) for p in r.rhs}
    assert ("?p", "has_next", "n?") in heads                   # the skolem successor, keyed on ?p
    assert any(p.o == "n?" or p.s == "n?" for p in r.rhs)      # the skolem literal appears in the head
