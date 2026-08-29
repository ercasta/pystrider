"""`help python`, answered by this domain alongside `loopingrules.help`'s
own occasion -- the substrate this package already depends on
unconditionally, not `harneskills`. See `pystrider/domain.py`'s own
docstring for the (corrected) argument.

    PYTHONPATH=../loopingrules python -m pytest tests/ -q
"""

from loopingrules import help as help_
from loopingrules.loop import Loop
from loopingrules.world import Reply, Said

from pystrider import domain


def say(loop, line):
    w = loop.world
    w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
            if w.destroy(entity) or True]


def test_help_python_is_answered_by_this_domain():
    loop = Loop()
    help_.install(loop)
    domain.install(loop)
    assert say(loop, "help python")[0].startswith("blocks, brew")


def test_help_python_does_not_answer_help_files():
    # This domain has no opinion about "files" -- the default responder
    # (a topic nobody recognizes at all) or `fs`'s own answer, neither
    # of which this domain proposes, is what should win instead.
    loop = Loop()
    help_.install(loop)
    domain.install(loop)
    assert say(loop, "help files") == ["no help for 'files'"]


def test_bare_help_is_unaffected_by_this_domain_being_installed():
    loop = Loop()
    help_.install(loop)
    domain.install(loop)
    assert say(loop, "help") == ["try: help files, help python"]
