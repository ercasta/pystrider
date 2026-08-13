"""The compliance pass: every operation a planner may imagine reaches the graph through the vocabulary.

⚠ **This pin exists because the property was broken and nobody noticed until the suite was run.**
`../ugm`'s de-Pythonization arc moved the workbench out of Python, and sharing versions between frames
is only correct if *every* read is interposable — so `rules/step.mf` now `REFUSE`s an unmediated
operator outright. Every one of our operations touched the graph bare, so **45 of 216 pins went red at
once**, all with the same message, none of them from a change on this side. Rewriting them to the eight
names (`slot_of` / `set_slot` / `related` / `relations` / `relation_at` / `relate` / `unrelate` /
`make`) was mechanical and cost nothing measurable.

**The refusal is the mechanism working.** With the operations bare, imagining `qualify` would have
written `qualifies` onto the REAL build — planning reaching the world, which is the one thing the
workbench exists to prevent. Before enforcement that was silent; ugm's own note records a step
*imagining* `tamper` writing `tampered` onto the real car.

⚠ **`offenders` only sees functions that declare parameter types**, which is `access.operators`' stated
hole, not an oversight of ours. Our patterns, bridges, dispatchers and monitor still touch the graph
bare and are green only because nothing imagines them: they are invoked directly from Python, on the
real graph. `test_the_bet_survives_mediation` is what says that is a position rather than luck — the
descriptions read identically either way, so mediating the rest is available whenever an operation
needs to lift or recognize *while imagining*, and is not owed before then.
"""
from pystrider import load, patterns
from pystrider.mf import access

#: Everything that touches the graph bare today, and is not caught because it declares no parameter
#: types. ⚠ A NAME LEAVING THIS SET IS FINE; a name ARRIVING is a new operation authored bare, and it
#: will refuse the first time a planner imagines it.
BARE_BY_DESIGN = frozenset({
    "as_iteration", "as_application", "as_conditional",                  # patterns.mf — invoked by us
    "as_iteration_from_for_stmt", "as_application_from_call",            # python.mf — lifts
    "as_conditional_from_if_stmt",
    "as_for_stmt", "as_if_stmt", "as_call",                              # python.mf — lowerings
    "render_the_app", "run_the_app",                                     # world.mf — these DISPATCH
    "watch_generating",                                                  # watch.mf — the monitor
})


def test_no_planning_operation_reaches_the_graph_bare():
    """ugm's compliance pass, run over our corpus. Empty is the property."""
    assert access.offenders(load().graph) == {}


def test_the_operations_that_are_still_bare_are_the_ones_we_named():
    """The honest floor beside the pass above — `offenders` cannot see these, so this pin does.

    ⚠ The control is that this set is not everything: if it were, the pin above would be vacuous."""
    lib = load()
    bare = {n for n in lib.names if access.bare_touches(lib.graph, n)}
    assert bare == BARE_BY_DESIGN
    assert set(lib.operations) - BARE_BY_DESIGN, "every planner operation must be mediated"


def test_the_bet_survives_mediation():
    """⭐ The load-bearing question, answered by measurement rather than by reasoning.

    The whole bet is that ONE authored description serves both halves — called it constructs, read back
    off its stored body by `establishes` it recognizes. Mediation lowers every read and write to a
    *call*, and `driver._effects` is normally blind to a call: the effect happens somewhere else. If
    that blinded `establishes`, mediating a pattern would silently turn it into a description that
    describes nothing, and `recognizes` would skip it — a plausible negative, not an error.

    It does not, and the reason is `access.as_opcode`: the vocabulary is a CLOSED set, so a static
    reader may know it exactly as it knows the opcodes. Checked here by mediating the real patterns at
    run time and comparing the descriptions read off both versions — same subject, same effects."""
    plain = load()
    mediated = load(source="\n".join([
        "fn as_iteration(it, seq, var, body) -> iteration:",
        '    INVOKE R(_) relate node=F(it) label="repeats_over" other=F(seq)',
        '    INVOKE R(_) relate node=F(it) label="element" other=F(var)',
        '    INVOKE R(_) relate node=F(it) label="each_does" other=F(body)',
    ]))
    assert patterns.pattern_of(mediated, "as_iteration") == patterns.pattern_of(plain, "as_iteration")
