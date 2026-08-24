"""Slice 2b — WHICH REPAIR IS AUTHORED, because otherwise it is declaration order.

    python experiments/restrider_attention.py

⚠ A RUNNER, not a pytest module (see `restrider/mf.py`). The pins are
`tests_restart/test_restrider_attention.py`.

`repair.ugm` has two families and both genuinely fix the bug. Slice 2 established
that and then said so out loud — *the winner is an undeclared tie-break wearing a
result's clothes* — and defended itself by DERIVING the winner from the graph
rather than naming it, so that a pin could not go vacuous the way engine 2's did.

**That defence was real and it was not a choice.** §1 below is the defect it left
standing: swap the two families in the file, change nothing else, and the emitted
artefact changes from `if age >= 18:` to `if age > 17:`. The corpus had no way to
say which it meant.

⭐⭐⭐ **Upstream's `attention` is what makes it sayable, and the reason it works is
that it names a NODE.** `prefer(<R>, key, n)` and `boost` name a RULE, so the same
statement would have come out as *prefer `<relax>`* — keyed on an identity that
goes stale the moment a family is renamed, composed, or joined by a third, which
is why upstream is retiring them (their own arms: node-keyed 13.0, rule-keyed 17.2
to 44.4, one of them worse than doing nothing). What we actually want to say is
not about a rule at all:

> **The case named 18. A repair may not move a boundary the case itself named.**

`<boundary>`'s antecedent states that coincidence — the value the case GIVES is the
literal the guard compares against — and its postcondition attends the OPERATOR
node. `<relax>` is the family that binds that node, so it is the family that lifts.
Nothing in the corpus names `<relax>`.

WHAT EACH SECTION ESTABLISHES:

  1  ⚠ the defect, shown: with no policy, DECLARATION ORDER decides the artefact
  2  ⭐ the authored policy: the same artefact under BOTH orders
  3  the rival policy — one line — takes the other family, also under both orders
  4  ⚠⚠ the silent failure: attending a node the application does not BIND
  5  the policy is silent when the case does not name the boundary

⚠ The other reach attention has — which of a rule's APPLICATIONS is taken, i.e.
which of eight loops gets described first — is measured in `docs/restart_port_
survey.md` §10.5 and is deliberately NOT adopted here. Recognition is not
tick-starved at our sizes, so there is nothing for it to buy yet.
"""
from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from restrider import corpus                        # noqa: E402
from restrider.emit import emit                     # noqa: E402
from restrider.evaluator import register            # noqa: E402
from restrider.facts import Facts                   # noqa: E402
from restrider.intake import intake                 # noqa: E402
from restrider.mf import PLUS                       # noqa: E402

BUG = "def classify(age):\n    if age > 18:\n        return 'adult'\n    return 'minor'\n"

#: What the corpus says today, and the one line another author changes to disagree.
AUTHORED = "after <boundary> => attend(?o, 1)"
RIVAL = "after <boundary> => attend(?r, 1)"


def swapped(text: str) -> str:
    """Declare `<lower>` before `<relax>`, changing nothing else.

    ⚠ This is the whole instrument, so it must not be able to quietly do something
    else: the two families are the tail of the file and `<lower>` is last, so the
    swap is two slices and a join. It is asserted below to have moved something.
    """
    i, j = text.index("rule <relax>"), text.index("rule <lower>")
    return text[:i] + text[j:] + "\n" + text[i:j]


def unpoliced(text: str) -> str:
    """Drop `<boundary>` AND its postcondition — the state slice 2 shipped in.

    ⚠ Both, or the loader is handed a trigger naming a rule that does not exist.

    ⚠⚠ PAREN-COUNTED, and the first version was not — it cut at the first `)` after
    the consequent, which is the one inside `+boundary(?c, ?r)`, and handed the
    loader a fragment. It failed loudly, which is the only reason this note is a
    note: a cut that left something parseable would have run the WRONG corpus in
    the column this whole file exists to compare against. Same lesson as
    `restrider_repair.without`, learned twice.
    """
    start = text.index("rule <boundary>")
    i, depth = text.index("(", start), 0
    while True:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    text = text[:start] + text[i + 1:]
    return "\n".join(l for l in text.splitlines() if not l.startswith("after <boundary>"))


