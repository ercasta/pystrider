"""Slice 2 — ONE GOAL DRIVES A CODE REPAIR, on `../ugm@restart`.

    python experiments/pystrider_repair.py

⚠ A RUNNER, not a pytest module (see `pystrider/mf.py`).

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
**The answer measured here is `+unmet($p, ...)`:** a repair is proposable only once
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

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r"C:\Users\ercas\creazioni\pystrider")

from pystrider import corpus                    # noqa: E402
from pystrider.emit import emit                 # noqa: E402
from pystrider.evaluator import evaluate, register  # noqa: E402
from pystrider.facts import Facts               # noqa: E402
from pystrider.intake import intake             # noqa: E402

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


#: ⚠⚠ SECTIONS 2 ONWARDS LOST THEIR ENGINE ON 2026-08-23, and that is most of this
#: probe. What drove them was a GOAL — `gate.write(focus, rel(GOAL, goal), PLUS)` — and
#: `focus`, `GOAL`, `SUBGOAL` and the whole backward reader went with the scratchpad
#: collapse. Goal management is a corpus's own business now
#: (`../ugm/ugm/rules/bundle.ugm`), so this comes back by AUTHORING, not by patching.
#:
#: The narrative is kept whole rather than trimmed to section 1: a probe that silently
#: drops the sections it can no longer run reads as if it had always been this small.
#: `docs/transplant.md`; the expectations survive as xfail(strict) in tests/test_repair.py.
GONE = "not on this engine - see docs/transplant.md"


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

    # 2 onwards ------------------------------------------------------------
    print("\n-- 2..7. one goal drives the repair --")
    print(f"     {GONE}")
    for line in (
        "what they measured, and it is the whole point of this slice:",
        "  * asserting ONE goal `agrees(f, case)` drove a real source change",
        "  * exactly ONE of two rival repair families fired (relax `>` to `>=`, or",
        "    lower the bound) and EITHER alone genuinely fixes the bug",
        "  * CHANGE then OBSERVE: the evaluation was re-derived after the change,",
        "    so `evaluated` held twice - a repair is not done until its effect is seen",
        "  * an INDEPENDENT GATE on the emitted source, because engine 2 once shipped",
        "    a plan that 'succeeded' while emitting byte-identical text",
        "  * the `+unmet($p, ...)` premise is load-bearing: without it a repair",
        "    damages CORRECT code, and the probe stripped it to prove that",
    ):
        print(f"     {line}")

    print(f"\n{checks} checks, {failures} failing")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
