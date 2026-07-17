"""Pins for the membrane-VAGUENESS limit-test (experiments/membrane_vagueness.py).

The last redoubt: does resolving an underspecified requirement need an LLM? The probe draws the
load-bearing line the user set — "underspecified" is in scope only as RULE-EXPANDABLE chunking — and
grounds every claim in the REAL playground engine. These pins hold:

(1) a vague chunk expands, by KNOWN RULES, to open-decision LEAVES no rule fills (structure pinned, no LLM);
(2) a leaf has NO TRUTH TO INFER — two authored values both drive green, as different apps (a choice);
(3) silent-default ships a valid-but-WRONG app with no signal (the LLM-sneaking-in anti-pattern);
(4) the surfaced membrane REFUSES until every open decision is authored (abstain, never default);
(5) articulation-vagueness is pre-CNL and its decomposition is a proposal (multiple valid readings);
(6) unknown-unknowns are invisible to surfacing — the honest, enumerated boundary.
"""
from experiments.membrane_vagueness import (
    _rule_heads, expand, pin, _valid, _identity, LEAF_KNOB, Cart,
)


def test_vague_chunk_expands_by_known_rules_to_open_decision_leaves():
    heads = _rule_heads()
    goal = ("requires_feature", "highlighted_discount")
    lines, leaves = expand(goal, heads)
    # the intermediate structure is rule-expandable (known rules unroll it) ...
    assert goal in heads and ("has_benefit", "discount") in heads and ("grants_discount", "yes") in heads
    # ... and it bottoms out at open decisions no rule fills, mapped to authored knobs.
    assert set(leaves) == {("customer_tier", "premium"), ("order_qualifies", "yes")}
    assert all(p in LEAF_KNOB for (p, _o) in leaves)          # every leaf is a surfacable decision
    assert any("rule-expandable" in ln for ln in lines) and any("LEAF" in ln for ln in lines)


def test_a_leaf_has_no_truth_to_infer():
    # Both authored values drive GREEN (valid) yet brew DIFFERENT apps -> the leaf is a choice, not a
    # fact the engine could recover. So an LLM cannot be load-bearing on it even in principle.
    premium = Cart(customer_tier="premium", order_spend=150)
    basic = Cart(customer_tier="basic", order_spend=150)
    assert _valid(premium) and _valid(basic)
    assert _identity(premium) != _identity(basic)


def test_silent_default_ships_a_valid_but_wrong_app():
    # The anti-pattern: an LLM guesses a leaf; the world's truth differs. Both are green, so the wrong
    # app ships with NO signal — the intent-side twin of unsound-silent footprint derivation.
    guess = Cart(customer_tier="premium", order_spend=150)    # LLM guesses "loyal"
    truth = Cart(customer_tier="basic", order_spend=150)      # the actual customer was basic
    assert _valid(guess) and _valid(truth)                    # nothing fails -> no signal
    assert _identity(guess) != _identity(truth)               # ...yet it is the wrong app


def test_surfaced_membrane_refuses_until_every_decision_is_authored():
    heads = _rule_heads()
    goal = ("requires_feature", "highlighted_discount")
    assert pin(goal, heads, authored={}).verdict == "REFUSE"
    # partial authoring still refuses, and names exactly what is open (honest-unknown, not a default).
    partial = pin(goal, heads, authored={"customer_tier": "premium"})
    assert partial.verdict == "REFUSE" and partial.holes == ("order_spend",)
    full = pin(goal, heads, authored={"customer_tier": "premium", "order_spend": 150})
    assert full.verdict == "ADMIT" and full.cart is not None and _valid(full.cart)


def test_articulation_vagueness_is_pre_cnl_and_decomposition_is_a_proposal():
    heads = _rule_heads()
    vague = ("trustworthy", "yes")
    _lines, leaves = expand(vague, heads)
    # neither rule-expandable nor a surfacable knob: no vocabulary names it -> pre-CNL.
    assert leaves == [vague] and vague[0] not in LEAF_KNOB
    # two candidate decompositions each brew a VALID app -> the decomposition is itself a proposal.
    a = Cart(irreversible=True, customer_tier="premium", order_spend=150)
    b = Cart(irreversible=True, customer_tier="basic", order_spend=80)
    assert _valid(a) and _valid(b) and _identity(a) != _identity(b)


def test_unknown_unknown_is_invisible_to_surfacing():
    heads = _rule_heads()
    tax = ("sales_tax", "yes")
    _lines, leaves = expand(tax, heads)
    # a decision no rule and no knob names cannot be surfaced -> the honest, enumerated boundary.
    assert leaves == [tax] and tax[0] not in LEAF_KNOB
    referenced = any(p == "sales_tax" for bodies in heads.values() for body in bodies for (p, _o) in body)
    assert not referenced
