"""Pins for the metarule probe (experiments/metarule_probe.py) — ugm's `define schema` mechanism
minting a real rule from a declared fact, checked against pystrider's own intake facts."""
from ugm.lowering import run_bank

from experiments.metarule_probe import (
    DECLARED_KINDS, SOURCE, from_code_tagged, graph_from_source, mint_tagging_schema,
)


def test_declaring_a_kind_mints_a_real_rule_no_python():
    g, _ = graph_from_source(SOURCE)
    rules = mint_tagging_schema(g)
    # one concrete rule per declared kind, keyed by the kind — minted, not hand-written.
    assert {r.key for r in rules} == set(DECLARED_KINDS)


def test_the_minted_rules_tag_only_the_declared_kinds():
    g, _ = graph_from_source(SOURCE)
    rules = mint_tagging_schema(g)
    run_bank(g, rules)
    tagged = from_code_tagged(g)
    assert set(tagged) == set(DECLARED_KINDS)          # exactly the declared kinds got tagged
    assert all(tagged[k] for k in DECLARED_KINDS)       # and each has a real tagged node


def test_a_new_kind_needs_only_a_new_fact_not_new_python():
    import ugm as h

    g, _ = graph_from_source(SOURCE)
    rules = mint_tagging_schema(g)
    run_bank(g, rules)
    assert "expr_stmt" not in from_code_tagged(g)       # not declared yet -> not tagged

    h.ingest(g, rules, "expr_stmt is tagging_from_code")
    run_bank(g, rules)
    assert "expr_stmt" in from_code_tagged(g)            # declared -> tagged, same schema, no code change


def test_undeclared_kinds_never_get_tagged_by_the_schema():
    g, _ = graph_from_source(SOURCE)
    rules = mint_tagging_schema(g)
    run_bank(g, rules)
    tagged = from_code_tagged(g)
    for kind in ("assign", "unknown_expr", "function", "variable"):
        assert kind not in tagged
