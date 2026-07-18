"""Pins for the one-pattern-both-directions probe (experiments/bidirectional_pattern.py).

The claim under test is the humble goal's load-bearing one: patterns expressed AS RULES so the SAME
library serves both writing and understanding. A pattern that only recognized, or only wrote, would
pass half of this file — which is why the perturbation pin exists.
"""
from experiments.bidirectional_pattern import (
    ATTACH, HAND_WRITTEN, ITERATION, MINT, READ_BRIDGE, RECOGNIZE, WRITE_BRIDGE,
    _run, emit, of_kind, read_side, recognized, write_side,
)
from pystrider.intake import intake_function


def test_the_pattern_recognizes_an_iteration_in_HAND_WRITTEN_python():
    # code the write half never produced, read through intake and the read bridge.
    assert recognized(read_side(HAND_WRITTEN)) == [("names", "n")]


def test_the_SAME_pattern_text_writes_one_from_an_intent():
    source = emit(write_side())
    assert source.splitlines()[1:] == ["    for n in names:", "        print(n)"]
    assert _run(source, ["ann", "bob"]) == ["ann", "bob"]      # and it actually runs


def test_the_pattern_recognizes_the_code_it_just_WROTE():
    # the round trip: out through the write bridge into Python, back in through intake.
    written = emit(write_side())
    assert recognized(read_side(written)) == [("names", "n")]


def test_editing_the_SHARED_description_breaks_BOTH_halves():
    # THE pin. Two libraries that happened to agree would each keep working when the other's
    # description changed; one library cannot. A rename is the perturbation because the bridges are
    # the only place naming is negotiated (an added unbound head var is not even well-formed — ugm
    # rejects an RHS-only head variable, which is itself the substrate refusing an ill-founded head).
    broken = ITERATION.replace("element", "bound_var")
    assert recognized(read_side(HAND_WRITTEN, broken)) == []          # the question stops matching
    assert of_kind(write_side(pattern=broken), "emit_for") == []      # ...and the construction stops


def test_the_pattern_is_ONE_text_used_in_BOTH_rule_positions():
    # not two descriptions kept in sync by hand: the recognizer's BODY and the attach rule's HEAD are
    # the same string, differing only in the subject variable.
    assert RECOGNIZE.endswith(ITERATION)                             # used as a rule body
    assert ATTACH.startswith(ITERATION.replace("?x", "?l"))          # ...and as a rule head


def test_neither_WORLD_vocabulary_leaks_into_the_pattern():
    # bridges reconcile naming; the pattern is authored against neither side's names. If intake's or
    # the emitter's vocabulary appeared here, the "one library" claim would be a coincidence of
    # naming rather than a shared description.
    for word in ("for_loop", "loop_body", "iterates", "emit_for", "iter_over", "body_has"):
        assert word not in ITERATION
    assert "for_loop" in READ_BRIDGE and "emit_for" in WRITE_BRIDGE  # they live in the bridges


def test_intake_models_a_for_loop_as_structure_AND_state():
    # the coverage growth this needed: `for` was an audited `not_modelled` gap, so the read half was
    # blind to every iteration. A bridge could never have closed that (docs/vocabulary_bridge.md).
    r = intake_function(HAND_WRITTEN)
    kinds = {(s, p, o) for s, p, o in r.facts}
    loops = [s for s, p, o in kinds if p == "is_a" and o == "for_loop"]
    assert len(loops) == 1
    assert r.not_modelled == []                                   # no audited gap left behind
    assert any(p == "binds" for _s, p, _o in kinds)
    assert any(p == "loop_body" for _s, p, _o in kinds)
    # and the loop variable is threaded as STATE too: it is assigned an element we do not model.
    assert any(p == "assigns" for _s, p, _o in kinds)


def test_the_loop_body_links_only_DIRECT_children():
    # a nested loop's statements belong to the inner loop, not to the outer one — otherwise a pattern
    # asking "what does this loop do per element" would collect somebody else's statements.
    nested = ("def report(rows):\n"
              "    for r in rows:\n"
              "        for c in r:\n"
              "            print(c)\n")
    r = intake_function(nested)
    body = {(s, o) for s, p, o in r.facts if p == "loop_body"}
    outer = [s for s, p, o in r.facts if p == "is_a" and o == "for_loop"]
    assert len(outer) == 2
    # each loop claims exactly one direct child, and no statement is claimed by both loops.
    claimed = [o for _s, o in body]
    assert len(claimed) == len(set(claimed))
