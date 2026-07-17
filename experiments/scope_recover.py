"""Feasibility probe — a SECOND interference class: SCOPE (no control effect escapes unhandled).

Every probe so far composed through grammapy's ACCUMULATE combinator (disjoint writes) and recovered
by SWAPPING a colliding fragment. This one composes through SCOPE: control flow is effects — a leaf may
`emit` a control signal, a handler node `handles` signals over its sub-tree, and the shape is sound iff
EVERY emitted signal has a covering handler ancestor (the algebraic-effects obligation; grammapy's
`unhandled_emissions` CNL rule-module). The failure is a control LEAK, not a write collision — an
emitted signal that escapes its scope, i.e. a real uncaught-effect bug.

The recovery is a DIFFERENT SHAPE, which is the point of doing a second class:

    Accumulate (compose_recover)   collision on a channel  ->  SWAP the colliding fragment for a disjoint one
    Scope      (this probe)        signal escapes its scope ->  INSERT a handler that covers it (GAP-FILL)

So the loop is the same (compose -> check -> recover -> verify) but the recovery is a WRAP/synthesize,
not a replace — the missing handler is fabricated, exactly the procedures GAP-FILL move.

Trust-by-execution is direct and load-bearing: signals are real Python exceptions, so an UNHANDLED
emission actually ESCAPES the emitted function (an uncaught exception), and a handled one is caught and
completes. The Scope check catches the leak at DESIGN time; running the code CONFIRMS it — the unhandled
build raises, the recovered build returns the handler's fallback. The generator proposes; the checker +
the Pilot dispose. No language model anywhere.

Run it: `python -m experiments.scope_recover`
"""
from __future__ import annotations

from dataclasses import dataclass

from grammapy.scope import ScopeNode, unhandled_emissions
from grammapy.combinators import Scope, CompositionError


class Signal(Exception):
    """A control signal as an algebraic effect — raised at an `emit`, caught by a covering handler."""
    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


# --- the control-tree fragments: an effect leaf, and the handler that can cover it ------------------

@dataclass(frozen=True)
class Effect:
    """A leaf that EMITS `signal` when `guard` holds, and otherwise yields `value`. `fallback` is the
    result a handler should substitute when it catches the signal — the declared recovery value (absent
    => the signal has no known recovery, so no handler can be synthesized: a genuine gap)."""
    name: str
    signal: str
    guard: str
    value: str
    fallback: "str | None"


@dataclass(frozen=True)
class Handler:
    """A binder that HANDLES `signal` over its sub-tree, substituting `value` when it fires."""
    signal: str
    value: str


VALIDATE = Effect("validate", signal="invalid", guard="x < 0", value="x * 2", fallback="0")
# an effect whose escape has NO declared recovery — a handler for it cannot be synthesized (refusal).
DEMAND = Effect("charge", signal="needs_funds", guard="x > 100", value="x", fallback=None)


@dataclass(frozen=True)
class Design:
    """A candidate program: an effect leaf, optionally wrapped in a handler. The build under revision."""
    effect: Effect
    handler: "Handler | None" = None

    def tree(self) -> ScopeNode:
        leaf = ScopeNode.of(self.effect.name, emits=[self.effect.signal])
        if self.handler is None:
            return leaf
        return ScopeNode.of(f"handle_{self.handler.signal}",
                            handles=[self.handler.signal], children=[leaf])

    def wrapped(self, handler: Handler) -> "Design":
        return Design(self.effect, handler)


# --- CHECK: grammapy's real Scope soundness (no emission escapes its scope) --------------------------

def check(design: Design) -> list[CompositionError]:
    """Run grammapy's SCOPE check over the design's control tree. [] if every emitted signal has a
    covering handler; else the `CompositionError` carrying the escaping `Unhandled` emissions."""
    try:
        Scope.check(design.tree())
        return []
    except CompositionError as e:
        return [e]


# --- RECOVER: insert a handler covering the escaping signal (GAP-FILL, not swap) ---------------------

@dataclass
class Recovery:
    escaping: str
    repaired: "Design | None"
    refusal: str = ""


def recover(design: Design) -> Recovery:
    """From the escaping emission, SYNTHESIZE a handler that covers it and wrap the design. The handler's
    recovery value is the effect's declared `fallback`; if none is declared, no handler can be
    synthesized — a NAMED refusal (the honest gap), never a program that still leaks."""
    escaped = unhandled_emissions(design.tree())
    sig = escaped[0].signal
    if design.effect.fallback is None:
        return Recovery(sig, None,
                        f"signal `{sig}` escapes and the effect declares no fallback — cannot synthesize "
                        f"a handler. Declare a recovery value (Effect.fallback) or a boundary that handles it.")
    return Recovery(sig, design.wrapped(Handler(sig, design.effect.fallback)))


