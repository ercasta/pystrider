"""Pins for slice 9 — the generation pipeline on `../ugm`'s single agenda.

Two claims, and each is paired with the thing that would make it vacuous:

* the loop can stop **before** the step that cannot be taken back, with the app written and not run —
  and the control is that it takes the *other* dispatch, the render, without pausing at all;
* a watcher authored as text judges our own search while it runs and stops it — and the control is the
  same search with a generous budget, which succeeds.

⚠ Three of these are PLANTED BUGS. Each breaks one property and must leave the verdict otherwise intact:
that signature is what says the pin is measuring the property rather than the outcome.
"""
import ast

import pytest

from pystrider.mf import dispatch, driver, function, loop as L
import pystrider

from experiments.strider_agenda import (DRIVE, RENDER, Cart, generate, leaves_the_machine,
                                        open_generation, parses)

pytest.importorskip("textual")


# --- 1. the irreversible step is declared, and the loop stops before it ---------------------------------

def test_the_loop_stops_with_the_app_WRITTEN_and_NOT_RUN():
    """⭐ The last reversible moment, for a code generator, is *after* the source exists.

    Everything up to `ast.unparse` can be thrown away for free — a plan, a graph, some text. `exec`ing
    that text cannot be taken back. So the informative place to pause is holding a complete app that has
    never executed, which is what this reads off the graph."""
    out = generate(open_generation())

    assert out["stopped_before"] is not None
    assert out["stopped_before"]["verb"] == L.ACT
    assert "DISPATCH" in out["stopped_before"]["doing"]
    # ⚠ THE WORLD, READ AT THE MOMENT WE DECLINED — not the policy re-asserted.
    assert out["ran"] is False and out["events"] == ()
    assert parses(out["source"]) and "class CheckoutApp" in out["source"]
    assert [g for g in (out["state"]["graph"],)][0].kind(out["still_waiting"][0]) == "activation"


def test_and_when_it_is_ALLOWED_the_app_really_runs():
    """⚠ THE VACUITY CONTROL for the pin above. A loop that could never reach the drive would satisfy
    every line of it, and "we stopped in time" would be a claim about a step that was never available."""
    out = generate(open_generation(), allow_the_drive=True)

    assert out["ran"] is True
    assert any(e.startswith("completed") for e in out["events"])
    assert out["stopped_before"] is None and out["still_waiting"] == ()


def test_a_LOOK_is_NOT_declined_which_is_what_makes_the_pause_about_IRREVERSIBILITY():
    """⭐ The render is a `DISPATCH` too. If the driver were stopping at *any* boundary crossing there
    would be no source at the pause — and there is one, because `render_app` is registered `observes=True`
    and `verb_of` answers `look`.

    ⚠ The default is the unsafe-to-assume one: an unmarked tool counts as changing the world. So the two
    registrations differ in exactly one flag and must be classified oppositely."""
    out = generate(open_generation())

    assert out["source"], "the observing dispatch was declined, so the pause is not about irreversibility"
    assert dispatch.observes(RENDER) is True
    assert dispatch.observes(DRIVE) is False
    assert L.LOOK in out["verbs"] and L.IMAGINE in out["verbs"]


def test_THE_TWO_LINES_OF_IRREVERSIBILITY_and_why_we_stop_at_the_LATER_one():
    """⚠⚠ THE FINDING, pinned so it cannot be mistaken for us weakening a safety property.

    `loop.verb_of` answers `act` for a `replay` **unconditionally** — it never looks at what the plan's
    operations do. For ugm that is right: a replay writes to the real graph and nothing is undone. But
    `pystrider`'s replay only rearranges an AST we own, so ugm's line falls *before* anything exists to
    look at, and a generator pausing there can show its author nothing.

    This runs the same generation under ugm's own line and pins the cost: the loop stops with **no
    source**, mid-plan. Reported as `docs/feedback_microfunctions.md` §12."""
    strict = generate(open_generation(),
                      policy=lambda g, task: L.verb_of(g, task) in L.IRREVERSIBLE)

    assert strict["stopped_before"]["verb"] == L.ACT
    assert strict["source"] is None and strict["ran"] is False
    assert strict["phase"] != "done", "it stopped before the plan was carried out, which is the point"
    # ⚠ And the two lines are genuinely different tasks: ugm's fires on the PURSUIT, because a pursuit in
    # its acting phase reports its replay's verb; ours fires on an ACTIVATION sitting on a `DISPATCH`.
    # Same verb, different kind of step — which is exactly the distinction `verb_of` has no word for.
    g = strict["state"]["graph"]
    assert g.kind(strict["stopped_before"]["task"]) == "pursuit"
    assert strict["phase"] == "acting"


