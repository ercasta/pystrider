"""Slice 0 on `../ugm@restart` — does THE BET survive the new floor?

    python experiments/restart_bet.py

⚠ THIS RUNS THE OTHER ENGINE, by path, exactly as `restart_scale.py` does, and for
the same reason: `pystrider` itself runs on ugm `main` via the `ugm-classic`
worktree. It imports nothing from `pystrider`.

⚠ AND IT IS NOT A TEST MODULE, DELIBERATELY. Putting `creazioni/ugm` on `sys.path`
makes `import ugm` resolve to `restart` for the WHOLE PROCESS, so a pytest module
doing this would silently re-point every other test in the run at an engine they
were not written for. That is survey §0's trap — *the same import resolves to two
different engines depending on where you stand* — arriving from the third
direction. It is a runner with its own checks and its own exit code, in the shape
`ugm/backward.py` uses.

THE BET, unchanged across three engines: **ONE authored description, read one way
recognizes code, read the other way writes it.**

  * engine 1 (`ugm` classic) — a CNL rule's BODY recognizes, its HEAD writes.
    Rode on pattern matching.
  * engine 2 (`microfunctions`) — deleted pattern matching, so the bet moved to
    `driver.establishes`: a function's BODY versus its EFFECTS. That rewrite is
    `pystrider/` as it stands.
  * engine 3 (`restart`) — what this file measures.

⭐⭐⭐ THE RESULT: THE BET IS NATIVE HERE, AND IT IS THE CLEANEST OF THE THREE.
`restart` has pattern-matching rules again (`implies({ant}, {con})`) AND a backward
reader over the same rules. So one authored rule is read forwards by the matcher
(structure ⟹ description = RECOGNIZE) and backwards by `<plan>`/`<expand>`
(description ⟹ the structural subgoals = WRITE). Neither reading is ours to build;
both ship. `establishes` — the module survey §2 lists as having no counterpart, and
the one the whole engine-2 rewrite was founded on — turns out **not to be needed**,
because what it reconstructed by reading a function body is what an antecedent
already is.

WHAT EACH CHECK ESTABLISHES:

  1  forwards, the description is CONCLUDED off structure — and `why()` names every
     part it read. Engine 2 had no trail; this is strictly more.
  2  backwards, the SAME rule yields exactly the structural parts, instantiated,
     with the subject bound and the unfilled parts left as variables.
  3  the perturbation: rename ONE label in the rule and BOTH halves go dark. This
     is the only check that distinguishes one description from two that happen to
     agree, and it is the pin `pystrider`'s own bidirectional work rests on.
  4  the write half closes: a TOOL fills the holes the description named, an
     AUTHORED rule re-asks the check, and the same rule read forwards concludes
     the description off the structure it caused to exist.

⚠⚠ AND THE CONTROL IS THE MORE USEFUL HALF OF 4 — see `_write` below. Without the
re-ask the description STILL holds; what is broken is that the plan reports every
subgoal `blocked` about a goal that is true. Pinning `holds` would have been a
check that could not fail.
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UGM_RESTART = r"C:\Users\ercas\creazioni\ugm"


def _engine():
    sys.path.insert(0, UGM_RESTART)
    import ugm

    assert "ugm-classic" not in ugm.__file__, (
        f"expected the restart engine, resolved {ugm.__file__} — is creazioni/ugm on `main`?"
    )
    from ugm import Machine, PLUS
    from ugm.core.text import load          # ⚠ `ugm.text` until `f632cc4 retire`

    return Machine, PLUS, load


Machine, PLUS, load = _engine()


# -- the one authored description -----------------------------------------------
#
# The neutral labels are `pystrider/rules/patterns.mf`'s, deliberately: this is the
# same description that package authors as a microfunction, restated in the only
# form `restart` has. ⚠ Intake's words and the pattern's words still must not
# coincide — `for_stmt` is Python's, `iteration` is ours — which is the constraint
# a bridge exists to make explicit, and it survives the substrate change untouched.
PATTERN = """
rule <iter> = implies(
  { +for_stmt(?n), +target(?n, ?v), +over(?n, ?s), +body(?n, ?b) },
  { +iteration(?n) } )