# --- EMIT + VERIFY BY EXECUTION (an unhandled signal really escapes) ---------------------------------

def emit(design: Design) -> str:
    """Emit a `task(x)` function. The effect becomes a guarded `raise Signal(...)`; a handler wraps the
    body in `try/except Signal`, substituting its recovery value for the covered signal."""
    e = design.effect
    body = [f"if {e.guard}:", f"    raise Signal({e.signal!r})", f"return {e.value}"]
    if design.handler is None:
        lines = ["def task(x):"] + [f"    {ln}" for ln in body]
    else:
        h = design.handler
        lines = ["def task(x):", "    try:"] + [f"        {ln}" for ln in body] + [
            "    except Signal as s:",
            f"        if s.name == {h.signal!r}:",
            f"            return {h.value}",
            "        raise",
        ]
    return "\n".join(lines)


@dataclass
class Verified:
    source: str
    normal: object
    escaped: bool
    signal_result: object
    ok: bool
    reason: str


def verify(design: Design) -> Verified:
    """RUN the emitted task on a normal input and a signal-triggering input. An unhandled emission
    ESCAPES (the Signal propagates out of the function) — observed here as a caught exception at the
    boundary; a handled one returns the fallback. `ok` iff the normal path is right AND the signal does
    not escape."""
    src = emit(design)
    ns: dict = {"Signal": Signal}
    exec(src, ns)
    task = ns["task"]
    normal = task(5)                                     # x>=0: no signal, normal value
    try:
        signal_result = task(-1)                         # x<0: emits `invalid`
        escaped = False
    except Signal:
        signal_result, escaped = None, True              # it escaped the function -> a control leak
    expected_fallback = int(design.effect.fallback) if design.effect.fallback is not None else None
    ok = (normal == 10) and (not escaped) and (signal_result == expected_fallback)
    reason = ("normal path correct and the signal is handled in scope" if ok
              else f"control leak: task(-1) escaped={escaped}, signal_result={signal_result}")
    return Verified(src, normal, escaped, signal_result, ok, reason)


# --- the loop --------------------------------------------------------------------------------------

@dataclass
class Outcome:
    label: str
    draft: Design
    steps: list
    final: "Design | None" = None
    verified: "Verified | None" = None
    refusal: str = ""

    @property
    def shipped_ok(self) -> bool:
        return self.verified is not None and self.verified.ok


def run(label: str, draft: Design) -> Outcome:
    out = Outcome(label, draft, [])
    design = draft
    for _ in range(2):
        errs = check(design)
        if not errs:
            out.final = design
            out.verified = verify(design)
            out.steps.append(f"SCOPE clean -> emit + verify: {out.verified.reason}")
            return out
        out.steps.append(f"SCOPE leak: {errs[0].conflicts[0]}")
        rec = recover(design)
        if rec.repaired is None:
            out.refusal = rec.refusal
            out.steps.append(f"RECOVER failed -> Refusal: {rec.refusal}")
            return out
        out.steps.append(f"RECOVER (GAP-FILL): insert handler covering `{rec.escaping}`")
        design = rec.repaired
    return out


def _show(o: Outcome) -> None:
    print(f"  [{o.label}]  handler at draft: {o.draft.handler.signal if o.draft.handler else '(none)'}")
    for s in o.steps:
        print(f"     {s}")
    if o.final is not None:
        v = o.verified
        print(f"     => shipped: task(5)={v.normal}, task(-1)={v.signal_result} (escaped={v.escaped})"
              f"   trustworthy: {o.shipped_ok}")
    print()


def main() -> None:
    print("SCOPE RECOVER — a second interference class: no control effect escapes its scope.\n")

    print("PART 1 — a GUARDED draft (validate wrapped in a handler): every emission is covered, ships\n")
    _show(run("guarded", Design(VALIDATE, Handler("invalid", "0"))))

    print("PART 2 — a LENIENT draft (validate, NO handler): `invalid` escapes; caught by SCOPE, and")
    print("recovered by INSERTING a handler (gap-fill), then verified — the leak becomes a caught signal\n")
    _show(run("lenient->recovered", Design(VALIDATE)))

    print("PART 3 — an effect with NO declared fallback (charge/`needs_funds`): the signal escapes and")
    print("no handler can be synthesized -> a NAMED refusal, never a program that still leaks\n")
    _show(run("no-fallback", Design(DEMAND)))

    print("Same loop as compose_recover, a different class and a different recovery SHAPE: Scope leaks are")
    print("repaired by INSERTING a handler (gap-fill), not swapping a fragment. The checker catches the")
    print("leak at design time; execution confirms it — an unhandled signal really escapes. No model.")


if __name__ == "__main__":
    main()