# --- 2. planted bug: the stop must be LOAD-BEARING ------------------------------------------------------

def test_PLANTED_BUG_a_verb_of_that_always_says_imagine_and_the_app_runs_anyway(monkeypatch):
    """⭐ The proof that the pause is doing the work. With `verb_of` blind, the driver's policy can never
    fire, the loop walks straight through the `DISPATCH`, and the app executes.

    ⚠ The right signature for a planted bug: the answer stays correct — the app is still built, still
    valid, still the same app — and only the property is lost."""
    monkeypatch.setattr(L, "verb_of", lambda g, task: L.IMAGINE)
    out = generate(open_generation())

    assert out["stopped_before"] is None
    assert out["ran"] is True, "with the verb blinded, nothing declined the irreversible step"
    assert parses(out["source"]), "and the answer is otherwise unharmed, which is the point"


# --- 3. the watcher: monitoring and control are separable -----------------------------------------------

#: ⚠ UNGUIDED. The guided search settles this app in 7 imagined states and no sampling monitor can reach
#: a verdict inside that — see the probe's docstring. The mechanism is fine; the computation is too fast.
WATCHABLE = {"guided": False}


@pytest.fixture(scope="module")
def unwatched():
    """The same generation with a budget nothing can hit — so `imagined` is WHAT THE END ACTUALLY WAS.

    ⚠ Measured here rather than written as a literal, and that is the repair of a real brittleness. Both
    tests below used to name `24`: the control asserted `== 24` and the mid-flight pin asserted `< 24`.
    ugm's 2026-08-02 restructuring made the unguided search settle in **20** states instead — a search
    that got *better*, changing no claim either test makes — and the control went red while the mid-flight
    pin silently weakened, its `< 24` now true of runs that had gone all the way to 20 and stopped
    nothing. A literal cannot tell those apart. Deriving the end means 'stopped early' stays a comparison
    against the end, which is what the sentence was always claiming.

    ⚠ Module-scoped because the pair must be the SAME search, and it is the slow one."""
    return generate(open_generation(budget=400, **WATCHABLE), allow_the_drive=True)


def test_a_watcher_authored_as_TEXT_stops_our_own_generation_MID_FLIGHT(unwatched):
    """⭐⭐ `pystrider/rules/watch.mf` reads the live search's `steps` against a budget and writes `stop`.

    Everything it needs was already data — the state of a running computation, the agenda that lets it
    run *beside* what it watches, and `stop` as an ordinary attribute anything may write. Nothing here is
    instrumentation we added for the occasion.

    ⚠ It is a refusal, and an honest one: no plan, no source, and the app never ran."""
    out = generate(open_generation(budget=8, **WATCHABLE), allow_the_drive=True)

    assert out["stop_why"] == ("generating this app imagined more states than the budget allowed")
    assert out["report"]["done"] is False
    assert out["source"] is None and out["ran"] is False
    assert out["abandoned"], "the render task saw there was nothing to render and said so"
    # ⚠ It stopped it EARLY, not at the end — a verdict delivered after the search finished would be a
    # post-mortem wearing the same words. The `unwatched` control says what "the end" actually was.
    assert out["imagined"] < unwatched["imagined"]


def test_and_the_SAME_generation_with_a_generous_budget_SUCCEEDS(unwatched):
    """⚠ THE VACUITY CONTROL, and without it the pin above measures only that a search can fail. The
    budget is the single difference; the app is built, driven and works.

    ⚠ The count itself is deliberately not pinned to a literal — see `unwatched`. What must hold is that
    this run reached the end under a budget it could not hit, which is what makes it the control."""
    assert unwatched["stop_why"] is None
    assert unwatched["report"]["done"] is True
    assert unwatched["ran"] is True and any(e.startswith("completed") for e in unwatched["events"])


