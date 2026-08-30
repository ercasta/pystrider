"""`watch <path.py> <name>` -- this domain's first DURABLE, stable-keyed
business fact, and the payoff `docs/TODO.md` thread 2 named as unverified:
a business rule's conclusion surviving a forget-and-reread (or a whole
restart) because it was never holding a raw entity id to begin with. See
`pystrider.domain`'s own docstring on `WatchedFunction`/`FunctionStatus`,
and `pystrider.resolve` for the seam this rests on.

    PYTHONPATH=../loopingrules python -m pytest tests/ -q
"""

from loopingrules import save
from loopingrules.loop import Loop
from loopingrules.world import Reply, Said

from pystrider import domain
from pystrider.domain import FunctionStatus, WatchedFunction


def say(loop, line):
    w = loop.world
    w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
           if w.destroy(entity) or True]


ONE_LOOP = """\
def classify(age):
    total = 0
    for x in items:
        total = total + x
    return total
"""

TWO_LOOPS = """\
def classify(age):
    total = 0
    for x in items:
        total = total + x
    for y in more:
        total = total + y
    return total
"""


def loop_with(tmp_path, name, text):
    loop = Loop()
    domain.install(loop)
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return loop, str(path)


# --- watch, on the live loop ----------------------------------------------

def test_watch_resolves_immediately_even_on_a_never_read_file(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    lines = say(loop, f"watch {path} classify")
    assert lines == ["now watching classify in a.py",
                     "classify in a.py: 1 loop(s)"]


def test_watching_twice_reports_already_watching_not_a_duplicate(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"watch {path} classify")
    lines = say(loop, f"watch {path} classify")
    assert lines == ["already watching classify in a.py"]
    assert len(loop.world.each(WatchedFunction)) == 1


def test_watching_a_missing_function_reports_not_found(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    lines = say(loop, f"watch {path} nope")
    assert lines == ["now watching nope in a.py", "nope in a.py: no longer found"]


def test_reconcile_is_silent_once_status_is_unchanged(tmp_path):
    # `_reconcile_watch` runs every tick `WatchedFunction` is populated --
    # it must not repeat itself just because nothing changed.
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"watch {path} classify")
    lines = say(loop, "blocks does not exist, but hear() should still settle")
    assert not any("loop(s)" in line or "no longer found" in line for line in lines)


def test_editing_and_rereading_updates_the_watched_status(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"watch {path} classify")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TWO_LOOPS)
    lines = say(loop, f"read {path}")
    assert "classify in a.py: 2 loop(s)" in lines
    # `_report_read`'s own summary line still comes first -- reconciling
    # is a side effect of the read, not the point of it (`install()`'s own
    # `priority=-2` on `_reconcile_watch` -- purely a reading-order nicety,
    # not load-bearing, but worth pinning so it does not silently flip).
    assert lines[0].startswith("a.py: 1 functions, 2 loops")
    assert lines[-1] == "classify in a.py: 2 loop(s)"


def test_the_watched_entity_itself_survives_the_reread(tmp_path):
    # The whole point: `WatchedFunction` is the SAME durable entity across
    # a reread that mints brand-new `Function`/`ForStmt`/... ids underneath
    # it -- it was never holding one of those to begin with.
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"watch {path} classify")
    [(entity_before, _wf)] = loop.world.each(WatchedFunction)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TWO_LOOPS)
    say(loop, f"read {path}")
    [(entity_after, _wf)] = loop.world.each(WatchedFunction)
    assert entity_before == entity_after


# --- the actual payoff: durable across `loopingrules.save` -----------------

def test_watched_function_and_status_are_NOT_transient(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"watch {path} classify")
    records = save.dump(loop.world)
    assert any(":WatchedFunction" in r.get("type", "") for r in records)
    assert any(":FunctionStatus" in r.get("type", "") for r in records)


def test_a_watched_function_survives_a_simulated_restart(tmp_path):
    """The end-to-end round trip `docs/TODO.md` thread 2 named as still
    unverified: durably remember a function, "restart" (dump the world,
    load it into a FRESH one -- every `@transient` entity `intake()` ever
    minted is gone, same as a real process restart would leave it, but
    `WatchedFunction`/`FunctionStatus` come back, same ids and all), and
    confirm `_reconcile_watch` -- run on a FRESH `Loop` over the restored
    world -- finds the SAME function again by resolving `(path, name)`
    fresh, not by any id that did not survive."""
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"watch {path} classify")
    [(watched_entity, _wf)] = loop.world.each(WatchedFunction)

    # "restart": round-trip through `loopingrules.save`, into a brand
    # new World -- nothing `intake()` minted answers `w.each` any more.
    records = save.dump(loop.world)
    restarted = Loop()
    problems = save.load(restarted.world, records)
    assert problems == []
    assert restarted.world.each(WatchedFunction) != []
    from pystrider.intake import Function
    assert restarted.world.each(Function) == [], (
        "a real restart would not restore this either -- @transient")

    # Reinstall the domain (as a real restart would) and edit the file
    # under the restored fact's feet, so the OLD entity id -- gone now
    # anyway -- could not possibly have still been right.
    domain.install(restarted)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TWO_LOOPS)
    # No `Said` needed at all -- `_reconcile_watch` is gated on
    # `WatchedFunction` being populated, which it already is, restored.
    restarted.run()

    [(entity_now, status_now)] = [
        (e, restarted.world.get(e, FunctionStatus))
        for e, _wf in restarted.world.each(WatchedFunction)]
    # `Entity.__eq__` also checks `.world is other.world` -- meaningless
    # across two different `World` instances (a restart IS a new one), so
    # the id -- what `save` actually promises to preserve -- is the claim.
    assert entity_now.id == watched_entity.id, "the durable entity itself is unchanged"
    assert status_now == FunctionStatus(path, "classify", exists=True, loops=2)