"""

# What an intake would have deposited for `for x in items: ...`.
CODE = """
fact +for_stmt(loop1)
fact +target(loop1, x)
fact +over(loop1, items)
fact +body(loop1, blk1)
"""

# ⚠ AUTHORED, not Python. A tool filling a hole is an event the agent should be
# able to reason about, and upstream's own lesson from `reenter` is that the
# decision must not sink into the machinery. `built(?w)` is the occasion; the rule
# says that occasion warrants asking the check again.
#
# It satisfies upstream's criterion for an occasion — *warranted only if re-asking
# cannot produce one* — because the tool declines a goal it has already filled, so
# the second ask produces no second `built`.
REASK = """
rule <reask> = implies( { +check(?p, ?w), +built(?w) },
                        { +again(check(?p, ?w), built(?w)) } )
"""

GOAL_SUBJECT = "loop9"          # a node that does not exist in any structure yet


def _plan_facts(m, kinds) -> set:
    out = set()
    for mo in m.chain.moments:
        for e in mo.delta:
            if e.sign == PLUS and m.g.relation_of(e.proposition) in kinds:
                out.add(m.g.show(e.proposition))
    return out


# -- 1. forwards: the description is recognized ---------------------------------

def recognize(pattern: str = PATTERN, code: str = CODE):
    """Read the rule forwards: structure ⟹ description.

    ⚠ ONE `load` call, never two — two build two scopes, so the facts' relations
    are TWINS of the rule's and nothing matches while the run reports a contented
    quiescence. Upstream's most-recorded trap, and it caught this session twice.
    """
    m = Machine()
    kb = load(m, pattern + code)
    m.run(limit=500)
    p = kb.term("iteration(loop1)")
    return m, m.holds(p), m.why(p)


# -- 2. backwards: the same rule says what would have to be built ---------------

def decompose(pattern: str = PATTERN):
    """Read the SAME rule backwards: description ⟹ the structural subgoals.

    No code facts at all. What comes back is the write half's work order.
    """
    m = Machine()
    kb = load(m, pattern)
    goal = kb.term(f"iteration({GOAL_SUBJECT})")
    m.gate.write(m.focus, m.g.rel(m.GOAL, goal), PLUS, mention=True)
    m.run(limit=2000)
    return m, _plan_facts(m, {m.SUBGOAL, m.BINDS, m.EXPANDS})


# -- 4. the write half, closed --------------------------------------------------

def _write(reask: bool):
    """Fill the holes the description named, and read the description back off them.

    The tool knows nothing about iteration. It is handed a subgoal the plan could
    not satisfy and mints a node per free variable — which is what writing code IS,
    allocating a node. **WHAT to mint is the description's to say**, and it says it
    by being an antecedent. That is the whole write half.

    ⚠⚠ THE CONTROL IS THE POINT. With `reask=False` the tool still mints, the
    forward rule still fires, and `iteration(loop9)` still holds — so a pin on
    `holds` CANNOT FAIL and would have measured nothing. What the re-ask changes is
    whether the PLAN knows: without it every subgoal is reported `blocked` while
    the goal is true. A planner confidently blocked about something that holds is
    the silent-wrong shape, not a missing feature.
    """
    m = Machine()
    kb = load(m, PATTERN + (REASK if reask else ""))
    minted, filled_for = [], set()

    def mint(_m, frame, e):
        g = m.g
        if g.relation_of(e.proposition) is not m.CHECK or e.sign != PLUS:
            return None
        _plan, goal = g.members(e.proposition)
        if goal in filled_for:
            return None     # ⚠ a tool that must answer everything is one nothing can decline
        filled_for.add(goal)
        prop = goal
        for i, mem in enumerate(g.members(goal)):
            if g.is_var(mem):
                # ⚠ SCOPED, not `g.atom` — a Python-minted relation is a TWIN of the
                # corpus's and the rule that reads it never fires. Cost this session
                # one wrong "the re-ask does not work".
                fresh = kb.atom(f"n{len(minted)}")
                prop = g.rel(g.relation_of(prop),
                             *[fresh if j == i else x for j, x in enumerate(g.members(prop))])
        minted.append(g.show(prop))
        m.gate.write(frame, prop, PLUS, source=m.KB, mention=True)
        m.gate.write(frame, g.rel(kb.atom("built"), goal), PLUS, source=m.KB, mention=True)
        return None

    kb.answerer("minter", "check", mint)
    goal = kb.term(f"iteration({GOAL_SUBJECT})")
    m.gate.write(m.focus, m.g.rel(m.GOAL, goal), PLUS, mention=True)
    m.run(limit=4000)
    return {
        "minted": minted,
        "achieved": _plan_facts(m, {m.ACHIEVED}),
        "blocked": _plan_facts(m, {m.BLOCKED}),
        "holds": m.holds(goal),
    }


# -- the runner -----------------------------------------------------------------

def run() -> int:
    checks, failures = 0, 0

    def check(name: str, ok: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}")

    print("THE BET on ../ugm@restart — one description, read two ways\n")

    # 1 --------------------------------------------------------------------
    m, verdict, why = recognize()
    print("-- 1. forwards: the description is RECOGNIZED off structure --")
    print(f"     holds(iteration(loop1)) = {verdict}")
    for line in why[:6]:
        print(f"     {line[:96]}")
    check("structure concludes the description", verdict == "+")
    check("and the trail names every part it read — engine 2 had none",
          all(w in " ".join(why) for w in ("for_stmt", "target", "over", "body")))

    # 2 --------------------------------------------------------------------
    m2, plan = decompose()
    print("\n-- 2. backwards: the SAME rule yields the work order --")
    for f in sorted(plan):
        print(f"     {f[:96]}")
    subgoals = " ".join(sorted(plan))
    check("every structural part becomes a subgoal",
          all(w in subgoals for w in ("for_stmt", "target", "over", "body")))
    check("the subject is BOUND, the unfilled parts stay variables",
          f"?n, {GOAL_SUBJECT}" in subgoals and "?b" in subgoals)

    # 3 --------------------------------------------------------------------
    # ⭐ The perturbation. Rename ONE label and both halves must go dark together;
    # that is what tells one description from two that agree. Half-dark would be
    # worse than either — it would mean the two readings share no author.
    print("\n-- 3. the perturbation: rename ONE label --")
    bent = PATTERN.replace("+over(?n, ?s)", "+across(?n, ?s)")
    _, bent_verdict, _ = recognize(pattern=bent)
    _, bent_plan = decompose(pattern=bent)
    bent_txt = " ".join(sorted(bent_plan))
    print(f"     forwards  holds = {bent_verdict}   (was +)")
    print(f"     backwards asks for `across`, not `over`: "
          f"{'across' in bent_txt and 'over(' not in bent_txt}")
    check("recognition goes dark", bent_verdict != "+")
    check("and the work order changes WITH it — one author, not two",
          "across" in bent_txt and "over(" not in bent_txt)

    # 4 --------------------------------------------------------------------
    print("\n-- 4. the write half, and its control --")
    off, on = _write(reask=False), _write(reask=True)
    for label, r in (("no re-ask (control)", off), ("re-ask authored", on)):
        print(f"     {label:22} minted {len(r['minted'])}  "
              f"achieved {len(r['achieved'])}  blocked {len(r['blocked'])}  "
              f"holds={r['holds']}")
    print(f"     minted: {on['minted']}")
    check("the tool fills every hole the description named", len(on["minted"]) == 4)
    check("every subgoal is achieved and none is blocked",
          len(on["achieved"]) == 4 and not on["blocked"])
    check("the SAME rule reads the description back off what was built",
          on["holds"] == "+")
    check("CONTROL: without the re-ask the goal holds ANYWAY — so `holds` alone "
          "could not fail", off["holds"] == "+")
    check("CONTROL: what breaks instead is the PLAN — blocked about a true goal",
          len(off["blocked"]) == 4 and not off["achieved"])

    print(f"\n{checks} checks, {failures} failing")
    if not failures:
        print("\n⭐ The bet is native on this floor: pattern-matching rules came back, and a")
        print("   backward reader over the same rules ships. `driver.establishes` — the")
        print("   module the engine-2 rewrite was founded on — is not needed, because what")
        print("   it reconstructed from a function body is what an antecedent already is.")
        print("⚠ What this does NOT establish: scale (see docs/restart_port_survey.md §6),")
        print("   intake/emit on a substrate with no attributes, or the nine other modules")
        print("   §2 counts as missing. It establishes that the CENTRAL BET is not one of them.")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
