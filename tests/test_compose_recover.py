"""Pins for the compose -> check -> recover loop (experiments/compose_recover.py).

The first-principle-rules slice: assemble a program from fragments, catch an UNSOUND composition with
grammapy's real disjoint-writes rule, repair it with a recovery RULE that reads the reified conflict
(each candidate swap disposed by SUPPOSE), and trust the result ONLY because it runs correctly. These
pins hold four claims: (1) a sound draft ships on the first check; (2) a conflicting draft is caught,
recovered by rule + SUPPOSE, and verified by re-execution; (3) the conflict is a REAL clobber — the
buggy program, if shipped, drops a field (so `verify` is doing real work, not rubber-stamping); and
(4) an unrepairable conflict becomes a named Refusal, never a clobbering program.
"""
from experiments.compose_recover import (
    CATALOG, Fragment, compose, check, recover, emit, verify, run, SHIFT_OPAQUE,
)

REQUIRED = ("scaled", "shifted")


def test_sound_draft_ships_on_first_check():
    out = run("sound", REQUIRED, CATALOG, prefer={"shifted": "shift_ok"})
    assert out.shipped_ok
    assert [f.name for f in out.final.fragments] == ["scale", "shift_ok"]
    assert out.verified.result == {"scaled": 10, "shifted": 15}


def test_conflicting_draft_is_caught_recovered_and_verified():
    out = run("buggy", REQUIRED, CATALOG, prefer={"shifted": "shift_bad"})
    # caught, then repaired to the disjoint provider, then RUN clean
    assert any("CHECK conflict" in s for s in out.steps)
    assert any("swap shift_bad -> shift_ok" in s for s in out.steps)
    assert out.shipped_ok
    assert [f.name for f in out.final.fragments] == ["scale", "shift_ok"]


def test_the_check_catches_a_real_clobber():
    # the buggy composition is a GENUINE executable bug: shift_bad writes out.scaled, clobbering scale.
    buggy = compose(REQUIRED, CATALOG, prefer={"shifted": "shift_bad"})
    assert check(buggy)                                   # grammapy refuses it (writes not disjoint)
    v = verify(buggy, REQUIRED)                           # and if it HAD shipped, it drops a field
    assert not v.ok
    assert "shifted" not in v.result                      # the second write clobbered the first key


def test_recovery_rule_proposes_off_the_reified_conflict():
    buggy = compose(REQUIRED, CATALOG, prefer={"shifted": "shift_bad"})
    err = check(buggy)[0]
    rec = recover(buggy, err, CATALOG)
    assert rec.blamed == "shift_bad"
    assert rec.proposals == ["shift_ok"]                  # the rule proposed the same-feature alternate
    assert rec.accepted == ("shift_bad", "shift_ok")      # SUPPOSE disposed it clean


def test_unrecoverable_conflict_becomes_a_named_refusal():
    thin = tuple(f for f in CATALOG if f.name != "shift_ok")   # no disjoint provider of `shifted`
    out = run("unrecoverable", REQUIRED, thin, prefer={"shifted": "shift_bad"})
    assert not out.shipped_ok
    assert out.final is None
    assert "no disjoint provider" in out.refusal          # a named gap, not a crash or a bad program


def test_unmodelable_fragment_is_refused_never_admitted():
    # a fragment whose footprint can't be soundly derived (writes via out.update) must be REFUSED, not
    # certified on a possible under-approximation — the productized honest-unknown membrane.
    assert SHIFT_OPAQUE.unknown                                # flagged un-analyzable (statically)
    out = run("unmodelable", REQUIRED, (CATALOG[0], SHIFT_OPAQUE))
    assert not out.shipped_ok and out.final is None
    assert "cannot derive a sound footprint" in out.refusal
    assert any("abstains" in s for s in out.steps)            # refused before the check, never admitted


def test_emitted_source_is_a_runnable_function():
    comp = compose(REQUIRED, CATALOG, prefer={"shifted": "shift_ok"})
    src = emit(comp)
    assert src.startswith("def report(x):")
    ns: dict = {}
    exec(src, ns)
    assert ns["report"](3) == {"scaled": 6, "shifted": 13}
