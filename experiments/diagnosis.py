"""Feasibility probe — DIAGNOSIS: abduce the ROOT CAUSE of an exception observed at a line.

This probe opens a fourth axis. The productized loop reasons FORWARD: SUPPOSE a value for a
parameter, CHAIN the operational semantics, and read what OUTCOME happens (does line 5 raise?).
The synthesis axis runs the loop backwards over the *code* space (a spec expands into the program).
**Diagnosis runs the same loop backwards over the *hypothesis* space**: you are handed a symptom —
"an `AttributeError` happened at line 5" (one traceback frame, no input given) — and you must abduce
the input that produces it, explain the causal chain, and (optionally) hand the cause to the repair
axis. Analysis asks *what happens if?*; diagnosis asks *what must have been true for this to happen?*

It is abduction, and it closes over the SAME firmware — the mirror is exact:

  | analysis (forward, productized) | diagnosis (this probe) |
  |---|---|
  | SUPPOSE input -> derive every outcome | OBSERVE one outcome -> abduce the inputs that entail it |
  | one hypothesis, all its effects | one effect-at-a-line, the hypotheses that reproduce it |
  | a value hypothesis is GIVEN | the value hypothesis is the UNKNOWN being solved for |
  | RECORD trace = why this input crashes | RECORD trace = why THIS crash happened (the reaching write) |
  | CHOOSE the graded-best repair | CHOOSE the graded-best EXPLANATION (Occam: the most specific cause) |
  | verify a repair by re-execution | verify a cause by re-execution (the SAME forward analyzer) |

Three findings, one line each:

  1. THE ROOT CAUSE IS ABDUCED, not supplied.  `analyze` REQUIRES you name the None parameter;
     diagnosis is handed only the crash site and searches the hypothesis space for the input that
     reproduces it — the missing half of the loop. From "AttributeError at line 5" alone it recovers
     "`raw` was None", plus the reaching-write chain that carried the None to the deref.

  2. CHOOSE PICKS THE MINIMAL (most specific) cause — an Occam prior as a graded selection.  Many
     hypotheses may reproduce a crash ("everything is None" always does); the ROOT cause is the
     smallest set of suspects that still reproduces it. CHOOSE grades candidates by specificity, so a
     single-variable cause wins over a supposing-everything one — parsimony realized through the
     public CHOOSE firmware, not a hand-rolled min.

  3. A SUSPECT IS EXONERATED BY RE-EXECUTION — trust by the checker, again.  A parameter whose being
     None causes a DIFFERENT crash (a different line) — or no crash at all — is not the cause of THIS
     one: the forward semantics simply do not derive the observed outcome under it, so it never
     enters the candidate set. The generator of hypotheses proposes; the forward analyzer disposes.

And then it FIXES: the abduced cause is a value hypothesis of exactly the shape `repair_all` consumes,
so "understand the root cause" flows straight into "and repair it, verified by re-execution" with no
new machinery — diagnosis is the front half of a debugger whose back half is the productized repair
axis. Like the other `experiments/*.py`, this is a probe (not yet productized): the smallest
end-to-end loop that proves the axis is real, pinned by `tests/test_diagnosis.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import ugm as h
from ugm import set_candidate, choose, explain_choice

from pystrider.intake import Intake, intake_function
from pystrider.analysis import Outcome, analyze_all, repair_all, RepairPlan
from pystrider.session import relabel_trace


# The observed-exception -> modelled-effect map, the mirror of `analysis.EFFECTS`. A traceback names
# an exception TYPE; the semantics derive an effect KIND. Today the raising effect we model is the
# None-deref; the table is the extension point (a new raising effect adds one row, no new machinery).
EXC_EFFECTS: dict[str, str] = {
    "AttributeError": "attribute_error",
}


@dataclass(frozen=True)
class Observation:
    """A crash report — the symptom, with NO input given. This is what one traceback frame hands you:
    an exception TYPE at a LINE of a function. Diagnosis abduces the input that produces it."""
    source: str
    line: int
    exc: str = "AttributeError"


@dataclass
class Cause:
    """One candidate root cause: a set of parameters SUPPOSED None. `reproduces` is set only if the
    forward analyzer, re-run under this hypothesis, actually derives the observed exception at the
    observed line — a suspect that does not reproduce it is never a cause (finding 3). `outcome`
    carries the matching outcome's RECORD trace: the causal chain (which write reached the deref)."""
    suspects: tuple[str, ...]            # the parameters this hypothesis supposes None
    reproduces: bool
    outcome: Outcome | None = None       # the matching outcome (same line + effect), with its trace

    @property
    def hypothesis(self) -> dict[str, str]:
        """The value hypothesis this cause names — exactly the shape `analyze` / `repair_all` take."""
        return {p: "none" for p in self.suspects}

    @property
    def specificity(self) -> float:
        """Occam as a graded fit: fewer suspects = a more specific, better explanation. A
        single-variable cause (1 suspect) beats a supposing-everything one. A cause that does not
        reproduce the crash is ineligible (fit 0) — it is not an explanation at all."""
        return (1.0 / len(self.suspects)) if (self.reproduces and self.suspects) else 0.0


