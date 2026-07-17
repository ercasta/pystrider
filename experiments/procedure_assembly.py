"""Feasibility probe — the COMPOSE->CHECK->RECOVER loop re-expressed as a ugm PROCEDURE, so the
assembly order AND the recovery are KB data (rules), not Python control flow — and the honest limit
that re-expression exposes.

`experiments/compose_recover.py` proved the loop with a Python driver: it composed fragments, ran
grammapy's disjoint-writes check at DESIGN time, and recovered with a hand-written `recover()` that
swapped the colliding fragment. This probe moves the same loop onto ugm's PLANNER + PROCEDURES arc
(completed 2026-07-17, `ugm/cnl/procedure_surface.py` + `corpus/procedure.cnl`), where:

  * the ASSEMBLY is authored as KB text — `to report : scale then shift` (the `to NAME :` surface);
  * the ORDER comes from the procedure's `step_before`, lifted to the planner's `before`;
  * a missing precondition is GAP-FILLED — the planner synthesizes + orders a filler step the
    procedure never named (here: `init`, which `scale`/`shift` need but no step declared);
  * the RECOVERY is the planner's own DISCREPANCY -> REPLAN rules (content-blind, in
    `corpus/procedure.cnl`): a step that RAN but whose declared effect never materialized is excluded
    and an ALTERNATIVE producer of that effect is chosen. No Python `if` — a rule does the swap.

Trust-by-execution is native: the act tool RUNS each fragment's statement against a real `out` dict
and reports back only the effects the world actually shows. A failure is DISCOVERED by running, not
declared, and the recovery is driven off that observation. No language model anywhere.

THE FINDING (the honest, valuable part). Runtime replan is NOT a drop-in for the design-time check —
it recovers a DIFFERENT failure class:

  * an OMISSION (a step that ran and produced NOTHING — a real action failure: the network was down)
    is recovered PERFECTLY: replan runs an alternative producer and the output is correct (PART 2).
  * a CORRUPTION (a clobber: a step that ran and overwrote a SIBLING's already-committed value) is
    only PARTIALLY recovered: replan re-achieves the missing effect, but it CANNOT UN-WRITE the
    committed bad value — ugm's world is monotone, the side effect already happened (PART 3).

So the two probes are complementary altitudes of one pattern, and design-time is STRICTLY NECESSARY
for interference:

    compose_recover  (design-time)   grammapy disjoint-writes -> SUPPOSE-validated swap  BEFORE running
                                     => the clobber never happens; the shipped program is correct.
    procedure_assembly (runtime)     planner discrepancy      -> rule-driven replan       AFTER running
                                     => heals an omission; too late to reverse a corruption.

The symbolic effect model is coarser than real correctness (`feat_scaled` = "the key exists", not
"the value is right"), so replan heals the omission it can SEE and is blind to the corruption it
cannot — which is precisely the case for catching interference statically, up front.

Run it: `python -m experiments.procedure_assembly`
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

import ugm as h
from ugm import AttrGraph
from ugm.dispatch import call_arg

# The procedures + planner banks ship with ugm (editable install): locate the corpus off the package.
_CORPUS = pathlib.Path(h.__file__).resolve().parent.parent / "corpus"


def _load(*names: str):
    text = "\n".join((_CORPUS / n).read_text(encoding="utf-8") for n in names)
    return h.load_machine_rules(text)


# --- the fragment library (the same PATTERNS as compose_recover, now as planner OPERATORS) ----------

@dataclass(frozen=True)
class Fragment:
    """A fragment as a planner operator. `feature` is the effect it INTENDS to produce (`feat_<key>`);
    `key` is the dict entry a successful run writes; `stmt` is the real Python run against {out, x}.
    A fragment fails in one of two ways: OMISSION (`stmt` writes nothing) or CLOBBER (`stmt` writes a
    DIFFERENT key, overwriting a sibling) — both leave its intended effect unobserved, but the clobber
    also corrupts the sibling's committed value."""
    name: str
    feature: str                    # the declared `add` effect, e.g. "feat_shifted"
    key: str                        # the output-dict key the intended effect corresponds to
    stmt: str                       # the real statement run against {out, x}


