"""Pins for the definition-substitution stress test (experiments/definition_substitution.py) — ugm's
`define ... iff ...` biconditional, used to derive a candidate fix from an abstract "licenses <concept>"
claim, no Python lookup table standing in for meaning."""
from experiments.definition_substitution import BUGS, propose_by_definition, search_fix_with_definitions


def _bug(label):
    return next(b for b in BUGS if b.label == label)


def test_the_necessary_direction_derives_the_concrete_compare_from_the_bare_claim():
    # "suspect licenses adult" alone (nothing about HOW) -> the definition's own inverse reconstructs it.
    assert propose_by_definition("adult") == ("ge", "age", 18)
    assert propose_by_definition("senior") == ("ge", "age", 65)


def test_an_undeclared_concept_is_refused_not_guessed():
    assert propose_by_definition("vip") is None


def test_the_off_by_five_bug_part_1_refused_is_fixed_by_definition_substitution():
    bug = _bug("senior threshold, off by FIVE (Part 1 refused this one)")
    fix = search_fix_with_definitions(bug)
    assert fix == ("definition_substitution", "ge", 65)


def test_an_undeclared_concept_bug_is_still_honestly_refused_end_to_end():
    bug = _bug("undeclared concept ('vip') — must be refused by ALL strategies, definitional included")
    assert search_fix_with_definitions(bug) is None
