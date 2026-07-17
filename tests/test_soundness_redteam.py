"""Pins for the soundness red-team (experiments/soundness_redteam.py).

The credibility of the whole thesis is the checker's honesty, so the red-team maps exactly where it can
be fooled. These pins hold that boundary so a regression (a new silent slip, or abstention no longer
catching a known class) is caught: plain writes are SOUND; update/setdefault/helper/alias are CAUGHT by
abstention; and exactly two footprint classes SLIP — operator-mutation (`|=`) and container-aliasing
across an untaken branch — the honest, enumerated blind spots. The execution oracle's input-dependence
blind spot is also pinned.
"""
from experiments.soundness_redteam import CASES, classify


def _verdict(label: str) -> str:
    c = next(c for c in CASES if c.label == label)
    return classify(c)[0]


def test_plain_writes_are_sound():
    assert _verdict("subscript") == "SOUND"
    assert _verdict("aug_subscript") == "SOUND"
    assert _verdict("tuple_targets") == "SOUND"


def test_abstention_catches_the_known_unmodelable_classes():
    for label in ("update_method", "setdefault_chain", "helper_mutate", "alias_direct"):
        assert _verdict(label) == "CAUGHT(abstain)", label


def test_exactly_two_footprint_classes_still_slip():
    slipped = {c.label for c in CASES if classify(c)[0] == "SLIPPED"}
    assert slipped == {"ior_operator", "container_alias_untaken"}   # the enumerated blind spots


def test_the_ior_slip_misses_the_write_silently():
    c = next(c for c in CASES if c.label == "ior_operator")
    verdict, derived = classify(c)
    assert verdict == "SLIPPED"
    assert "out.a" not in derived                         # `out |= {...}` write is invisible to the footprint


def test_execution_oracle_input_dependence_is_real():
    # the falsy-but-valid input a single-input verify would miss.
    ns: dict = {}
    exec("def f(v):\n    return v or 'default'", {}, ns)
    assert ns["f"](5) == 5                                # one input looks fine
    assert ns["f"](0) == "default"                        # another reveals the dropped valid input