@dataclass
class Diagnosis:
    """The result of abducing a crash: the CHOOSE-best (minimal) root cause, every candidate tried
    (auditable, monotone — losers are retained), and the CHOOSE why-trace behind the pick."""
    observation: Observation
    intake: Intake
    root_cause: Cause | None
    candidates: list[Cause]              # every hypothesis evaluated, minimal-first
    choose_trace: list[str] = field(default_factory=list)

    @property
    def reproducing(self) -> list[Cause]:
        return [c for c in self.candidates if c.reproduces]

    def causal_chain(self) -> list[str]:
        """The reaching-write chain that carried the None to the crash site — the outcome's RECORD
        trace, rendered with source labels in place of node ids. The 'why' the forward loop records."""
        if not self.root_cause or not self.root_cause.outcome:
            return []
        return relabel_trace(self.root_cause.outcome.trace, self.intake.label_of)

    def explanation(self) -> list[str]:
        obs = self.observation
        if not self.root_cause:
            return [f"no input makes {obs.exc} happen at line {obs.line} — "
                    f"not reproducible under the modelled value hypotheses"]
        rc = self.root_cause
        who = " and ".join(rc.suspects)
        lines = [f"root cause: {obs.exc} at line {obs.line} happens when {who} is None"]
        if rc.outcome:
            lines.append(f"  the None reaches the deref of {rc.outcome.base_var!r} "
                         f"({rc.outcome.label}) - causal chain:")
            lines += [f"    {t}" for t in self.causal_chain()]
        return lines


def _param_subsets(params: list[str], max_suspects: int) -> list[tuple[str, ...]]:
    """Every non-empty subset of parameters, MINIMAL-FIRST (by increasing size). The search order is
    the parsimony order: the first size that reproduces the crash holds the root cause. Bounded by
    `max_suspects` — the abduction fuel budget, the mirror of intake's unroll / synthesis pool bound."""
    out: list[tuple[str, ...]] = []
    for k in range(1, min(max_suspects, len(params)) + 1):
        out.extend(combinations(params, k))
    return out


def _choose_cause(causes: list[Cause]) -> tuple[Cause | None, list[str]]:
    """Run the public CHOOSE firmware over the reproducing causes, graded by SPECIFICITY, and return
    the winner + the auditable `explain_choice` trace. The alpha-cut drops fit-0 (non-reproducing)
    candidates — exactly `analysis._choose`, but selecting an EXPLANATION instead of a repair."""
    g = h.Graph()
    goal = g.add_node("cause_goal")
    node_of: dict[str, Cause] = {}
    for c in causes:
        opt = g.add_node("+".join(c.suspects) or "none")
        node_of[g.name(opt)] = c
        set_candidate(g, goal, opt, c.specificity)
    winners = choose(g, goal, alpha=0.01)
    trace = explain_choice(g, goal)
    winner = node_of[g.name(winners[0])] if winners else None
    return winner, trace


def diagnose(obs: Observation, *, max_suspects: int | None = None) -> Diagnosis:
    """ABDUCE the root cause of `obs`: enumerate value hypotheses (subsets of parameters supposed
    None, minimal-first), re-run the forward analyzer under each, KEEP the ones that reproduce the
    observed exception at the observed line, and CHOOSE the most specific (smallest) — the root cause.

    The unknown being solved for is the input; the forward semantics are the checker that verifies a
    guess (finding 3 — a suspect stays only if the crash is actually derived under it). No new engine
    machinery: the same `analyze_all` the productized loop runs, driven in reverse over hypotheses."""
    intake = intake_function(obs.source)
    effect = EXC_EFFECTS.get(obs.exc)
    budget = max_suspects if max_suspects is not None else len(intake.params)

    candidates: list[Cause] = []
    if effect is not None:
        for suspects in _param_subsets(intake.params, budget):
            outcomes = analyze_all(intake, {p: "none" for p in suspects})
            match = next((o for o in outcomes
                          if o.line == obs.line and o.kind == effect), None)
            candidates.append(Cause(suspects=suspects, reproduces=match is not None,
                                    outcome=match))

    root_cause, choose_trace = _choose_cause([c for c in candidates if c.reproduces])
    return Diagnosis(observation=obs, intake=intake, root_cause=root_cause,
                     candidates=candidates, choose_trace=choose_trace)


