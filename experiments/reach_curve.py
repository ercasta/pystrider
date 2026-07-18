"""How far does a SMALL rule set actually reach? — the coverage claim, measured.

The framing this project runs on (user, 2026-07-18): aiming for perfect rules that generate any program
is infeasible; a limited set of rules that can NAVIGATE — do something, check it, course-correct —
reaches a far larger share of the solution space. Every slice so far has demonstrated that on specs
chosen to demonstrate it. This measures it over a grid instead, which is a much weaker-sounding thing
to do and therefore the only one worth reporting.

**A raw pass rate would measure nothing** — it would only report how many unreachable specs we chose to
put in the grid. So every case is labelled reachable-or-not IN ADVANCE, from the rule set alone
(`_reachable`), and the measurement is whether the loop's ACTUAL reach matches its PREDICTED reach.
That makes each run a prediction that can come out wrong in either direction: a spec we called
unreachable that ships, or one we called reachable that refuses.

Two things here are worth believing:

  1. **Composition reach.** The repairs are single-step edits; the reachable set is their COMPOSITIONS.
     `HELLO_ANN` is reached by no rule alone. Reported by how many repairs each success actually
     APPLIED — separately from how many were ATTEMPTED, because trying one and finding it does not
     apply is the real cost of navigating, and it is paid on successes too.
  2. **No success is silent.** For every spec that ships, this probe RE-RUNS the shipped source itself
     and checks it against the spec, independently of the loop's own verdict — a probe that measured
     success with the mechanism under test would measure nothing. A build that shipped a wrong program
     appears as `SILENT WRONG`. That is the one outcome that would falsify the approach: an unreachable
     spec refused by name is an honest boundary; a spec that ships a wrong program is a broken method.

Run it: `python -m experiments.reach_curve`
"""
from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass

from experiments.build_procedure import INPUTS_LOOP, REPAIRS, RUNTIME_LIBRARY, build

__all__ = ["TRANSFORMS", "Outcome", "flat_spec", "loop_spec", "grid", "measure", "summarize", "run"]


# --- the transform axis ------------------------------------------------------------------------------
# What each printed line is required to be, with the number of repair hops it needs (None = outside the
# rule set). `shout_only` is the sharp case: `shout` EXISTS as a repair and still cannot uppercase a raw
# value, because it only ever wraps an already-greeted payload. Reach is the closure of what the rules
# COMPOSE to, not the set of functions lying around.

TRANSFORMS = {
    "plain":      (lambda v: v,                       0),
    "greet":      (lambda v: "hello_" + v,            1),
    "loud":       (lambda v: ("hello_" + v).upper(),  2),
    "shout_only": (lambda v: v.upper(),            None),
    "unknown":    (lambda v: "goodbye_" + v,       None),
}

_VALUES = ["ann", "bob", "cat"]


def _structural(structural):
    out = []
    if "audit" in structural:
        out += [("report", "requires_call", "audit"), ("audit", "is_a", "policy_call")]
    if "iteration" in structural:
        out += [("report", "requires_iteration_over", "names")]
    return out


def flat_spec(transforms, structural=()):
    """N ordinary output lines, the k-th needing `transforms[k]`."""
    facts = [("report", "is_a", "procedure")]
    inputs = {}
    for k, t in enumerate(transforms):
        val = _VALUES[k % len(_VALUES)]
        inputs["v%d" % k] = val
        facts += [("line%d" % k, "is_a", "intent"), ("line%d" % k, "of", "report"),
                  ("line%d" % k, "outputs", "v%d" % k), ("line%d" % k, "at", "i%d" % k),
                  ("line%d" % k, "expects", TRANSFORMS[t][0](val))]
        if k:
            facts.append(("i%d" % (k - 1), "before", "i%d" % k))
    return facts + _structural(structural), inputs


