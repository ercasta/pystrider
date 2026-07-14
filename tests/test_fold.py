"""Tests for the semilattice-fold combinator (grammapy vision.md §3.4, §7.3).

Fold combines many contributions into one verdict through a declared total-order join. The core
property is ORDER-INDEPENDENCE (the semilattice law, here by construction of the chain): the folded
result must not depend on the order the contributions arrived in. The declared chain IS the policy —
`deny_overrides` is `grant < deny`; a safety-first confirmation policy is `waived < optional < obligatory`.
"""
import itertools

import pytest

from grammapy import Fold, Lattice, FoldItem, CompositionError

DENY_OVERRIDES = Lattice("deny_overrides", ("grant", "deny"))
CONFIRM_SAFETY = Lattice("obligation_overrides", ("waived", "optional", "obligatory"))


def test_join_takes_the_higher_ranked_element():
    assert DENY_OVERRIDES.join("grant", "deny") == "deny"       # deny wins
    assert CONFIRM_SAFETY.join("waived", "obligatory") == "obligatory"
    assert CONFIRM_SAFETY.join("waived", "optional") == "optional"


def test_deny_overrides_folds_a_vote():
    items = [FoldItem("role_admin", "grant"), FoldItem("resource_locked", "deny"),
             FoldItem("owner", "grant")]
    Fold.check(DENY_OVERRIDES, items)
    assert Fold.combine(DENY_OVERRIDES, items) == "deny"        # any deny overrides the grants


def test_fold_is_order_independent():
    items = [FoldItem("a", "waived"), FoldItem("b", "obligatory"), FoldItem("c", "optional")]
    results = {Fold.combine(CONFIRM_SAFETY, list(p)) for p in itertools.permutations(items)}
    assert results == {"obligatory"}                            # same verdict for EVERY ordering


def test_empty_fold_is_the_bottom_identity():
    assert Fold.combine(CONFIRM_SAFETY, []) == "waived"         # the join identity (chain bottom)


def test_a_verdict_outside_the_domain_is_rejected():
    items = [FoldItem("ok", "optional"), FoldItem("bug", "maybe")]
    with pytest.raises(CompositionError) as ctx:
        Fold.check(CONFIRM_SAFETY, items)
    msg = str(ctx.value)
    assert "maybe" in msg and "bug" in msg and "not in the lattice domain" in msg


def test_flipping_the_chain_flips_the_policy():
    # same contributions, a DIFFERENT declared policy -> a different (reviewable) outcome.
    waiver_overrides = Lattice("waiver_overrides", ("obligatory", "optional", "waived"))
    items = [FoldItem("irreversible", "obligatory"), FoldItem("trusted", "waived")]
    assert Fold.combine(CONFIRM_SAFETY, items) == "obligatory"  # safety policy: obligation wins
    assert Fold.combine(waiver_overrides, items) == "waived"    # lenient policy: waiver wins


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
