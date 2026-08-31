"""What `pystrider.resolve` promises: a stable key answers to a live
entity, `forget`/`reread` are the whole of what "stale" means for
code-derived facts today, and neither leaks nor rereads more than it has
to.

    PYTHONPATH=../loopingrules python -m pytest tests/ -q
"""

import pytest

from loopingrules.world import World

from pystrider import resolve
from pystrider.intake import Block, Function, Origin, Qualname, Unreadable


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


LOOPY = """\
def classify(age):
    total = 0
    for x in items:
        total = total + x
    return total
"""

PARTIAL = """\
def f():
    return [x for x in range(3)]
"""


# --- forget -------------------------------------------------------------

def test_forget_on_an_unread_path_is_a_no_op(tmp_path):
    w = World()
    assert resolve.forget(w, str(tmp_path / "never.py")) == 0
    assert len(w) == 0


def test_forget_destroys_everything_from_one_path_only(tmp_path):
    w = World()
    a = write(tmp_path, "a.py", LOOPY)
    b = write(tmp_path, "b.py", LOOPY)
    resolve.reread(w, a)
    taken_b, _ = resolve.reread(w, b)
    dropped = resolve.forget(w, a)
    assert dropped > 0
    assert all(o.value != a for _e, o in w.each(Origin))
    # `b`'s own entities are untouched -- forget is scoped by path.
    assert w.get(taken_b.module, Origin).value == b


# --- reread: the premise this whole module exists for -------------------

def test_reread_mints_FRESH_ids_not_the_same_ones(tmp_path):
    # The whole argument for `@transient`/stable keys: an id from one
    # intake means nothing after a reread, because a reread does not
    # reuse the ids it just destroyed.
    w = World()
    path = write(tmp_path, "a.py", LOOPY)
    first, _ = resolve.reread(w, path)
    second, _ = resolve.reread(w, path)
    assert first.module != second.module
    assert second.module.alive
    assert not first.module.alive


def test_reread_returns_the_source_alongside(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", LOOPY)
    _taken, source = resolve.reread(w, path)
    assert source == LOOPY


def test_reread_of_a_missing_file_raises_OSError(tmp_path):
    w = World()
    with pytest.raises(OSError):
        resolve.reread(w, str(tmp_path / "nope.py"))


# --- resolve_function -----------------------------------------------------

def test_resolve_function_finds_an_already_known_function(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", LOOPY)
    resolve.reread(w, path)
    entity = resolve.resolve_function(w, path, "classify")
    assert entity is not None
    assert w.get(entity, Function).name == "classify"


def test_resolve_function_rereads_exactly_once_for_a_never_seen_path(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", LOOPY)
    assert w.each(Origin) == []            # nothing known about it yet
    entity = resolve.resolve_function(w, path, "classify")
    assert entity is not None
    assert any(o.value == path for _e, o in w.each(Origin))


def test_resolve_function_does_NOT_reread_on_a_known_files_missing_name(tmp_path):
    # A name a KNOWN file does not have is a real, stable answer -- not
    # staleness. Rereading here would turn a rule calling this every tick
    # into a disk-read storm that never settles (see the module's own ⚠).
    w = World()
    path = write(tmp_path, "a.py", LOOPY)
    resolve.reread(w, path)
    module_before = list(w.entities())
    assert resolve.resolve_function(w, path, "no_such_function") is None
    assert list(w.entities()) == module_before, "must not have rebuilt anything"


def test_resolve_function_on_a_file_that_cannot_be_read_raises(tmp_path):
    w = World()
    with pytest.raises(OSError):
        resolve.resolve_function(w, str(tmp_path / "nope.py"), "anything")


# --- resolve_function: dotted qualname disambiguation ----------------------

NESTED_SAME_NAME = """\
def a():
    def inner():
        return 1
    return inner()

def b():
    def inner():
        return 2
    return inner()
"""


def test_bare_name_of_a_scope_collision_is_still_ambiguous(tmp_path):
    # Undisambiguated on purpose -- neither caller named a scope, so this
    # is the same "whichever sorts first" answer as before `Qualname`
    # existed. Named here so a future change to that ordering is a
    # visible break, not a silent one.
    w = World()
    path = write(tmp_path, "a.py", NESTED_SAME_NAME)
    resolve.reread(w, path)
    entity = resolve.resolve_function(w, path, "inner")
    assert entity is not None
    assert w.get(entity, Qualname).value == "a.inner"     # first by entity id


def test_a_dotted_qualname_disambiguates_a_scope_collision(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", NESTED_SAME_NAME)
    resolve.reread(w, path)
    a_inner = resolve.resolve_function(w, path, "a.inner")
    b_inner = resolve.resolve_function(w, path, "b.inner")
    assert a_inner is not None and b_inner is not None
    assert a_inner != b_inner
    assert w.get(a_inner, Qualname).value == "a.inner"
    assert w.get(b_inner, Qualname).value == "b.inner"


def test_a_top_level_functions_dotted_qualname_is_just_its_name(tmp_path):
    # A top-level function's qualname has no dots -- resolving by its bare
    # name must keep working exactly as before `Qualname` existed.
    w = World()
    path = write(tmp_path, "a.py", LOOPY)
    resolve.reread(w, path)
    entity = resolve.resolve_function(w, path, "classify")
    assert entity is not None
    assert w.get(entity, Function).name == "classify"


# --- the leak `resolve.forget` needs closed: EVERY entity carries Origin -

def test_every_intaken_entity_carries_origin_even_a_synthetic_block(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", LOOPY)
    resolve.reread(w, path)
    blocks = [e for e, _b in w.each(Block)]
    assert blocks, "the fixture has a function body -- at least one Block"
    assert all(w.get(b, Origin) == Origin(path) for b in blocks)


def test_a_placeholder_for_an_unmodelled_construct_carries_origin_too(tmp_path):
    w = World()
    path = write(tmp_path, "p.py", PARTIAL)
    resolve.reread(w, path)
    placeholders = [e for e, _u in w.each(Unreadable)]
    assert placeholders, "the fixture has a ListComp -- intake refuses it"
    assert all(w.get(p, Origin) == Origin(path) for p in placeholders)
