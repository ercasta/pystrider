"""Pins for the Scope interference class (experiments/scope_recover.py).

A second combinator (Scope: no control effect escapes its scope) driven through the same
compose->check->recover->verify loop, with a DIFFERENT recovery shape — insert a handler (gap-fill),
not swap a fragment. These pins hold: (1) a guarded design ships; (2) a lenient design's leak is
caught by grammapy's Scope and recovered by inserting a handler; (3) the check maps to a REAL bug —
the unhandled emission actually escapes the emitted function as an uncaught exception; (4) an effect
with no declared fallback becomes a named Refusal, never a still-leaking program; and (5) the recovery
is a wrap/gap-fill that names the escaping signal.
"""
import pytest

from experiments.scope_recover import (
    Design, VALIDATE, DEMAND, Handler, Signal, check, recover, emit, verify, run,
)


def test_guarded_design_ships():
    o = run("guarded", Design(VALIDATE, Handler("invalid", "0")))
    assert o.shipped_ok
    assert o.verified.normal == 10 and o.verified.signal_result == 0 and not o.verified.escaped


def test_lenient_leak_is_caught_and_recovered_by_inserting_a_handler():
    o = run("lenient", Design(VALIDATE))
    assert any("SCOPE leak" in s for s in o.steps)
    assert any("insert handler" in s for s in o.steps)
    assert o.shipped_ok
    assert o.final.handler is not None and o.final.handler.signal == "invalid"


def test_the_unhandled_emission_really_escapes_the_function():
    # the design-time Scope check corresponds to a real runtime leak: an uncaught Signal.
    leaky = Design(VALIDATE)                              # no handler
    assert check(leaky)                                   # Scope refuses it
    src = emit(leaky)
    ns = {"Signal": Signal}
    exec(src, ns)
    with pytest.raises(Signal):                           # task(-1) lets `invalid` escape
        ns["task"](-1)
    assert ns["task"](5) == 10                            # the normal path is fine


def test_recovery_gap_fills_and_names_the_escaping_signal():
    rec = recover(Design(VALIDATE))
    assert rec.escaping == "invalid"
    assert rec.repaired is not None and rec.repaired.handler == Handler("invalid", "0")


def test_effect_without_fallback_becomes_a_named_refusal():
    o = run("no-fallback", Design(DEMAND))
    assert not o.shipped_ok
    assert o.final is None
    assert "needs_funds" in o.refusal and "no fallback" in o.refusal


def test_verify_confirms_the_recovered_build_handles_the_signal():
    recovered = recover(Design(VALIDATE)).repaired
    v = verify(recovered)
    assert v.ok and not v.escaped and v.signal_result == 0
