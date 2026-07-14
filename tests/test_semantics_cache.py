"""Pins for the semantics rule-bank cache (perf fix, 2026-07-14).

`build_rule_graph`/`rule_list` used to re-run `load_machine_rules(SEMANTICS)` on EVERY detect —
and that call VALIDATES the bank by running it (`machine_rule_defects`), so it was ~65% of every
`analyze` and ran 7× per `repair_all` (measured: repair_all 8.2s→0.21s, suite 376s→31s once cached;
see experiments/session_benchmark.py). The bank is static, so it is now parsed ONCE and memoized.

These pins lock the two invariants the fix rests on, so it can't silently regress:
  1. the parse is memoized (identity), and
  2. each rule GRAPH is still assembled fresh per call — so no consumer accumulates shared graph
     state (the correctness guarantee that makes sharing the parse safe).
"""
import ugm as h

from pystrider import intake_function, repair_all
from pystrider.semantics import _parsed_rules, build_rule_graph, rule_list


def test_parsed_bank_is_memoized():
    # the expensive parse+validate happens once — the same object is returned each call.
    assert _parsed_rules() is _parsed_rules()


def test_rule_list_is_a_fresh_list_over_the_shared_rules():
    a, b = rule_list(), rule_list()
    assert a is not b                      # a caller mutating the list can't corrupt the cache
    assert a == b                          # same shared Rule objects, same order


def test_build_rule_graph_is_fresh_each_call_but_equivalent():
    g1, g2 = build_rule_graph(), build_rule_graph()
    assert g1 is not g2                    # distinct graphs — no shared state across detects
    assert set(h.derived_triples(g1)) == set(h.derived_triples(g2))   # identical reified bank


def test_repair_still_reaches_clean_after_caching():
    src = "def decide(user):\n    name = user.name\n    return name.upper()\n"
    plan = repair_all(intake_function(src), {"user": "none"})
    assert plan.clean
