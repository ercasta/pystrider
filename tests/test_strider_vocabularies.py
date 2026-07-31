"""Pins for slice 4 (experiments/strider_vocabularies.py) — three independently-authored vocabularies
composing under the goal-driven approach, with no forward chaining anywhere.

The load-bearing pins: the derivation chain crosses all three blocks in order and IS the returned plan;
a rule's condition really is enforced by its parameter type; and a failed search's reasoning has to be
RETRIEVED from imagination, because the real graph never sees it.
"""
import pytest

import experiments.strider_vocabularies as V
from strider.mf import types


@pytest.fixture(scope="module")
def full():
    lib, cart = V.world()
    return lib, cart


# --- the claim: independently-authored blocks still compose ---------------------------------------------

def test_the_derivation_crosses_ALL_THREE_vocabularies_in_order(full):
    """⭐ business -> business -> ux -> bridge. Nothing declares this order; the parameter types do."""
    lib, cart = full
    got = V.ask(lib, cart, "admitted_highlighted_discount")
    assert got["answered"]
    assert got["derivation"] == ("qualify_order", "grant_discount", "surface_benefit", "admit_highlight")


def test_the_PLAN_is_the_derivation_so_the_reasoning_is_auditable(full):
    """⭐⭐ Strictly better than what it replaces. Forward chaining left a saturated graph and the job of
    reconstructing why a fact was there; here the chain that established the goal IS the answer."""
    lib, cart = full
    got = V.ask(lib, cart, "admitted_confirmation_step")
    assert got["derivation"] == ("oblige_confirmation", "admit_confirmation")


def test_a_rules_CONDITION_is_now_its_PARAMETER_TYPE(full):
    """The old CNL body `when ?cart order_qualifies yes` is `grant_discount(c: qualified_cart)`. Pinned
    against the types, because this is the substitution the whole slice rests on."""
    lib, _cart = full
    assert types.attrs_of(lib.graph, "qualified_cart")["order_qualifies"] is True
    assert types.attrs_of(lib.graph, "wants_confirmation")["requires_confirmation_step"] is True


def test_an_unqualified_cart_does_not_satisfy_the_downstream_type():
    """⚠ Vacuity control for the pin above: the type must actually exclude something, or 'the condition
    is the type' is a claim about nothing."""
    lib, cart = V.world(amount=50)
    assert not types.is_a(lib.graph, cart, "qualified_cart")


# --- swap a block, the rest re-derives -------------------------------------------------------------------

def test_swapping_the_TOOLKIT_changes_the_answer_and_nothing_else_is_edited():
    """The README's retarget claim: same business, same UX, a library that cannot gate."""
    lib, cart = V.world(toolkit=V.BARE)
    assert not V.ask(lib, cart, "admitted_confirmation_step")["answered"]


def test_control_the_same_cart_on_the_full_toolkit_succeeds(full):
    """⚠ Vacuity control. Without this the refusal above could be caused by anything at all."""
    lib, cart = full
    assert V.ask(lib, cart, "admitted_confirmation_step")["answered"]


def test_changing_only_the_BUSINESS_block_changes_the_UI():
    """A cart below the threshold earns no discount, so there is no benefit to surface — the UI shape
    follows from the business rule alone, with no UX or toolkit edit."""
    lib, cart = V.world(amount=50)
    assert not V.ask(lib, cart, "admitted_highlighted_discount")["answered"]


def test_a_non_premium_cart_also_loses_the_discount():
    lib, cart = V.world(tier="basic")
    assert not V.ask(lib, cart, "admitted_highlighted_discount")["answered"]


# --- ⚠ the regression, and the way back ------------------------------------------------------------------

def test_a_FAILED_search_leaves_the_real_graph_untouched():
    """⚠ THE REGRESSION, pinned as a FACT so nobody assumes otherwise. Forward chaining saturated the real
    graph, so a failure left its diagnosis lying there. Goal-directed planning reasons on copies and
    discards them, so `pursue` answers 'no plan found' — true, and useless on its own."""
    lib, cart = V.world(toolkit=V.BARE)
    got = V.ask(lib, cart, "admitted_confirmation_step")
    assert not got["answered"]
    assert lib.graph.attr(cart, "unsupported_confirmation_step") is None
    assert lib.graph.attr(cart, "requires_confirmation_step") is None
    assert got["report"]["blocked_by"] == ()      # nothing was FORBIDDEN; it was simply never established


def test_the_reason_is_RETRIEVABLE_from_imagination():
    """The frames are ordinary graph nodes and still exist. The bridge did run and did record why — on a
    frame nobody looks at. So a refusal has to be retrieved from the imagined worlds, never read off the
    real one, and any operation that wants to explain itself must record its reason where the frames are."""
    lib, cart = V.world(toolkit=V.BARE)
    got = V.ask(lib, cart, "admitted_confirmation_step")
    assert V.why_not(lib, cart, got["report"])["unsupported_confirmation_step"] == [True]


def test_the_retrieved_reason_DISCRIMINATES_between_causes():
    """⚠ Vacuity control, and the one that matters: two different failures must give two different
    reasons, or `why_not` is just reporting that something went wrong."""
    bare_lib, bare_cart = V.world(toolkit=V.BARE)
    bare = V.why_not(bare_lib, bare_cart, V.ask(bare_lib, bare_cart, "admitted_confirmation_step")["report"])

    poor_lib, poor_cart = V.world(amount=50)
    poor = V.why_not(poor_lib, poor_cart, V.ask(poor_lib, poor_cart, "admitted_highlighted_discount")["report"])

    assert bare["unsupported_confirmation_step"] == [True]
    assert poor["order_qualifies"] == [False]
    assert "unsupported_confirmation_step" not in poor


# --- ⚠ the honest price of dropping forward chaining ------------------------------------------------------

def test_an_open_question_costs_ONE_SEARCH_PER_CANDIDATE(full):
    """⚠ Forward chaining answered `who admitted_for cart` from a saturated graph — one pass, then a
    lookup. `goal.py` constrains named individuals and has no quantifier, so an open question is N
    searches. Pinned as a number rather than hidden behind an API that looks like a lookup."""
    lib, cart = full
    out = V.open_question(lib, cart, V.ADMISSIONS)
    assert out["searches"] == len(V.ADMISSIONS)
    assert out["imagined_total"] > 0
    assert set(out["admitted"]) == set(V.ADMISSIONS)
    assert out["refused"] == []


def test_the_open_question_reports_refusals_by_name():
    lib, cart = V.world(toolkit=V.BARE)
    out = V.open_question(lib, cart, V.ADMISSIONS)
    assert out["refused"] == ["admitted_confirmation_step"]
    assert "admitted_highlighted_discount" in out["admitted"]
