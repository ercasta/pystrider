"""`forget <path.py>` / `forget` -- the two granularities `docs/TODO.md`
thread 2 named as unused: a path-scoped sweep (`pystrider.resolve.forget`)
and a blunt, world-wide one (`World.purge_transient()`). See `_forget`'s
own docstring in `pystrider/domain.py` for what each spelling actually
does, and why they are not two names for the same op.

    PYTHONPATH=../loopingrules python -m pytest tests/ -q
"""
from __future__ import annotations

from loopingrules.loop import Loop
from loopingrules.world import Reply, Said

from pystrider import domain
from pystrider.domain import FunctionStatus, WatchedFunction
from pystrider.intake import Function, Origin


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


def loop_with(tmp_path, name, text):
    loop = Loop()
    domain.install(loop)
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return loop, str(path)


# --- forget <path.py>: the scoped form, resolve.forget -------------------

def test_forgetting_a_read_path_destroys_its_entities(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"read {path}")
    assert any(o.value == path for _e, o in loop.world.each(Origin))
    lines = say(loop, f"forget {path}")
    assert lines[0].startswith("forgot a.py: ")
    assert lines[0].endswith("entities destroyed")
    assert not lines[0].endswith(" 0 entities destroyed")
    assert not any(o.value == path for _e, o in loop.world.each(Origin))


def test_forgetting_a_never_read_path_is_a_reported_no_op(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    lines = say(loop, f"forget {path}")
    assert lines == ["forgot a.py: 0 entities destroyed"]


def test_forgetting_one_path_leaves_another_untouched(tmp_path):
    loop, path_a = loop_with(tmp_path, "a.py", ONE_LOOP)
    path_b = str(tmp_path / "b.py")
    with open(path_b, "w", encoding="utf-8") as fh:
        fh.write(ONE_LOOP)
    say(loop, f"read {path_a}")
    say(loop, f"read {path_b}")
    say(loop, f"forget {path_a}")
    assert not any(o.value == path_a for _e, o in loop.world.each(Origin))
    assert any(o.value == path_b for _e, o in loop.world.each(Origin))


# --- forget (bare): the blunt form, World.purge_transient -----------------

def test_bare_forget_detaches_transient_components_world_wide(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"read {path}")
    assert loop.world.each(Function)               # something to purge
    lines = say(loop, "forget")
    assert lines[0].startswith("forgot everything transient: ")
    assert lines[0].endswith("components detached world-wide")
    assert loop.world.each(Function) == []
    assert loop.world.each(Origin) == []


def test_bare_forget_does_not_touch_a_watched_functions_durable_facts(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"watch {path} classify")
    say(loop, "forget")
    # `WatchedFunction`/`FunctionStatus` are not `@transient` -- a person's
    # standing interest survives the blunt form exactly as it survives a
    # restart (see `WatchedFunction`'s own docstring).
    assert len(loop.world.each(WatchedFunction)) == 1
    assert len(loop.world.each(FunctionStatus)) == 1


def test_a_watched_function_recovers_after_a_bare_forget(tmp_path):
    # `Origin` itself is transient, so a bare `forget` makes
    # `resolve_function` see NOTHING known about `path` -- same as a
    # never-`read` file -- and it rereads exactly once. `_reconcile_watch`'s
    # own "not answerable yet" skip covers the one tick `LoopCount` needs to
    # catch up; `say`'s `loop.run()` ticks to settle either way, so this
    # comes back correct within one `say` call, not a second one.
    loop, path = loop_with(tmp_path, "a.py", ONE_LOOP)
    say(loop, f"watch {path} classify")
    say(loop, "forget")
    [(_e, status)] = loop.world.each(FunctionStatus)
    assert status == FunctionStatus(path, "classify", exists=True, loops=1)
