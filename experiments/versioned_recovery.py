"""Feasibility probe — VERSIONED STATE makes runtime recovery COMPLETE (monotonicity as the enabler).

`experiments/procedure_assembly.py` found the limit: the planner's discrepancy/replan rules heal an
OMISSION fully but a CLOBBER only partially — a corrupting write to a sibling's already-committed
value can't be un-written, because ugm's world is monotone. That finding was an artifact of the
REPRESENTATION: procedure_assembly modeled the state as a single MUTABLE dict, one destructive cell
per channel — the one thing a monotone substrate is bad at.

This probe applies the fix (the user's point): represent the state as SUCCESSIVE VERSIONS. A write does
not mutate a cell; it APPENDS an immutable, fragment-attributed write node. "The current value of a
channel" is a PROJECTION over the write history — the latest write by a fragment that is still in the
live build. Nothing is ever deleted (monotone); revision is append + move a pointer. This is exactly
SSA/φ, git's moving HEAD, Datomic's as-of, event-sourcing.

The payoff is that the SAME rules now recover COMPLETELY, with no new recovery logic:

  * `corpus/procedure.cnl`'s REPLAN already marks the clobbering step `excluded` on the discrepancy —
    an ADDITIVE marker, never a deletion. The recovery DECISION is the rule's, unchanged.
  * the projection simply reads that marker: a write by an `excluded` fragment is not live. So the
    clobber's write to `scaled` drops out of the current version, and `scale`'s correct `scaled=10`
    — which was appended, never overwritten, and is still right there in the history — becomes current
    again. `scaled` reads 10, not 15. The corruption is REVERSED.

So monotonicity, far from blocking revision, is what MAKES it clean: the correct prior value still
exists, so recovery = re-project past the excluded write (a `current`-pointer move), not an un-doable
mutation. The revised claim from procedure_assembly holds: design-time interference detection is an
EARLINESS optimization, not a correctness necessity — with versioned state, runtime recovery is
complete.

Reuses the fragment library + planner wiring from `procedure_assembly`; the ONLY change is the act
tool (append-only versioned writes instead of a mutated dict) and the projection. No model anywhere.

Run it: `python -m experiments.versioned_recovery`
"""
from __future__ import annotations

from dataclasses import dataclass

import ugm as h
from ugm import AttrGraph

from experiments.procedure_assembly import (
    Fragment, INIT, SCALE, SHIFT_OK, SHIFT_BAD, SHIFT_FLAKY, LIBRARY,
    _load, _ensure, _stage_op, _rank_noop,
)
from ugm.dispatch import call_arg


# --- the version store: an append-only log of fragment-attributed writes ----------------------------

@dataclass(frozen=True)
class Write:
    """One immutable, versioned write: channel `chan` got value `val`, produced by fragment `by`, at
    monotone sequence `seq`. Appended, never mutated — the event-sourced state history."""
    seq: int
    chan: str
    val: object
    by: str


def _run_fragment(frag: Fragment, x: int) -> dict:
    """RUN a fragment's real statement in isolation and return the dict entries it wrote (so each write
    is attributed to exactly this fragment). The clobber (`shift_bad`) writes `scaled`, not `shifted`."""
    env: dict = {"out": {}, "x": x}
    exec(frag.stmt, {}, env)
    return dict(env["out"])


# --- the ACT + OBSERVE boundary, now VERSIONED: append writes, never mutate --------------------------

def _versioned_act_tool(log: list[Write], order: list[str], x: int):
    """The world-action tool, versioned. RUN the op's statement, APPEND a `Write` per dict entry it set
    (attributed to the fragment, at the next monotone seq), then OBSERVE: `<now> true feat_<key>` iff
    this fragment actually wrote that key. A clobber appends a write to the WRONG channel and leaves its
    intended effect unobserved -> DISCREPANCY. The history grows; nothing is overwritten."""
    def handler(g, call_id):
        op = call_arg(g, call_id, "arg")
        if op is None:
            return set()
        if any(g.has_key(r, "done") for r, _ in g.relations_from(op)):
            return set()                                 # act ONCE (the ready token persists)
        frag = LIBRARY[g.name(op)]
        order.append(frag.name)
        wrote = _run_fragment(frag, x)                   # RUN — get this fragment's own writes
        for chan, val in wrote.items():                  # APPEND each as an immutable versioned write
            log.append(Write(len(log), chan, val, frag.name))
        touched = set()
        now, yes = _ensure(g, "<now>"), _ensure(g, "<yes>")
        for r, e in list(g.relations_from(op)):          # OBSERVE effects from THIS fragment's writes
            if g.has_key(r, "add"):
                feat = g.name(e)
                achieved = (feat == "out_ready") or (feat.removeprefix("feat_") in wrote)
                if achieved:
                    touched.add(g.add_relation(now, "true", e))
        touched.add(g.add_relation(op, "done", yes))
        return touched
    return handler


# --- the current-version projection: latest write per channel by a NON-EXCLUDED fragment ------------

def _excluded_fragments(g: AttrGraph) -> set[str]:
    """The fragments the RULES excluded (procedure.cnl: `?o excluded <yes> when ?o discrepancy ?e`) —
    read straight off the graph. This additive marker IS the recovery decision; the projection obeys it."""
    excl = set()
    for name in LIBRARY:
        found = g.nodes_named(name)
        if found and any(g.has_key(r, "excluded") for r, _ in g.relations_from(found[0])):
            excl.add(name)
    return excl


