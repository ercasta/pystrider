"""The bridge — business, UX and toolkit knowledge, each in its own vocabulary.

⭐⭐ These are the pins for the headline claim: *keep your rules in separate files,
bridge them, and brew a working, verified UI.* What makes it a claim rather than a
demo is that each block is authored in ignorance of the others and the ONLY join is
`bridge.cnl` — so the pins below check the separation as hard as they check the
result.

The narrative version, with its printed evidence, is
`python -m demos.playground.playground --flip`.
"""
from __future__ import annotations

import pytest

from demos.playground import design
from demos.playground.brew import Cart, block_text, blocks_with, brew, reason
from pystrider import cnl

textual = pytest.importorskip("textual", reason="driving the emitted app needs textual")


# -- the blocks stay in their own vocabularies ----------------------------------

def _predicates(block) -> set:
    return {t.predicate for t in block.facts} | {
        t.predicate for r in block.rules for t in (r.head,) + r.body}


def test_business_and_toolkit_share_NO_vocabulary():
    """⭐ The separation claim, checked rather than asserted in prose.

    If commerce and widgets ever shared a predicate, the blocks would be joined
    somewhere other than the bridge and swapping one would stop re-targeting the
    system — the demonstration would still LOOK like it worked.
    """
    blocks = {b.name: b for b in cnl.load_all("demos/playground", ("business", "ux",
                                                                  "textual", "bridge"))}
    assert not _predicates(blocks["business"]) & _predicates(blocks["textual"])
    assert not _predicates(blocks["ux"]) & _predicates(blocks["textual"])


def test_the_bridge_is_the_ONLY_file_naming_both_sides():
    """A UX feature and a library capability meet in exactly one place."""
    blocks = {b.name: b for b in cnl.load_all("demos/playground", ("business", "ux",
                                                                  "textual", "bridge"))}
    feature, capability = "highlighted_discount", "styled_label"
    naming_both = [name for name, b in blocks.items()
                   if feature in _terms(b) and capability in _terms(b)]
    assert naming_both == ["bridge"]


def _terms(block) -> set:
    out = set()
    for t in list(block.facts) + [t for r in block.rules for t in (r.head,) + r.body]:
        out |= {t.subject, t.object}
    return out


def test_a_head_variable_nothing_binds_is_REFUSED_at_parse_time():
    """⚠ Forward chaining would assert it about EVERY entity in the world.

    Backward reading hid this by only expanding what was asked for. This floor
    does not, so it is a parse error rather than a rule that quietly fires about
    the discount policy, the widgets and the toolkit alike.
    """
    with pytest.raises(ValueError, match="binds it"):
        cnl.parse("?a wants ?b when ?a asked yes", name="loose")


# -- one authored rule, one system ----------------------------------------------

def test_every_authored_rule_became_exactly_one_system():
    r = reason(Cart())
    authored = sum(len(b.rules) for b in r.blocks)
    # the block rules, plus the arithmetic grounding and the three design checks
    assert len(r.facts.loop.systems) == authored + 4


def test_the_world_SETTLES():
    """⚠ `Facts.run` refuses a run that is still firing at the budget, so reaching
    here at all is the claim. On the old floor a rule without a `no <own
    conclusion>` premise never stopped; here `attach` compares before it stores."""
    r = reason(Cart())
    assert r.ticks < 10 and not r.facts.loop.errors


# -- the business rules reach the screen ----------------------------------------

def test_a_loyal_qualifying_order_earns_a_discount_ACROSS_the_blocks():
    r = reason(Cart())
    assert r.granted and r.features == ["highlighted_discount"]


@pytest.mark.parametrize("cart,why", [
    (Cart(customer_tier="basic"), "not loyal"),
    (Cart(order_spend=50.0), "below the threshold"),
])
def test_a_cart_that_earns_nothing_admits_no_feature(cart, why):
    r = reason(cart)
    assert not r.granted and r.features == [], why


def test_the_threshold_is_read_from_the_BLOCK_not_held_in_python():
    """⭐ Editing `discount_policy threshold 100` re-derives the whole app."""
    raised = block_text("business").replace("discount_policy threshold 100",
                                            "discount_policy threshold 200")
    assert not reason(Cart(order_spend=150.0), blocks_with(business=raised)).granted
    assert reason(Cart(order_spend=150.0)).granted


# -- ⭐⭐ the screen shape is FORCED, not chosen ---------------------------------