def test_PLANTED_BUG_the_judgement_is_reached_and_IGNORED_so_the_app_is_built_anyway(monkeypatch):
    """⭐⭐ MONITORING AND CONTROL ARE SEPARABLE, and this separates them.

    `stop` is cleared before every search step, so the watcher still reads the search correctly and still
    writes its verdict — `stop_why` survives — and the generation proceeds to build and run the app
    regardless. Judging is not the same capability as being able to act on the judgement, and only the
    second is what ugm added."""
    real_step = driver.step

    def deaf(g, search, **hooks):
        g.put(search, stop=None)
        return real_step(g, search, **hooks)

    monkeypatch.setattr(driver, "step", deaf)
    out = generate(open_generation(budget=8, **WATCHABLE), allow_the_drive=True)

    assert out["stop_why"], "the watcher must still have JUDGED — otherwise this tests nothing"
    assert out["report"]["done"] is True and out["ran"] is True


def test_PLANTED_BUG_a_watcher_that_does_not_SHARE_the_agenda_is_only_a_POST_MORTEM():
    """⭐ Interleaving is the other half, and removing it removes the capability without touching a line
    of the watcher. Here the pursuit is run to completion on an agenda of its own first; the watcher then
    starts, finds the search already `done`, and has nothing left to say.

    ⚠ This is the one whose green is easiest to fake: a watcher that never fired for any *other* reason
    would look identical, which is why the two tests above run the same budget and the same search."""
    state = open_generation(budget=8, **WATCHABLE)
    g = state["graph"]

    solo = L.open_loop(g, "no interleaving")
    L.schedule(g, solo, state["pursuit"])
    L.run(g, solo, max_ticks=4000)
    assert g.attr(g.target(state["pursuit"], "search"), "done"), "the search finished unwatched"

    out = generate(state, allow_the_drive=True)
    assert out["stop_why"] is None, "it could only ever have delivered a verdict about a finished search"
    assert out["ran"] is True and out["report"]["done"] is True


# --- 4. a monitor is a fourth category ------------------------------------------------------------------

def test_a_MONITOR_is_a_fourth_category_and_nothing_can_ever_WANT_one():
    """⚠ The category is drawn by the file, like the other three. But the safety property is not the
    category: `driver.proposals` finds candidates through `function.producers`, which keys on the declared
    return type, and a monitor declares none. **Nothing can want it**, which is stronger than a rule
    saying nobody may ask.

    Vacuity guard: an operation from the same library IS a producer, so this is a fact about monitors and
    not about our reading of `returns_of`."""
    lib = pystrider.load()
    g = lib.graph

    assert lib.monitors == ("watch_generating",)
    assert "watch_generating" not in lib.patterns + lib.bridge_names + lib.operations
    assert function.returns_of(g, "watch_generating") is None
    assert function.returns_of(g, "qualify") is not None
    assert all("watch_generating" not in function.producers(g, t)
               for t in ("build", "qualified_build", "displaying_build", "finishing_build"))


def test_the_two_WORLD_functions_are_the_only_ones_that_can_reach_the_world():
    """⚠ `dispatch` is the one place an effect leaves the graph, so "which of our functions can touch the
    world" is answerable by reading the library rather than by trusting a file name. `world.mf` is a
    separate file so a reader does not have to — and this pin is what keeps the file name honest."""
    lib = pystrider.load()
    g = lib.graph
    dispatching = {name for name in lib.names
                   if any(str(i).startswith("DISPATCH") for i in function.load(g, name)[1])}
    assert dispatching == {"render_the_app", "run_the_app"}


def test_the_emitted_app_at_the_pause_is_the_SAME_app_that_later_ran():
    """⚠ Otherwise "we looked at it before running it" would be about a different artifact. The pause and
    the run are two moments in one pipeline, so the source at the first must be byte-identical to the
    source that the second executes."""
    paused = generate(open_generation())
    whole = generate(open_generation(), allow_the_drive=True)

    assert paused["source"] == whole["source"]
    assert ast.parse(paused["source"]) is not None
