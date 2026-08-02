"""SLICE 9 — GENERATION ON ONE AGENDA: the irreversible step is DECLARED, and a watcher can stop us.

`../ugm` shipped `loop.py`: every control loop in the engine — the interpreter, a search, a replay, a
whole goal-pursuit — is a node plus a `step`, on one ordered agenda that rotates. Two things in it are
ours rather than merely elegant, and this probe is the two of them measured on the app generator slice 7
built.

**⭐⭐ 1. A CODE GENERATOR'S IRREVERSIBLE STEP IS RUNNING WHAT IT WROTE, and now it is declared.** The
whole of `strider` up to `ast.unparse` is imagination: a plan can be discarded, a graph can be dropped,
text costs nothing. `exec`ing that text cannot be taken back. `strider/rules/world.mf` puts both steps
behind `DISPATCH` and registers them differently — `render_app` observes, `drive_app` acts — so
`loop.verb_of` answers `look` for the first and `act` for the second **before either is taken**, and a
driver stops with the source in hand and nothing run.

**⭐⭐ 2. A WATCHER AUTHORED AS TEXT JUDGES OUR OWN GENERATION MID-FLIGHT AND STOPS IT.**
`strider/rules/watch.mf` reads the live search's `steps` against a budget and writes `stop`. It is on the
same agenda as the thing it watches, so it judges *while* the search runs rather than delivering a
post-mortem — and the refusal that comes back is honest: no plan, no source, and the app never ran.

**⚠⚠ THE FINDING, and it is about `verb_of` rather than about us: THERE ARE TWO LINES OF
IRREVERSIBILITY AND THE VOCABULARY HAS ONE WORD.** `loop.verb_of` answers `act` for a `replay`
*unconditionally* — it does not look at what the plan's operations do. For ugm that is right and safe: a
replay applies operations to the real graph and nothing is ever undone. But `strider`'s replay only
rearranges an AST we own, and by that reading a generator must stop before it has anything to show, which
makes the pause useless exactly when it should be informative.

So this probe's driver declines a step that is `act` **and** an `activation` — i.e. one sitting on a
`DISPATCH`, which is the only way an effect leaves the graph at all (`dispatch.py`'s own claim). The
distinction it is drawing is *irreversible inside the system* against *irreversible in the world*, and
`verb_of` cannot express it because a replay's verb is a constant. ⚠ We are not overriding a safety
property: we are stopping at a **later** line and saying so, and the pin below reads the world at the
moment we stopped rather than trusting the policy. Reported as `docs/feedback_microfunctions.md` §12.

**⚠ WHAT IS STILL PYTHON, stated so nobody reads more into this than it says.** The agenda holds the
pursuit, the watcher, the render and the drive; the `while` around `tick` is ours, which is exactly what
`loop.run`'s docstring says a driver is for. Setting the world up — intaking the skeleton, minting the
build, opening the goal — is Python and unchanged from slice 7.

**PREDICTIONS, recorded before running, and the one that missed is the useful one:**

1. *The watcher overshoots its budget, and by a bounded amount.* It polls at one instruction per tick
   while the search imagines one state per tick, so it **samples rather than traps**. Predicted
   `budget .. budget + 8` states. **MEASURED: budget 8 stopped at 18 — a miss, by more than the band.**
   The assumption it names: I costed the polling cycle at 7 instructions and it is 8, because jumping
   back to `.again` spends a tick like any other instruction; and with four tasks rotating, one poll
   costs 32 ticks and the search advances 8 states inside it. So the resolution of this monitor is
   **8 states, plus wherever its first poll happens to land** — which is the whole of the overshoot and
   is not a small correction to the predicted band but a different shape of answer.
2. *Stopping before the drive leaves a complete, valid app.* The source parses, and the event trace is
   empty because nothing ran it. **Held.**
3. *The same generation with a generous budget builds and drives the app successfully* — the control
   without which #1 measures only that a small number is small. **Held: 24 states, driven, WORKS.**

**⭐⭐ AND THE MEASUREMENT NOBODY ASKED FOR, which is the real finding: A SAMPLING MONITOR CANNOT JUDGE A
FAST COMPUTATION.** The default *guided* search settles this app in **7 imagined states**, and the
watcher cannot bite it at any budget — its first poll lands after the search is already done, so the only
verdict it can reach is "over". Everything about the mechanism is fine and it is still useless there.
That is why part 3 below watches an **unguided** search (24 states): ugm's guidance is so effective on
this goal that it removes the very condition under which a budget monitor is meaningful. ⚠ The general
form is worth carrying: *self-monitoring on a shared agenda has a resolution, and a computation faster
than that resolution is unwatchable by it.* Trapping — a check inside the search's own step — is the
other design, and it is the one that costs a seam.

Run it: `python -m experiments.strider_agenda`   (needs `pip install textual`)
"""
from __future__ import annotations

