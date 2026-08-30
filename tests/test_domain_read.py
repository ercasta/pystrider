"""`read <path.py>`, on the SHARED loop -- `pystrider.domain`'s own
docstring, "the SHARED world," is the argument this file pins down: a
report that needs `patterns` to have run (`_report_read`), correctly
scoped to the file just read even though the world may hold others', and
none of it -- not one component -- reaching `loopingrules.save.dump()`.

    PYTHONPATH=../loopingrules python -m pytest tests/ -q
"""

from loopingrules import save
from loopingrules.loop import Loop
from loopingrules.world import Reply, Said

from pystrider import domain
from pystrider.intake import Function


def say(loop, line):
    w = loop.world
    w.spawn(Said("user", line))
    loop.run()
    return [reply.text for entity, reply in w.each(Reply)
           if w.destroy(entity) or True]


LOOPY = """\
def classify(age):
    total = 0
    for x in items:
        total = total + x
    for y in more:
        total = total + y
    return total
"""

PARTIAL = """\
def f():
    return [x for x in range(3)]
"""


def loop_with(tmp_path, name, text):
    loop = Loop()
    domain.install(loop)
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return loop, str(path)


# --- the report itself ---------------------------------------------------

def test_read_reports_functions_loops_and_iterations_recognized(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", LOOPY)
    lines = say(loop, f"read {path}")
    assert lines[0] == "a.py: 1 functions, 2 loops, 2 recognized as iterations"


def test_iteration_recognition_needs_PATTERNS_not_just_intake(tmp_path):
    # The whole reason `_read`/`_report_read` are two rules: if `patterns`
    # never got installed on this loop, intake still succeeds but nothing
    # is ever recognized as an `Iteration` -- pinning that patterns really
    # is what supplies the "2 recognized" above, not intake alone.
    loop = Loop()
    for rule in domain.RULES:
        loop.rule(rule)
    loop.rule(domain._report_read, priority=-1)
    loop.world.learn(*domain.WORDS)            # `install()` minus `patterns`
    path = tmp_path / "a.py"
    path.write_text(LOOPY, encoding="utf-8")
    lines = say(loop, f"read {path}")
    assert lines[0] == "a.py: 1 functions, 2 loops, 0 recognized as iterations"


def test_read_reports_unmodelled_constructs(tmp_path):
    loop, path = loop_with(tmp_path, "p.py", PARTIAL)
    lines = say(loop, f"read {path}")
    assert lines[1] == "  unmodelled (1): ListComp"


def test_read_reports_nothing_unread_when_complete(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", LOOPY)
    lines = say(loop, f"read {path}")
    assert lines[1] == "  nothing unread"


def test_read_reports_the_round_trip_line_last(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", LOOPY)
    lines = say(loop, f"read {path}")
    assert lines[-1].startswith("  round-trips byte-exact against the source:")


def test_read_of_a_missing_file_says_so_and_touches_nothing(tmp_path):
    loop = Loop()
    domain.install(loop)
    before = len(loop.world)
    lines = say(loop, f"read {tmp_path / 'nope.py'}")
    assert len(lines) == 1 and lines[0].startswith("cannot read")
    assert len(loop.world) == before


# --- shared-world correctness: scoping and idempotence --------------------

def test_reading_the_same_file_twice_does_not_double_count(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", LOOPY)
    say(loop, f"read {path}")
    before = len(loop.world)
    lines = say(loop, f"read {path}")
    assert lines[0] == "a.py: 1 functions, 2 loops, 2 recognized as iterations"
    assert len(loop.world) == before, "a reread must not accumulate entities"
    assert len(loop.world.each(Function)) == 1


def test_reading_two_files_does_not_merge_their_counts(tmp_path):
    loop = Loop()
    domain.install(loop)
    (tmp_path / "a.py").write_text(LOOPY, encoding="utf-8")
    (tmp_path / "b.py").write_text("def other():\n    for z in range(1):\n        pass\n",
                                   encoding="utf-8")
    say(loop, f"read {tmp_path / 'a.py'}")
    lines_b = say(loop, f"read {tmp_path / 'b.py'}")
    assert lines_b[0] == "b.py: 1 functions, 1 loops, 1 recognized as iterations"
    assert len(loop.world.each(Function)) == 2


# --- settling leaves nothing but the CONVERSATION behind -------------------

def test_read_settling_leaves_no_bookkeeping_behind(tmp_path):
    loop, path = loop_with(tmp_path, "a.py", LOOPY)
    say(loop, f"read {path}")
    w = loop.world
    assert w.each(domain.ReadWanted) == []
    assert w.each(domain.ReadDone) == []


def test_none_of_a_read_reaches_the_persisted_world(tmp_path):
    # The whole point of this session's `@transient` work: intaking a real
    # file spawns dozens of entities, and `loopingrules.save.dump()` must
    # not write a single one of them down.
    loop, path = loop_with(tmp_path, "a.py", LOOPY)
    say(loop, f"read {path}")
    records = save.dump(loop.world)
    assert not any(":Function" in r.get("type", "") for r in records)
    assert not any(":ForStmt" in r.get("type", "") for r in records)
    assert not any(":Iteration" in r.get("type", "") for r in records)