def test_marking_the_action_irreversible_FLIPS_the_screen_shape():
    """The deontic UX rule obliges a confirmation; the design layer resolves the
    only production that provides it. Nothing in Python says `if irreversible`."""
    assert brew(Cart()).screen == "one_screen"
    flipped = brew(Cart(irreversible=True))
    assert flipped.screen == "confirm_screen"
    assert "confirmation_step" in flipped.reasoning.features
    screen = next(d for d in flipped.decisions if d["point"] == "screen")
    assert screen["detail"].startswith("Forced")


def test_the_gate_is_emitted_ONLY_when_the_shape_called_for_it():
    assert "ConfirmScreen" not in brew(Cart()).source
    assert "ConfirmScreen" in brew(Cart(irreversible=True)).source


# -- the honest gap: the toolkit cannot do that ---------------------------------

def test_removing_a_CAPABILITY_un_admits_the_feature_that_needed_it():
    """⚠ Not an error and not a silent omission — the feature is simply not
    admitted, and the app is emitted without it."""
    without = block_text("textual").replace("styled_label  supported_by textual", "")
    b = brew(Cart(), blocks_with(textual=without))
    assert b.reasoning.features == []
    assert "def _show_discount" not in b.source
    assert b.reasoning.granted, "the BUSINESS still granted it; only the UI cannot show it"


def test_an_UNCOVERED_control_signal_REFUSES_to_emit_an_app():
    """⭐⭐ The check that makes the gate a consequence rather than a decoration.

    Take the modal capability away from an irreversible checkout and the completion
    leaf still emits `needs_confirmation` with nothing above it handling the signal.
    The design is REJECTED and no source is produced — rather than an ungated
    irreversible checkout that looks fine.
    """
    without = block_text("textual").replace("modal_confirm supported_by textual", "")
    b = brew(Cart(irreversible=True), blocks_with(textual=without))
    assert not b.admitted and b.source == ""
    effect = next(d for d in b.decisions if d["point"] == "effect")
    assert not effect["admitted"] and "unhandled" in effect["detail"]


def test_two_widgets_claiming_one_SLOT_is_caught_at_design_time():
    """`Accumulate`'s frame rule: the placed widgets must write disjoint slots."""
    # ⚠ Rewritten by PARSING rather than by string replacement: an earlier version
    # matched on two spaces where the block has three, so the edit silently did
    # nothing and the test passed by asserting about the UNMODIFIED design.
    clashing = "\n".join(
        "styled_label writes screen.result" if line.split()[:2] == ["styled_label", "writes"]
        else line
        for line in block_text("design").splitlines())
    assert "styled_label writes screen.result\n" in clashing + "\n", "the edit must bite"
    b = brew(Cart(), blocks_with(design=clashing))
    widgets = next(d for d in b.decisions if d["point"] == "widgets")
    assert not widgets["admitted"] and "both write" in widgets["detail"]
    assert b.source == "", "nothing is emitted from a design that does not compose"


# -- ⚠⚠ and it is trusted because it RUNS ---------------------------------------

def test_the_emitted_app_DRIVES_and_the_discount_is_actually_shown():
    v = brew(Cart()).verified
    assert v.works
    assert v.events == ["discount_shown 135.0", "highlighted", "completed 135.0"]


def test_the_irreversible_checkout_IS_GATED_BEFORE_it_completes():
    """⚠⚠ THE INDEPENDENT GATE. A template that renders the right widgets and never
    wires them reads perfectly; only running it can tell. The ORDER is the claim."""
    v = brew(Cart(irreversible=True)).verified
    assert v.works and v.gated
    assert v.events.index("gate_shown") < v.events.index("completed 135.0")


def test_CANCELLING_the_gate_does_not_complete_the_purchase():
    """The other half of safety: the gate is a gate, not a notification."""
    from demos.playground.brew import emit, verify
    cart = Cart(irreversible=True)
    r = reason(cart)
    source = emit(cart, r, "confirm_screen")
    v = verify(source, cart, r, choice="confirm-cancel")
    assert not v.completed and v.gated
    assert v.live, "...and the happy path still completes, so this is not a dead app"


# -- why ------------------------------------------------------------------------

def test_a_derived_fact_can_be_EXPLAINED_across_the_blocks():
    r = reason(Cart(irreversible=True))
    trail = " ".join(r.why("confirmation_step", "admitted_for", "cart"))
    assert "requires_feature" in trail and "realized_by" in trail
    assert "supported_by" in trail and "bridge.cnl" in trail