import ast

import strider
from strider.emit import emit
from strider.mf import Focus, Machine, dispatch, driver, function, loop as L
from strider.library import Library

from experiments.strider_app import Cart, build_goal, decisions, run_events, setup

#: The two tools, and the difference between them is the slice. ⚠ `drive_app` is registered WITHOUT
#: `observes`, which is the safe default rather than an omission — an unmarked tool counts as changing
#: the world, and this one does.
RENDER, DRIVE = "render_app", "drive_app"


def register_tools(lib) -> None:
    """Wire the two handlers to this library. ⚠ `dispatch`'s registry is global, so this is re-run per
    generation — the handlers close over the graph they belong to and must not outlive it."""

    def render(g, build):
        """Graph in, text out. Nothing outside the machine can tell this ran, which is what `observes`
        claims and why the driver below takes this step without pausing."""
        source = emit(Library(g, (), ()), g.target(build, "module_node"))
        g.put(build, source=source)
        return source

    def drive(g, build):
        """⚠ THE IRREVERSIBLE ONE. `exec` of source this system wrote, driven through a real Textual
        Pilot. There is no undo for this and there should not appear to be one."""
        events = run_events(g.attr(build, "source"), str(g.attr(build, "spend")))
        g.put(build, ran=True, events=tuple(events))
        return events

    dispatch.register(RENDER, render, observes=True)
    dispatch.register(DRIVE, drive)


# --- putting the whole pipeline on one agenda -----------------------------------------------------------

def open_generation(cart: Cart = Cart(), *, budget: int | None = None, **kw) -> dict:
    """Everything scheduled, nothing done. Four tasks, one agenda, in the order they were asked for."""
    from strider.mf import thread as T

    lib, build, module = setup(cart)
    g = lib.graph
    register_tools(lib)

    goal = build_goal(g, build)
    pursuit = driver.open_pursuit(g, goal, T.open_thread(g, "build app"), build, **kw)
    agenda = L.open_loop(g, "generating an app")
    L.schedule(g, agenda, pursuit, why="derive the app")
    L.schedule(g, agenda, _activation(g, "render_the_app", b=build, p=pursuit), why="render it")
    L.schedule(g, agenda, _activation(g, "run_the_app", b=build), why="run it")

    watcher = None
    if budget is not None:
        # ⚠ The budget is a NODE, not a Python number, because the watcher reads it with `ATTR` like
        # anything else. What it costs to change the budget should be what it costs to change any fact.
        watcher = _activation(g, "watch_generating", p=pursuit, budget=g.mint("budget", value=budget))
        L.schedule(g, agenda, watcher, why="do not plan forever")

    return {"lib": lib, "graph": g, "build": build, "module": module, "cart": cart,
            "goal": goal, "pursuit": pursuit, "loop": agenda, "watcher": watcher}


def _activation(g, name: str, **args):
    """A stored function, started and not stepped — a task the outer loop can advance.

    ⚠ `of=` is what makes it drivable at all: `loop.advance` REFUSES an activation whose program exists
    only as a Python tuple, because it could then be resumed by nothing but the caller holding it."""
    focus = Focus(g)
    for param, node in args.items():
        focus.open(param, node)
    return Machine(function.load(g, name)[1]).start(g, focus, of=function.find(g, name))


