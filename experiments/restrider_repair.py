"""Slice 2 — ONE GOAL DRIVES A CODE REPAIR, on `../ugm`.

    python experiments/restrider_repair.py

⚠ A RUNNER, not a pytest module (see `restrider/mf.py`).

The same off-by-one guard bug engine 2 repaired, re-derived here — deliberately, so
the result checks against a real prior one instead of against nothing. The bug is
given as a CASE, never as a spec:

    def classify(age):
        if age > 18:        # wrong: 18 is an adult
            return 'adult'
        return 'minor'

⭐⭐⭐ **WHAT THIS SLICE IS ACTUALLY FOR.** Survey §2 lists *a rule's condition is
its parameter type* as the one item that is **a redesign, not a port** — it is what
let engine 2 delete forward chaining and say *the plan IS the derivation*, and
`restart` has no parameter types. Three candidates were named and none measured.
**The answer measured here is `+unmet(?p, ...)`:** a repair is proposable only once
BACKWARD READING has found the goal unmet, so the search still discovers the order,
and the condition is now an ordinary antecedent member — arguable, and another
author can write a different one. §5 below is the control that makes that a
measurement rather than a story.

WHAT EACH SECTION ESTABLISHES:

  1  the bug is diagnosed from a CASE, by a tool deriving from STRUCTURE
  2  one goal, backward reading, and the repair reaches the REAL graph
  3  the artefact: emit the repaired source and RUN it — the independent gate
  4  the rival family also fixes it, DERIVED from the plan rather than named
  5  ⭐ the control: with the `unmet` member gone, the repair fires on CORRECT code
  6  the membrane: an operator nobody modelled is refused, and nothing is credited
"""
from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# The repo root, so this runs from anywhere — it was an absolute Windows
# path, which made the runner machine-specific for no reason.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from restrider import corpus                    # noqa: E402
from restrider.emit import emit                 # noqa: E402
from restrider.evaluator import evaluate, register  # noqa: E402
from restrider.facts import Facts               # noqa: E402
from restrider.intake import intake             # noqa: E402
from restrider.mf import PLUS                   # noqa: E402

BUG = "def classify(age):\n    if age > 18:\n        return 'adult'\n    return 'minor'\n"
#: ⚠ The control's input: already correct, so any repair fired against it is a
#: repair that was never warranted.
CORRECT = "def classify(age):\n    if age >= 18:\n        return 'adult'\n    return 'minor'\n"


def world(source: str, rules: str = "", scope: str = "s2", given=18, wants="adult"):
    """Intake the code, state the case, bind the evaluator. No goal yet."""
    f = Facts(rules or corpus("patterns", "repair"), scope=scope)
    taken = intake(source, f, "<slice2>")
    function = f.subjects("function")[0]
    case = f.node("case")
    f.fact("case", case)
    f.fact("given", case, f.value(given))
    # ⚠ `wants`, not `expects` — `expects` is one of the engine's own reserved
    # relations, so ours would have been the machinery's. Renamed after the plan
    # answered strangely about it.
    f.fact("wants", function, case, f.value(wants))
    register(f)
    f.run()
    return f, taken, function, case


def pursue(f: Facts, function: int, case: int):
    goal = f.g.rel(f.rel("agrees"), function, case)
    f.m.gate.write(f.m.focus, f.g.rel(f.m.GOAL, goal), PLUS, mention=True)
    steps = f.run(limit=8000)
    return goal, steps


def without(text: str, name: str) -> str:
    """Drop one authored rule from a corpus, by name.

    ⚠ Paren-counted rather than split on blank lines: the first version cut on
    `"\\n\\nrule "` and handed the loader a fragment, which failed loudly. It could
    just as easily have removed a DIFFERENT rule and left something that parsed —
    a control that silently exercises the wrong corpus is the failure this whole
    section is built to avoid.
    """
    start = text.index(f"rule <{name}>")
    i, depth = text.index("(", start), 0
    while True:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return text[:start] + text[i + 1:]


def family(f: Facts) -> str:
    """WHICH repair happened — derived from the graph, never named in advance.

    ⚠ Engine 2 pinned its winner by name and the pin went **silently vacuous** when
    upstream's tie-break flipped: it went on passing while exercising the family the
    planner had just chosen. Both families here are valid, so the winner is an
    undeclared tie-break wearing a result's clothes.
    """
    if f.subjects("lowered"):
        return "lower"
    return "relax" if f.subjects("relaxed") else "none"


