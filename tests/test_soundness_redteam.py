"""Pins for the soundness red-team (experiments/soundness_redteam.py).

The credibility of the whole thesis is the checker's honesty, so the red-team maps exactly where it can
be fooled. These pins hold that boundary so a regression is caught: plain writes are SOUND; and every
footprint escape — update/setdefault/helper/alias AND (since abstention was productized + strengthened)
operator-mutation (`|=`) and container-aliasing across an untaken branch — is CAUGHT by abstention, so the
footprint oracle has NO remaining silent slip. The execution oracle's input-dependence blind spot (still
open) is also pinned.
"""
from experiments.soundness_redteam import CASES, classify


def _verdict(label: str) -> str:
    c = next(c for c in CASES if c.label == label)
    return classify(c)[0]


def test_plain_writes_are_sound():
    assert _verdict("subscript") == "SOUND"
    assert _verdict("aug_subscript") == "SOUND"
    assert _verdict("tuple_targets") == "SOUND"


def test_dict_methods_are_now_modeled_soundly():
    # update/setdefault graduated from abstained to MODELED: their key-writes are derived exactly.
    assert _verdict("update_method") == "SOUND"
    assert _verdict("setdefault_chain") == "SOUND"


def test_abstention_catches_the_genuinely_unmodelable_escapes():
    # what remains out of the model — a callee, an alias, operator-mutation, container-aliasing — abstains.
    for label in ("helper_mutate", "alias_direct", "ior_operator", "container_alias_untaken"):
        assert _verdict(label) == "CAUGHT(abstain)", label


def test_no_footprint_class_slips_anymore():
    slipped = {c.label for c in CASES if classify(c)[0] == "SLIPPED"}
    assert slipped == set()               # operator-mutation + container-aliasing are now closed


def test_the_ior_write_is_now_caught_not_admitted():
    c = next(c for c in CASES if c.label == "ior_operator")
    verdict, derived = classify(c)
    assert verdict == "CAUGHT(abstain)"   # the raw oracles still can't see `out |= {...}` ...
    assert "out.a" not in derived         # ... but abstention REFUSES rather than certify the under-approx


def test_execution_oracle_input_dependence_is_real():
    # the falsy-but-valid input a single-input verify would miss.
    ns: dict = {}
    exec("def f(v):\n    return v or 'default'", {}, ns)
    assert ns["f"](5) == 5                                # one input looks fine
    assert ns["f"](0) == "default"                        # another reveals the dropped valid input
