"""Pins for slice 0 (experiments/microfunction_pattern.py) — pystrider's bidirectional-pattern bet,
re-derived from first principles on ../ugm's new microfunctions engine.

These are the four findings that decide whether pystrider can be rewritten on that substrate. Each was
probed rather than assumed, and the two that could have been vacuous carry a control.
"""
import pytest

from experiments.microfunction_pattern import (
    Abstained, EACH_DOES, abstains_on_unknown, honest_refusal, iteration_source, library,
    minting_is_not_recognizable, minting_source, pattern_of, perturbation, recognize, round_trip,
    write_iteration,
)


# --- finding #2: the join survives, and one description serves both halves ----------------------------

def test_one_description_writes_and_recognizes():
    r = round_trip()
    assert r["round_trips"], r


def test_the_effect_tuples_carry_BOTH_roles():
    """The shared-variable join `?f each_does ?b` expressed on the new substrate. Without the object
    role, three effects about the same node could not say WHICH part is which."""
    _subject, required = pattern_of(library())
    assert ("link", EACH_DOES, "it", "body") in required
    assert all(subj == "it" and obj is not None for _k, _l, subj, obj in required)


def test_recognition_returns_bindings_not_a_verdict():
    """The useful unit is the partial description, not yes/no — `understand_partial.py`'s result."""
    g = library()
    seq, var, body = g.mint("sequence"), g.mint("variable"), g.mint("block")
    it = write_iteration(g, seq, var, body)
    assert recognize(g, it) == {"seq": seq, "var": var, "body": body}


# --- finding #1: a minting function is not recognizable; a cast is ------------------------------------

def test_minting_loses_the_subject_join_and_says_so():
    r = minting_is_not_recognizable()
    assert r["every_subject_role_is_lost"], r["effects"]
    assert r["refused_with"] is not None            # refused, not silently half-working
    assert not r["unknown"]                         # and NOT because anything was unreadable


def test_the_cast_form_is_what_makes_it_readable():
    """The same description, authored as a cast, recovers exactly what minting lost."""
    _subject, required = pattern_of(library())
    assert len(required) == 3


# --- finding #3: recognition must abstain where ranking may over-approximate --------------------------

def test_abstains_when_the_effect_set_is_incomplete():
    r = abstains_on_unknown()
    assert r["unknown"] and r["abstained"], r


def test_control_unknown_is_caused_by_the_register_key_not_by_SET():
    """Vacuity control: pin the CAUSE. A literal key in the same body is readable."""
    r = abstains_on_unknown()
    assert r["control_literal_key_is_readable"], r
    assert r["control_still_recognizes"], r


def test_abstention_is_an_exception_not_a_None():
    """An empty pattern would silently recognize EVERYTHING; refusing is the only safe answer."""
    with pytest.raises(Abstained):
        pattern_of(library(minting_source()), "make_iteration")


# --- finding #4: ONE library, not two that agree ------------------------------------------------------

def test_perturbing_one_label_darkens_BOTH_halves():
    r = perturbation()
    assert r["perturbed_still_self_consistent"], r   # the perturbed library still agrees with itself
    assert r["perturbed_writer_emits_new_label"], r  # the WRITE half moved
    assert r["old_code_now_invisible"], r            # the READ half moved, together with it


def test_control_the_perturbation_pin_is_not_vacuous():
    """The same hand-built shape MUST be readable by the unperturbed library, or `old_code_now_invisible`
    would be satisfied by a node nothing could ever read."""
    r = perturbation()
    assert r["control_same_shape_is_read_unperturbed"], r
    assert r["original_library_still_reads_it"], r


# --- honest refusal, this repo's standing floor -------------------------------------------------------

def test_out_of_repertoire_is_refused_not_guessed():
    r = honest_refusal()
    assert r["partial_refused"] and r["foreign_refused"], r
    assert r["complete_accepted"], r


def test_a_renamed_label_is_not_quietly_tolerated():
    """Belt and braces on the refusal floor: the recognizer has no fuzzy matching to fall back on."""
    g = library(iteration_source(each_does="each_doez"))
    seq, var, body = g.mint("sequence"), g.mint("variable"), g.mint("block")
    it = g.mint("iteration")
    g.link(it, "repeats_over", seq)
    g.link(it, "element", var)
    g.link(it, EACH_DOES, body)
    assert recognize(g, it) is None