INIT = Fragment("init", feature="out_ready", key="", stmt="pass")
SCALE = Fragment("scale", feature="feat_scaled", key="scaled", stmt="out['scaled'] = x * 2")
SHIFT_OK = Fragment("shift_ok", feature="feat_shifted", key="shifted", stmt="out['shifted'] = x + 10")
# OMISSION failure: intends feat_shifted but its action produces nothing (a transient world failure).
SHIFT_FLAKY = Fragment("shift_flaky", feature="feat_shifted", key="shifted", stmt="pass")
# CORRUPTION failure (the clobber): intends feat_shifted but writes the `scaled` key, overwriting scale.
SHIFT_BAD = Fragment("shift_bad", feature="feat_shifted", key="shifted", stmt="out['scaled'] = x + 10")

LIBRARY = {f.name: f for f in (INIT, SCALE, SHIFT_OK, SHIFT_FLAKY, SHIFT_BAD)}
# a feature's canonical (successful) producer — used to know which dict KEY an effect corresponds to.
KEY_OF_FEATURE = {"out_ready": "", "feat_scaled": "scaled", "feat_shifted": "shifted"}


def _feature_holds(env: dict, feature: str) -> bool:
    """OBSERVE whether a declared effect actually holds in the world after execution: `out_ready` once
    the dict exists; `feat_<key>` iff `out` has that key. This is the effect model — presence of a key,
    NOT correctness of its value (the coarseness the finding turns on)."""
    if feature == "out_ready":
        return env["out"] is not None
    return KEY_OF_FEATURE.get(feature, feature) in env["out"]


# --- staging the operators into the planner vocabulary (`op pre P`, `op add E`) ---------------------

def _ensure(g: AttrGraph, name: str) -> str:
    found = g.nodes_named(name)
    return found[0] if found else g.add_node(name)


def _stage_op(g: AttrGraph, frag: Fragment) -> None:
    """Author a fragment as a planner operator: its `add` effect (the feature) + preconditions (every
    writer needs the output dict ready; `init` needs nothing)."""
    o = _ensure(g, frag.name)
    g.add_relation(o, "add", _ensure(g, frag.feature))
    if frag is not INIT:
        g.add_relation(o, "pre", _ensure(g, "out_ready"))


# --- the ACT + OBSERVE boundary (§8): RUN the fragment, report only effects the world shows ---------

def _act_tool(env: dict, order: list[str]):
    """The world-action tool the planner calls per ready op. RUN the op's real statement against `env`
    ({out, x}), then OBSERVE the resulting dict and materialize `<now> true <effect>` ONLY for effects
    that actually hold. A failing fragment (omission or clobber) leaves its intended effect unobserved
    -> the DISCREPANCY rule fires. Content-blind on WHICH op (the rules chose it); it only knows how to
    run a fragment and look at the world — the honest §8 boundary."""
    def handler(g, call_id):
        op = call_arg(g, call_id, "arg")
        if op is None:
            return set()
        if any(g.has_key(r, "done") for r, _ in g.relations_from(op)):
            return set()                                 # an op acts ONCE (the ready token persists)
        frag = LIBRARY[g.name(op)]
        order.append(frag.name)
        exec(frag.stmt, {}, env)                         # RUN the real code against {out, x}
        touched = set()
        now, yes = _ensure(g, "<now>"), _ensure(g, "<yes>")
        for r, e in list(g.relations_from(op)):          # OBSERVE: emit only effects the world SHOWS
            if g.has_key(r, "add") and _feature_holds(env, g.name(e)):
                touched.add(g.add_relation(now, "true", e))
        touched.add(g.add_relation(op, "done", yes))
        return touched
    return handler


def _rank_noop():
    """Close the planner's per-op `rank` call (no comparison needed with a single candidate)."""
    def handler(g, call_id):
        op = call_arg(g, call_id, "arg")
        return {g.add_relation(op, "ranked", _ensure(g, "<yes>"))} if op else set()
    return handler