def leaves_the_machine(g, task) -> bool:
    """⚠ THE POLICY, and it is a judgement rather than a reading — see the module docstring's finding.

    `act` on a replay means *this changes the graph and nothing is undone*; `act` on an activation means
    *this is sitting on a DISPATCH*, and `dispatch` is the one place an effect leaves the graph. Only the
    second is irreversible in the world, and a generator that stopped at the first would pause before it
    had produced anything to look at."""
    return L.verb_of(g, task) in L.IRREVERSIBLE and g.kind(task) == "activation"


def generate(state: dict, *, max_ticks: int = 6000, allow_the_drive: bool = False,
             policy=leaves_the_machine) -> dict:
    """Tick the agenda, stopping before the first step that leaves the machine.

    Returns what happened, read off the graph rather than accumulated in Python where it can drift from
    it. `allow_the_drive` is the second half of the demonstration: the same loop, told to go on."""
    g, agenda = state["graph"], state["loop"]
    verbs, order, stopped_at = [], [], None

    for _ in range(max_ticks):
        here = L.agenda(g, agenda)
        if not here:
            break
        if not allow_the_drive and policy(g, here[0]):
            stopped_at = {"task": here[0], "verb": L.verb_of(g, here[0]),
                          "doing": L.describe(g, here[0])}
            break
        rec = L.tick(g, agenda)
        if rec is None:
            break
        verbs.append(rec["verb"])
        order.append(rec["kind"])

    build, search = state["build"], g.target(state["pursuit"], "search")
    return {"state": state, "ticks": L.ticks(g, agenda), "verbs": tuple(verbs), "kinds": tuple(order),
            "stopped_before": stopped_at, "still_waiting": L.agenda(g, agenda),
            "phase": g.attr(state["pursuit"], "phase"),
            "imagined": g.attr(search, "steps") if search else 0,
            "stop_why": g.attr(search, "stop_why") if search else None,
            "report": driver.pursuit_report(g, state["pursuit"]),
            "source": g.attr(build, "source"), "ran": bool(g.attr(build, "ran")),
            "events": g.attr(build, "events") or (),
            "abandoned": g.attr(build, "abandoned")}


# --- reading the outcome --------------------------------------------------------------------------------

def parses(source) -> bool:
    """The emitted app is real Python — checked by parsing it, which is not running it."""
    if not source:
        return False
    try:
        ast.parse(source)
    except SyntaxError:
        return False
    return True


def narrate(out: dict) -> str:
    stopped = out["stopped_before"]
    where = f"stopped before: {stopped['verb']} — {stopped['doing']}" if stopped else "agenda emptied"
    return (f"{out['ticks']:>4} ticks | phase {out['phase']:<8} | imagined {out['imagined']:>3} | "
            f"source {'yes' if out['source'] else ' no'} | ran {str(out['ran']):<5} | {where}")


def main() -> None:
    print("=" * 108)
    print("SLICE 9 — one agenda: derive, render, run. The last one is an ACT and the loop knows it first.")
    print("=" * 108)

    print("\n1. STOPPING AT THE LAST REVERSIBLE MOMENT")
    out = generate(open_generation())
    print("  ", narrate(out))
    print("   the app was written and NOT run:", parses(out["source"]), "/ events:", out["events"])
    print("   still on the agenda:", tuple(out["state"]["graph"].kind(t) for t in out["still_waiting"]))

    print("\n2. AND WHEN ALLOWED, IT TAKES THE STEP")
    out2 = generate(open_generation(), allow_the_drive=True)
    print("  ", narrate(out2))
    print("   decided:", decisions(out2["state"]))
    print("   drove:  ", out2["events"])

    print("\n3. THE WATCHER — authored as text, judging our own search mid-flight")
    print("   UNGUIDED, because the guided search settles in 7 states and no sampling monitor can")
    print("     reach a verdict inside that. The mechanism is fine; the computation is too fast for it.")
    for budget in (8, 400):
        watched = generate(open_generation(budget=budget, guided=False), allow_the_drive=True)
        print(f"   budget {budget:>3}:", narrate(watched))
        print(f"{'':14}why: {watched['stop_why'] or watched['report'].get('why', '')[:90]}")

    print("\n" + "=" * 108)
    print("The app that existed but had not run, at the moment the loop declined to run it")
    print("=" * 108)
    print(out["source"])


if __name__ == "__main__":
    main()