def repair(rules: str, scope: str, given=18, wants="adult"):
    """Intake the bug, state the case, pursue the goal, and report the artefact."""
    f = Facts(rules, scope=scope)
    taken = intake(BUG, f, "<slice2b>")
    function = f.subjects("function")[0]
    case = f.node("case")
    f.fact("case", case)
    f.fact("given", case, f.value(given))
    f.fact("wants", function, case, f.value(wants))
    register(f)
    f.run()
    goal = f.g.rel(f.rel("agrees"), function, case)
    f.m.gate.write(f.m.focus, f.g.rel(f.m.GOAL, goal), PLUS, mention=True)
    steps = f.run(limit=8000)
    return {
        "f": f,
        "family": "lower" if f.subjects("lowered")
                  else ("relax" if f.subjects("relaxed") else "none"),
        "guard": emit(f, taken.module).strip().splitlines()[1].strip(),
        "source": emit(f, taken.module),
        "ticks": len(steps),
        "holds": f.m.holds(goal),
        "policy_fired": bool(f.subjects("boundary")),
    }


def run() -> int:
    checks, failures = 0, 0

    def check(name: str, ok: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}")

    print("slice 2b — which repair, and who says so\n")

    live = corpus("patterns", "repair")
    bare = unpoliced(live)

    # 1 --------------------------------------------------------------------
    # ⚠ THE DEFECT, and it is only visible from outside the run: every check slice
    # 2 owns passes in BOTH columns below. A green suite over a corpus whose
    # artefact depends on the order its rules happen to be written in.
    a = repair(bare, "s1a")
    b = repair(swapped(bare), "s1b")
    print("-- 1. ⚠ with no policy, DECLARATION ORDER decides the artefact --")
    print(f"     as written        -> {a['family']:6} {a['guard']}")
    print(f"     families swapped  -> {b['family']:6} {b['guard']}")
    check("both orders repair the bug — neither is wrong", a["holds"] == PLUS and b["holds"] == PLUS)
    check("⚠ ...and they emit DIFFERENT source, chosen by nothing",
          a["guard"] != b["guard"])
    check("CONTROL: the swap is what moved it — the corpora differ",
          swapped(bare) != bare)

    # 2 --------------------------------------------------------------------
    c = repair(live, "s2a")
    d = repair(swapped(live), "s2b")
    print("\n-- 2. ⭐ the authored policy: `after <boundary> => attend(?o, 1)` --")
    print(f"     as written        -> {c['family']:6} {c['guard']}   ticks {c['ticks']}")
    print(f"     families swapped  -> {d['family']:6} {d['guard']}   ticks {d['ticks']}")
    check("the policy fired — the case names the guard's own literal",
          c["policy_fired"])
    check("⭐ the artefact is the SAME under both declaration orders",
          c["guard"] == d["guard"])
    check("...and it is the family the policy is about, not the one rank gives",
          c["family"] == "relax" and d["family"] == "relax")
    check("the goal still comes to hold — this is a choice, not a veto",
          c["holds"] == PLUS and d["holds"] == PLUS)

    # 3 --------------------------------------------------------------------
    # ⭐ ANOTHER AUTHOR DISAGREES IN ONE LINE. That is the difference between a
    # preference and a tie-break: this one is arguable, and the argument is in the
    # corpus rather than in the order the file happens to be in.
    rival, rival_swapped = (repair(t.replace(AUTHORED, RIVAL), s)
                            for t, s in ((live, "s3a"), (swapped(live), "s3b")))
    print("\n-- 3. the rival policy, `attend(?r, 1)` — the THRESHOLD node --")
    print(f"     as written        -> {rival['family']:6} {rival['guard']}")
    print(f"     families swapped  -> {rival_swapped['family']:6} {rival_swapped['guard']}")
    check("the rival takes the OTHER family", rival["family"] == "lower")
    check("...and it is stable under the swap too — so §2 is the policy, not luck",
          rival["guard"] == rival_swapped["guard"])
    check("CONTROL: the two policies differ by exactly one authored line",
          live.replace(AUTHORED, RIVAL).count(RIVAL) == 1
          and sum(1 for x, y in zip(live.split(), live.replace(AUTHORED, RIVAL).split())
                  if x != y) == 1)

    # 4 --------------------------------------------------------------------
    # ⚠⚠ TWO WAYS TO ATTEND NOTHING, AND BOTH ARE SILENT — a run that behaves
    # exactly like the untaught one. No error, no empty result, nothing to notice.
    # They are different mistakes and the second was nearly written up as the
    # first, so they are separated here.
    print("\n-- 4. ⚠⚠ two ways to attend nothing, both silent --")

    # 4a. A node BOTH families bind. `?f`, `?g` and `?c` are in the antecedent of
    # `<relax>` AND `<lower>`, so attending one lifts them equally. Upstream's
    # *attention that names everything discriminates nothing*, in the smallest
    # possible form: everything is two.
    shared = {}
    for var in ("?f", "?g", "?c"):
        m = repair(swapped(live).replace(AUTHORED, f"after <boundary> => attend({var}, 1)"),
                   f"s4{var[1]}")
        shared[var] = m
        print(f"     (a) attend({var}) — BOTH families bind it -> {m['family']:6} {m['guard']}")
    check("⚠ a node both families bind discriminates nothing — rank decides again",
          all(m["guard"] == b["guard"] for m in shared.values()))

    # 4b. A node NEITHER family binds. The survey's own probe attended a container
    # — the function's body block — and read the null result as *attention buys us
    # nothing*, for a full cycle. The lift reads the nodes an APPLICATION binds;
    # `<relax>` binds the operator and the guard, never the block the guard is in.
    container = swapped(live).replace(
        "{ +wants(?f, ?c, ?v),", "{ +wants(?f, ?c, ?v), +body(?f, ?bl),"
    ).replace(AUTHORED, "after <boundary> => attend(?bl, 1)")
    check("CONTROL: the container variant is a real edit, not a no-op replace",
          "+body(?f, ?bl)" in container and "attend(?bl, 1)" in container)
    m = repair(container, "s4bl")
    print(f"     (b) attend(?bl) — NEITHER binds it     -> {m['family']:6} {m['guard']}")
    check("⚠⚠ attending a container is attending nothing, and it does not announce it",
          m["guard"] == b["guard"])
    check("...and in every one of these the policy rule still FIRED, so the trail "
          "looks exactly like the working one",
          m["policy_fired"] and all(x["policy_fired"] for x in shared.values()))
    check("CONTROL: the node exactly ONE family binds is the one that moves it",
          d["guard"] != b["guard"])

    # 5 --------------------------------------------------------------------
    # The policy states a coincidence, so it must be silent when there is none.
    # ⚠ What this arm CANNOT show, said rather than implied: for this bug 18 is the
    # only case that disagrees, so there is no case that needs a repair WITHOUT
    # naming the boundary. Silence is checked; silence-with-a-repair is not
    # reachable from this fixture.
    e = repair(live, "s5", given=25)
    print("\n-- 5. the policy is silent when the case does not name the boundary --")
    print(f"     given=25 -> policy fired: {e['policy_fired']}   {e['guard']}")
    check("no boundary is claimed — 25 is not the guard's literal",
          not e["policy_fired"])
    check("...and nothing was repaired, because nothing disagreed",
          e["family"] == "none")

    print(f"\n{checks} checks, {failures} failing")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