def run() -> int:
    checks, failures = 0, 0

    def check(name: str, ok: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}")

    print("slice 2 — one goal drives a code repair\n")

    # 1 --------------------------------------------------------------------
    f, taken, function, case = world(BUG)
    before = evaluate(f, function, case)
    print("-- 1. diagnosis, from a CASE and the STRUCTURE --")
    print(f"     guard found: {bool(f.of('guard', function))}   classify(18) derives {before!r}")
    check("the code is read well enough to say what it does", before.value == "minor")
    ((_case, wanted),) = f.of("wants", function)
    check("...which disagrees with the case, so there is something to repair",
          f.payload(wanted) != before.value)

    # 2 --------------------------------------------------------------------
    goal, steps = pursue(f, function, case)
    won = family(f)
    print("\n-- 2. one goal, and the repair reaches the REAL graph --")
    print(f"     ticks {len(steps)}   repair family chosen: {won}")
    print(f"     agrees = {f.m.holds(goal)}")
    check("the goal comes to hold", f.m.holds(goal) == PLUS)
    check("a repair family was applied", won != "none")
    check("CHANGE then OBSERVE — the evaluation was re-derived after the change",
          len(f.of("evaluated", function)) == 2)

    # 3 --------------------------------------------------------------------
    # ⚠⚠ THE INDEPENDENT GATE. Engine 2 shipped a plan that "succeeded" while
    # emitting BYTE-IDENTICAL source — a plan that changes nothing is
    # indistinguishable from a real fix unless something inspects the ARTEFACT.
    # So: render it, and RUN it.
    repaired = emit(f, taken.module)
    namespace: dict = {}
    exec(compile(repaired, "<repaired>", "exec"), namespace)     # noqa: S102
    print("\n-- 3. the artefact, emitted and EXECUTED --")
    for line in repaired.splitlines():
        print(f"     {line}")
    check("the emitted source is not the source we started with", repaired != BUG)
    check("⭐ and RUNNING it gives the answer the case asked for",
          namespace["classify"](18) == "adult")
    check("...without breaking the case that already worked",
          namespace["classify"](5) == "minor")

    # 4 --------------------------------------------------------------------
    # The rival, DERIVED: whichever family did not win must fix it alone.
    rival = "relax" if won == "lower" else "lower"
    only_rival = without(corpus("patterns", "repair"), won)
    fr, tr, fn_r, case_r = world(BUG, rules=only_rival, scope="rival")
    pursue(fr, fn_r, case_r)
    rival_src = emit(fr, tr.module)
    ns: dict = {}
    exec(compile(rival_src, "<rival>", "exec"), ns)              # noqa: S102
    print(f"\n-- 4. the rival family ({rival}), with {won} removed --")
    print(f"     {rival_src.splitlines()[1].strip()}")
    check(f"the rival ({rival}) also genuinely fixes it — 'found A' is not 'B is wrong'",
          ns["classify"](18) == "adult" and ns["classify"](5) == "minor")
    check("...and it is a DIFFERENT repair, not the same one under another name",
          rival_src != repaired)

    # 5 --------------------------------------------------------------------
    # ⭐⭐ THE CONTROL, and the point of the slice. Strip `+unmet(?p, ...)` from the
    # repair rules and the condition that replaced the parameter type is gone.
    print("\n-- 5. ⭐ the control: what makes a repair unproposable? --")
    # ⚠ The gate is REPLACED, not deleted. `+unmet(?p, evaluated(?f, ?c, ?v))` is
    # also where `?f` and `?c` come from, so removing it leaves the consequent
    # naming variables nothing bound — and the loader refuses the rule outright
    # (*concludes about a variable its antecedent never binds*). That refusal is
    # the engine being careful, but it would have made this control untestable by
    # accident. `+wants(?f, ?c, ?v)` binds the same three and gates nothing: it
    # holds from the start, for correct and broken code alike.
    ungated = corpus("patterns", "repair").replace(
        "+unmet(?p, evaluated(?f, ?c, ?v))", "+wants(?f, ?c, ?v)")
    # ...and the consequent's denial of that same occasion goes with it, or `?p`
    # is left unbound there instead.
    ungated = ungated.replace("-unmet(?p, evaluated(?f, ?c, ?v)),\n    ", "")
    fc, tc, fn_c, _case_c = world(CORRECT, rules=ungated, scope="ungated")
    fc.run()
    ungated_src = emit(fc, tc.module)
    print(f"     correct code, repairs UNGATED -> {ungated_src.splitlines()[1].strip()}")
    # ⚠ `ast.unparse` returns no trailing newline, so compare against the source
    # stripped — not against a previous emit, which would be the stability-is-not-
    # fidelity trap in a place where it happens to look convenient.
    check("without the `unmet` member a repair fires on CORRECT code",
          ungated_src.strip() != CORRECT.strip())
    fg, tg, _fn_g, _case_g = world(CORRECT, scope="gated")
    fg.run()
    gated_src = emit(fg, tg.module)
    print(f"     correct code, repairs GATED   -> {gated_src.splitlines()[1].strip()}")
    check("⭐ with it, correct code is left alone — the condition IS the member",
          gated_src.strip() == CORRECT.strip())
    check("...and no repair family fired at all, not merely a harmless one",
          family(fg) == "none")

    # 6 --------------------------------------------------------------------
    # ⚠⚠⚠ Engine 2's evaluator claimed in PROSE to model `gt`/`ge` only and fell
    # through to `gt` for everything else, deriving `age < 18` as `age > 18`.
    print("\n-- 6. the membrane --")
    fm, _tm, fn_m, case_m = world(
        "def classify(age):\n    if age is 18:\n        return 'adult'\n    return 'minor'\n",
        scope="membrane")
    verdict = evaluate(fm, fn_m, case_m)
    print(f"     `is` -> {verdict!r}")
    check("an operator nobody modelled is refused BY NAME", verdict.refused is not None)
    check("...and nothing is concluded about what the code returns",
          verdict.value is None and not fm.of("evaluated", fn_m))

    print(f"\n{checks} checks, {failures} failing")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
