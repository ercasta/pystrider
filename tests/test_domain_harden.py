"""`harden <path.py>`, on the SHARED loop -- the request -> analysis ->
gated repair -> report wiring for `pystrider.exceptions`. Mirrors
`tests/test_domain_read.py`'s own shape (`_read`/`_report_read`'s two-rule
pattern); see `pystrider.domain`'s own docstring, "`harden`/
`_report_harden`."

    PYTHONPATH=../loopingrules python -m pytest tests/ -q
"""

from loopingrules.loop import Loop
from loopingrules.world import Reply, Said

from pystrider import domain
from pystrider.exceptions import MayRaise, Repaired, WantsHardening


def say(loop, line):
    w = loop.world
    w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
           if w.destroy(entity) or True]


ONE_DIV = "def divide(x, y):\n    return x / y\n"

NO_RISK = "def classify(age):\n    return age\n"

ALREADY_GUARDED = (
    "def divide(x, y):\n"
    "    try:\n"
    "        return x / y\n"
    "    except ZeroDivisionError:\n"
    "        raise\n"
)


def loop_with(tmp_path, name, text):
    loop = Loop()
    domain.install(loop)
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return loop, str(path)


def test_harden_wraps_a_risky_division_and_reports_it(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_DIV)
    lines = say(loop, f"harden {path}")
    assert lines[0] == "a.py: 1 risky spot(s), 0 already guarded, 1 newly wrapped"
    assert "try:" in lines[1]
    assert "except ZeroDivisionError:" in lines[1]


def test_harden_reports_nothing_risky_when_there_is_none(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", NO_RISK)
    assert say(loop, f"harden {path}") == ["a.py: nothing looked risky"]


def test_harden_on_an_already_guarded_division_wraps_nothing_more(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ALREADY_GUARDED)
    lines = say(loop, f"harden {path}")
    assert lines == ["a.py: 1 risky spot(s), 1 already guarded, 0 newly wrapped"]


def test_hardening_twice_is_not_two_standing_requests(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_DIV)
    first = say(loop, f"harden {path}")
    second = say(loop, f"harden {path}")
    # Nothing is ever written back to disk (deliberately, see `_report_harden`'s
    # own docstring), so re-reading the SAME unchanged file re-derives the
    # same outcome both times -- what this pins is that the STANDING request
    # itself is not duplicated.
    assert second == first
    assert len(loop.world.each(WantsHardening)) == 1


def test_read_alone_never_wraps_anything_recognition_still_happens(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", ONE_DIV)
    say(loop, f"read {path}")
    w = loop.world
    risky = w.each(MayRaise)
    assert risky != []                                       # recognition happened
    assert all(not w.has(e, Repaired) for e, _tag in risky)   # never rewritten
    assert w.each(WantsHardening) == []                       # no request was ever made


def test_help_python_mentions_harden():
    from loopingrules import help as help_
    loop = Loop()
    help_.install(loop)
    domain.install(loop)
    assert "harden <path.py>" in say(loop, "help python")[0]
