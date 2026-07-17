"""Pins for bundle-composability coverage (experiments/composability_coverage.py).

The real economic variable: how much of a new app is compose-existing vs author-new. The vocabulary
extraction is objective (parsed from the bundles) and grounds the classification. These pins hold:
(1) the vocabulary is the actual bundle tokens; (2) a COMPOSABLE requirement uses only existing
vocabulary; (3) a NEW-BUNDLE requirement genuinely introduces a token the bundles lack; and (4) the
spectrum spans all three tiers (the classification isn't degenerate).
"""
from experiments.composability_coverage import extract_vocab, classify, REQUIREMENTS, Req


def test_vocabulary_is_the_actual_bundle_tokens():
    vocab = extract_vocab()
    assert {"grants_discount", "confirm", "highlighted_discount", "supported_by"} <= vocab
    assert "sales_tax" not in vocab and "currency" not in vocab      # genuinely outside the bundles


def test_composable_requirements_use_only_existing_vocabulary():
    vocab = extract_vocab()
    for r in REQUIREMENTS:
        if classify(r, vocab) == "COMPOSABLE":
            assert set(r.needs) <= vocab, r.label                    # grounded: no new tokens


def test_new_bundle_requirements_introduce_a_missing_token():
    vocab = extract_vocab()
    for r in REQUIREMENTS:
        if classify(r, vocab) == "NEW-BUNDLE":
            assert set(r.needs) - vocab, r.label                     # grounded: really needs new vocab


def test_the_spectrum_spans_all_three_tiers():
    vocab = extract_vocab()
    verdicts = {classify(r, vocab) for r in REQUIREMENTS}
    assert verdicts == {"COMPOSABLE", "NEW-RULE", "NEW-BUNDLE"}       # not a degenerate classification


def test_a_retarget_reuses_the_spec():
    # a NEW-BUNDLE re-target (web) still reuses the business/ux decisions — the expensive part is the library.
    retargets = [r for r in REQUIREMENTS if r.reuses_spec]
    assert retargets and all(classify(r, extract_vocab()) == "NEW-BUNDLE" for r in retargets)