def project_current(log: list[Write], excluded: set[str]) -> dict:
    """Resolve the CURRENT state: for each channel, the latest write (max seq) by a fragment still in
    the live build (not `excluded`). The clobber's write is retained in the log but skipped here, so the
    superseded-correct value re-surfaces. This is the `current`-pointer move, as a query."""
    current: dict = {}
    for w in log:                                        # log is in seq order; last live write wins
        if w.by not in excluded:
            current[w.chan] = w.val
    return current


def reify_current_pointer(log: list[Write], excluded: set[str]) -> tuple[AttrGraph, str, list[str]]:
    """Build the reified `current` version in a state graph: a `<current>` node wired to exactly the
    LIVE write nodes (the hyperedge pointing at the current nodes representing the state). Every write —
    including the excluded clobber — is minted (monotone: nothing deleted); only the live ones are under
    `<current>`. Returns (graph, current_node, retained_but_not_current_write_labels)."""
    sg = AttrGraph()
    cur = sg.add_node("<current>")
    not_current: list[str] = []
    # keep only the last live write per channel as "current" (last-writer-wins), like the projection.
    live_by_chan: dict[str, Write] = {}
    for w in log:
        if w.by not in excluded:
            live_by_chan[w.chan] = w
    for w in log:
        label = f"{w.chan}={w.val!r}@{w.seq}(by {w.by})"
        wn = sg.add_node(label)
        if live_by_chan.get(w.chan) is w:
            sg.add_relation(cur, "has", wn)              # the current pointer includes this write
        else:
            not_current.append(label)                    # retained in the graph, but not current
    return sg, cur, not_current


# --- the loop -------------------------------------------------------------------------------------

@dataclass
class Run:
    label: str
    procedure: str
    order: list[str]
    log: list[Write]
    excluded: set[str]

    @property
    def current(self) -> dict:
        return project_current(self.log, self.excluded)

    @property
    def in_place(self) -> dict:
        """What a MUTABLE dict would have ended at (the procedure_assembly model): every write applied
        destructively, last-writer-wins with NO exclusion — the clobber sticks."""
        d: dict = {}
        for w in self.log:
            d[w.chan] = w.val
        return d

    @property
    def ok(self) -> bool:
        return self.current == {"scaled": 10, "shifted": 15}


def run_versioned(label: str, steps: tuple[str, ...], alternatives: tuple[Fragment, ...] = ()) -> Run:
    rules = _load("procedure.cnl", "planning.cnl", "planning_execution.cnl")
    g = AttrGraph()
    _stage_op(g, INIT)
    _stage_op(g, SCALE)
    for frag in {LIBRARY[s] for s in steps} | set(alternatives):
        _stage_op(g, frag)

    procedure = "to report : " + " then ".join(steps)
    h.ingest(g, [], procedure)

    log: list[Write] = []
    order: list[str] = []
    h.ingest(g, rules, "run report",
             tools={"act": _versioned_act_tool(log, order, x=5), "rank": _rank_noop()})
    return Run(label, procedure, order, log, _excluded_fragments(g))


def _show(r: Run) -> None:
    print(f"  [{r.label}]  authored: {r.procedure!r}")
    print(f"     ran: {r.order}   excluded by rules: {sorted(r.excluded) or '{}'}")
    print(f"     write history (append-only, nothing deleted):")
    for w in r.log:
        live = "" if w.by not in r.excluded else "   <- superseded (by an excluded fragment); RETAINED"
        print(f"        seq {w.seq}: {w.chan} = {w.val!r}   by {w.by}{live}")
    _, _, not_cur = reify_current_pointer(r.log, r.excluded)
    print(f"     <current> pointer includes the live writes; NOT current (still in graph): {not_cur or '[]'}")
    print(f"     in-place dict (procedure_assembly's model): {r.in_place}")
    print(f"     PROJECTED current version (this probe):      {r.current}   => fully correct: {r.ok}\n")


def main() -> None:
    print("VERSIONED RECOVERY — the clobber is REVERSED by re-projecting past an excluded write.\n")

    print("PART 1 — the CLOBBER, versioned (scale then shift_bad). Same rules, same discrepancy/replan;")
    print("the only change is append-only writes + a current projection that obeys the `excluded` marker.\n")
    _show(run_versioned("clobber->complete", ("scale", "shift_bad"), alternatives=(SHIFT_OK,)))

    print("PART 2 — the OMISSION, versioned (scale then shift_flaky): already correct without versioning;")
    print("stays correct here — versioning never hurts the case replan already handled.\n")
    _show(run_versioned("omission", ("scale", "shift_flaky"), alternatives=(SHIFT_OK,)))

    print("The in-place model ended `scaled=15` (procedure_assembly PART 3, unrecoverable). The versioned")
    print("projection ends `scaled=10`: scale's correct write was appended, never overwritten, and the")
    print("`excluded` marker (set by the SAME rule) drops the clobber from the current version. Monotone")
    print("substrate + first-class versions => runtime recovery is COMPLETE. Design-time is an")
    print("earliness optimization, not a correctness necessity.")


if __name__ == "__main__":
    main()