# --- the loop: author the procedure, run it, verify by the resulting dict ---------------------------

@dataclass
class Run:
    label: str
    procedure: str
    order: list[str]
    out: dict

    @property
    def recovered(self) -> bool:
        """A step ran, failed, and an alternative producer was replanned in (>1 shift* op ran)."""
        return sum(1 for n in self.order if n.startswith("shift")) > 1

    @property
    def scaled_ok(self) -> bool:
        return self.out.get("scaled") == 10          # scale's correct value survived (no clobber)

    @property
    def shifted_ok(self) -> bool:
        return self.out.get("shifted") == 15         # the shifted effect was (re-)achieved

    @property
    def ok(self) -> bool:
        return self.scaled_ok and self.shifted_ok


def run_procedure(label: str, steps: tuple[str, ...], alternatives: tuple[Fragment, ...] = ()) -> Run:
    """Author `to report : <steps>` and `run report`, driving execution through ugm's real planner +
    stepping bank. `alternatives` are extra producers staged (not steps) that REPLAN may choose."""
    rules = _load("procedure.cnl", "planning.cnl", "planning_execution.cnl")
    g = AttrGraph()
    _stage_op(g, INIT)
    _stage_op(g, SCALE)
    for frag in {LIBRARY[s] for s in steps} | set(alternatives):
        _stage_op(g, frag)

    procedure = "to report : " + " then ".join(steps)
    h.ingest(g, [], procedure)                           # AUTHOR the assembly (KB text)

    env = {"out": {}, "x": 5}
    order: list[str] = []
    h.ingest(g, rules, "run report",                     # INVOKE: gap-fill + discrepancy/replan drive it
             tools={"act": _act_tool(env, order), "rank": _rank_noop()})
    return Run(label, procedure, order, env["out"])


def _show(r: Run) -> None:
    print(f"  [{r.label}]  authored: {r.procedure!r}")
    print(f"     ran (execution order): {r.order}")
    print(f"     gap-filled: {'init' if 'init' in r.order else '(none)'}  (a step no `then` named)")
    if r.recovered:
        print(f"     RECOVERED by rule: a shift step's effect was never observed -> DISCREPANCY -> "
              f"REPLAN chose an alternative")
    print(f"     verify by execution: out = {r.out}")
    print(f"       scaled correct (==10): {r.scaled_ok}   shifted achieved (==15): {r.shifted_ok}"
          f"   => fully correct: {r.ok}\n")


def main() -> None:
    print("PROCEDURE-DRIVEN ASSEMBLY — the compose->check->recover loop as KB data (planner + procedures)\n")

    print("PART 1 — a SOUND procedure (scale then shift_ok): planner gap-fills `init`, runs in order\n")
    _show(run_procedure("sound", ("scale", "shift_ok")))

    print("PART 2 — an OMISSION failure (scale then shift_flaky): shift_flaky's action produces nothing")
    print("(the network was down). The planner's DISCREPANCY/REPLAN rules recover it with shift_ok, and")
    print("the output is FULLY CORRECT — replan is perfect for the class it was built for. No Python.\n")
    _show(run_procedure("omission->recovered", ("scale", "shift_flaky"), alternatives=(SHIFT_OK,)))

    print("PART 3 — a CLOBBER (scale then shift_bad): shift_bad overwrites scale's committed value. The")
    print("SAME rules recover the missing `shifted` effect — but scaled stays CORRUPTED (15, not 10):")
    print("runtime replan cannot un-write a committed side effect. THIS is why the design-time check")
    print("(compose_recover) is necessary — it catches interference BEFORE the clobber ever runs.\n")
    _show(run_procedure("clobber->partial", ("scale", "shift_bad"), alternatives=(SHIFT_OK,)))

    print("The assembly order, the gap-fill, and the RECOVERY are all KB rules now — the procedure, not")
    print("a Python driver, does the work. But runtime replan heals an OMISSION, not a CORRUPTION: for")
    print("the interference class, design-time detection (compose_recover) is strictly necessary.")


if __name__ == "__main__":
    main()