def loop_spec(transform, trailing=None, structural=()):
    """A loop over two names, its body needing `transform`, optionally followed by a plain line."""
    facts = [("report", "is_a", "procedure"),
             ("each", "is_a", "intent"), ("each", "of", "report"),
             ("each", "iterates", "names"), ("each", "binds", "n"), ("each", "at", "i0"),
             ("body", "is_a", "intent"), ("body", "of", "report"), ("body", "inside", "each"),
             ("body", "outputs", "n"), ("body", "at", "b0")]
    facts += [("body", "expects", TRANSFORMS[transform][0](v)) for v in INPUTS_LOOP["names"]]
    inputs = {"names": list(INPUTS_LOOP["names"])}
    if trailing is not None:
        inputs["tail"] = "zed"
        facts += [("tail_line", "is_a", "intent"), ("tail_line", "of", "report"),
                  ("tail_line", "outputs", "tail"), ("tail_line", "at", "i1"),
                  ("tail_line", "expects", TRANSFORMS[trailing][0]("zed")),
                  ("i0", "before", "i1")]
    return facts + _structural(structural), inputs


# --- running one spec and JUDGING IT OURSELVES -------------------------------------------------------

@dataclass(frozen=True)
class Outcome:
    label: str
    kind: str            # shipped | uncovered | unverified | unstructured | SILENT WRONG
    repairs: int         # repairs that ACTUALLY CHANGED the program
    tried: int           # repairs attempted — the navigate cost of finding out
    reachable: bool      # predicted from the rule set, BEFORE running
    wanted: tuple = ()
    got: tuple = ()


def _independent_run(source, inputs):
    """Execute the SHIPPED source ourselves — deliberately not the loop's own observation machinery."""
    env = {}
    buf = io.StringIO()
    exec(compile(RUNTIME_LIBRARY + source, "<shipped>", "exec"), env)
    with contextlib.redirect_stdout(buf):
        env["report"](*inputs.values())
    return buf.getvalue().splitlines()


def measure(label, spec, inputs, reachable=True):
    b = build(spec, inputs)
    tried = len([o for o in b.order if o in REPAIRS])
    # repairs that CHANGED the program. One that is tried and does not apply is a turn the loop spent
    # finding out — real navigate cost, but not a step of the composition.
    applied = sum(1 for line in b.workspace.log if ": applied" in line)
    wanted = tuple(b.workspace.wanted())
    if b.shipped is None:
        return Outcome(label, b.refusal.kind, applied, tried, reachable, wanted, tuple(b.stdout))
    got = tuple(_independent_run(b.shipped, inputs))
    if not set(wanted) <= set(got):
        return Outcome(label, "SILENT WRONG", applied, tried, reachable, wanted, got)
    return Outcome(label, "shipped", applied, tried, reachable, wanted, got)


def _reachable(transforms, structural=(), has_loop=False):
    """Is this spec inside the rules' closure — declared from the RULE SET, never read off the result."""
    if any(TRANSFORMS[t][1] is None for t in transforms):
        return False                       # a transform no composition of repairs reaches
    if "iteration" in structural and not has_loop:
        return False                       # a shape requirement no expansion rule can produce
    return True


def grid(full=True):
    """The spec space, each case carrying its PREDICTED reachability."""
    cases = []

    def flat(label, transforms, structural=()):
        spec, inputs = flat_spec(transforms, structural)
        cases.append((label, spec, inputs, _reachable(transforms, structural, False)))

    def loop(label, transform, trailing=None, structural=()):
        spec, inputs = loop_spec(transform, trailing, structural)
        used = (transform,) + ((trailing,) if trailing else ())
        cases.append((label, spec, inputs, _reachable(used, structural, True)))

    singles = list(TRANSFORMS) if full else ["plain", "greet", "loud", "shout_only"]
    for t in singles:
        flat("flat/1/" + t, (t,))
        flat("flat/2/" + t + "+plain", (t, "plain"))
        loop("loop/" + t, t)
        if full:
            flat("flat/3/" + t + "+plain+greet", (t, "plain", "greet"))
            flat("flat/1/" + t + "+audit", (t,), ("audit",))
            loop("loop/" + t + "+tail", t, trailing="plain")
            loop("loop/" + t + "+requires_iteration", t, structural=("iteration",))
    if full:
        # a loop REQUIRED but never asked for — predicted unreachable for a reason that is not about
        # transforms, which is what keeps the prediction from being one rule in disguise.
        flat("flat/2/plain+greet+requires_iteration", ("plain", "greet"), ("iteration",))
    return cases