def diagnose_and_fix(obs: Observation) -> tuple[Diagnosis, RepairPlan | None]:
    """Understand the root cause, then REPAIR it. The abduced cause is a value hypothesis of exactly
    the shape `repair_all` consumes, so diagnosis hands straight off to the productized repair axis —
    the fix is verified by re-execution (every candidate edit re-analyzed) just as any repair is. The
    front half of a debugger (abduce the cause) wired to its back half (fix it), on one firmware."""
    dx = diagnose(obs)
    if not dx.root_cause:
        return dx, None
    plan = repair_all(dx.intake, dx.root_cause.hypothesis)
    return dx, plan


# --- live walkthrough ------------------------------------------------------------------------

def main() -> None:
    # A crash report with NO input: just "AttributeError happened at line 5". The reaching-write
    # subtlety the README leads with — `data` is assigned twice; the LAST write (`data = raw`) wins.
    src = (
        "def pipeline(raw):\n"
        "    data = validate(raw)\n"      # line 2: data is the validated (non-None) result ...
        "    data = raw\n"                # line 3: ... clobbered by the raw input
        "    return data.rows()\n"        # line 4->5 (1-based with the def): the deref that raised
    )
    obs = Observation(source=src, line=4, exc="AttributeError")
    dx = diagnose(obs)

    print("DIAGNOSIS - abduce the root cause of a crash, given only the exception + line.\n")
    print(f"observed: {obs.exc} at line {obs.line}   (no input supplied)\n")
    print("hypothesis search (each subset of params supposed None, re-run through the forward "
          "analyzer):")
    for c in dx.candidates:
        verdict = "REPRODUCES the crash" if c.reproduces else "does NOT reproduce it"
        print(f"  - suppose {('+'.join(c.suspects)):16s} None -> {verdict}")

    print()
    for line in dx.explanation():
        print(line)

    print(f"\nCHOOSE picked the most specific cause (fit = specificity):")
    for t in dx.choose_trace:
        print(f"    {t}")

    # Now discrimination: a two-parameter function where each None crashes a DIFFERENT line, so the
    # cause of a SPECIFIC crash isolates one suspect and exonerates the other (finding 3).
    print("\n" + "-" * 88)
    src2 = (
        "def process(cfg, data):\n"
        "    conn = cfg\n"
        "    a = conn.open()\n"           # line 3: crashes iff cfg is None
        "    rows = data\n"
        "    return rows.all()\n"         # line 5: crashes iff data is None
    )
    dx2 = diagnose(Observation(source=src2, line=3, exc="AttributeError"))
    print("A two-suspect function; AttributeError observed at line 3 (conn.open):\n")
    for c in dx2.candidates:
        verdict = "REPRODUCES" if c.reproduces else "exonerated (a DIFFERENT crash, or none)"
        print(f"  - suppose {('+'.join(c.suspects)):16s} None -> {verdict}")
    print()
    for line in dx2.explanation():
        print(line)

    # And the payoff: understand THEN fix, handing the abduced cause to the productized repair axis.
    print("\n" + "-" * 88)
    _dx, plan = diagnose_and_fix(obs)
    print("...and FIX it - the abduced cause feeds `repair_all` (verified by re-execution):\n")
    for line in plan.summary():
        print(f"  {line}")
    print("\nrepaired source:")
    for line in plan.source.splitlines():
        print(f"    {line}")

    print("\nThe point: `analyze` needs you to NAME the None input; diagnosis is given only the crash "
          "and\nrecovers the input - the loop run backwards over the hypothesis space, CHOOSE picking "
          "the most\nspecific cause, each guess verified by the SAME forward analyzer, then handed to "
          "repair. One firmware.")


if __name__ == "__main__":
    main()