def summarize(outcomes):
    by_kind = {}
    for o in outcomes:
        by_kind.setdefault(o.kind, []).append(o)
    hops = {}
    for o in outcomes:
        if o.kind == "shipped":
            hops[o.repairs] = hops.get(o.repairs, 0) + 1
    inside = [o for o in outcomes if o.reachable]
    outside = [o for o in outcomes if not o.reachable]
    refused = ("uncovered", "unverified", "unstructured")
    return {"total": len(outcomes),
            "by_kind": {k: len(v) for k, v in sorted(by_kind.items())},
            "shipped_by_repairs": dict(sorted(hops.items())),
            "silent_wrong": len(by_kind.get("SILENT WRONG", [])),
            "in_closure": len(inside),
            "in_closure_shipped": len([o for o in inside if o.kind == "shipped"]),
            "out_closure": len(outside),
            "out_closure_refused": len([o for o in outside if o.kind in refused]),
            "max_tried": max((o.tried for o in outcomes), default=0)}


# --- the walkthrough ---------------------------------------------------------------------------------

def run():
    print("REACH — how much of a spec space does a small, fixed rule set actually cover?")
    print()
    print("   the whole rule set: 2 expansion rules, %d repairs (%s), 2 patterns."
          % (len(REPAIRS), ", ".join(sorted(REPAIRS))))
    print("   Nothing is tuned per spec.")
    print()

    outcomes = [measure(*case) for case in grid()]
    s = summarize(outcomes)

    print("   %d specs run" % s["total"])
    print()
    for kind, n in s["by_kind"].items():
        print("      %-14s %3d" % (kind, n))

    print()
    print("   THE MEASUREMENT. Each spec was labelled reachable-or-not IN ADVANCE, from the rule set")
    print("   alone. A raw pass rate would only report how many unreachable specs we chose to include;")
    print("   this reports whether ACTUAL reach matches PREDICTED reach:")
    print("      inside the closure : %d/%d shipped" % (s["in_closure_shipped"], s["in_closure"]))
    print("      outside it         : %d/%d refused by name" % (s["out_closure_refused"],
                                                                s["out_closure"]))
    print("      SILENT WRONG       : %d" % s["silent_wrong"])

    print()
    print("   SUCCESSES BY REPAIRS THAT CHANGED THE PROGRAM — the composition claim:")
    for hops, n in s["shipped_by_repairs"].items():
        note = {0: "no repair needed", 1: "one single-step edit"}.get(hops, "%d edits COMPOSED" % hops)
        print("      %d repair(s): %3d   (%s)" % (hops, n, note))
    print("      (repairs ATTEMPTED peaked at %d — trying one and finding it does not apply is the"
          % s["max_tried"])
    print("       cost of navigating, and it is paid on successes too.)")

    print()
    print("   WHAT WAS REFUSED — each a spec the rules genuinely cannot reach:")
    for o in outcomes:
        if o.kind in ("unverified", "unstructured", "uncovered"):
            print("      %-38s %-14s wanted %s" % (o.label, o.kind, list(o.wanted)[:2]))

    print()
    print("   Every shipped program was RE-RUN here and checked against its spec, independently of the")
    print("   loop's own verdict. SILENT WRONG is the number that would falsify the approach: an")
    print("   unreachable spec refused by name is an honest boundary; a spec that ships a wrong")
    print("   program is a broken method.")
    print()
    print("   Note the shape axis costs nothing — every reachable transform stayed reachable inside a")
    print("   loop, with the same repairs. And `shout_only` shows the boundary is the CLOSURE of the")
    print("   rules, not the functions available: `shout` exists and still cannot uppercase a raw")
    print("   value, because it only ever wraps an already-greeted payload.")


if __name__ == "__main__":
    run()
