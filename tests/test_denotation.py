"""`pystrider.denotation` — a `Denotation` resolves to the same entity
`intake.py`'s own structure would find by hand, survives round-tripping
through `encode`/`decode`, and a bad hop misses honestly rather than
guessing."""
from __future__ import annotations

import pytest

from loopingrules.world import World
from pystrider import resolve
from pystrider.denotation import Root, Step, decode, encode, locate
from pystrider.intake import Arithmetic


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


SOURCE = "def f(x):\n    return (2 + 3) * 4\n"


def test_root_and_step_locate_the_arithmetic_the_direct_walk_finds(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", SOURCE)
    resolve.reread(w, path)

    root = Root(path, "f")
    body = Step(root, "body")
    first_stmt = Step(body, "stmt", 0)          # the `return` statement
    expr = Step(first_stmt, "returned")          # `(2 + 3) * 4` itself

    # The OUTER arithmetic (`*`) is what `returned` points at directly --
    # found by its own operator, not entity order.
    outer, = (e for e, a in w.each(Arithmetic) if a.operator == "mul")
    assert locate(w, expr) == outer.id


def test_a_bare_step_into_several_matches_refuses_to_guess(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", "def f(x):\n    y = 1\n    return 2 + 3\n")
    resolve.reread(w, path)

    root = Root(path, "f")
    body = Step(root, "body")
    # `stmt` is multi-valued and TWO statements sit in this body -- a bare
    # step (`index=None`) must not silently pick one, same posture
    # `World.get` already enforces everywhere else in this codebase.
    with pytest.raises(ValueError):
        locate(w, Step(body, "stmt"))


def test_an_out_of_range_index_misses_honestly(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", SOURCE)
    resolve.reread(w, path)

    root = Root(path, "f")
    body = Step(root, "body")
    assert locate(w, Step(body, "stmt", 5)) is None


def test_an_unmodelled_label_misses_honestly(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", SOURCE)
    resolve.reread(w, path)

    assert locate(w, Step(Root(path, "f"), "not_a_real_label")) is None


def test_a_dead_root_misses_honestly(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", SOURCE)
    resolve.reread(w, path)

    assert locate(w, Root(path, "not_a_real_function")) is None
    # a step off a dead root has nothing to hop from either
    assert locate(w, Step(Root(path, "not_a_real_function"), "body")) is None


def test_encode_decode_round_trips_a_nested_denotation():
    d = Step(Step(Root("a.py", "f"), "body"), "stmt", 0)
    assert decode(encode(d)) == d


def test_encoded_denotation_is_component_field_storable():
    # `world._lower` only accepts primitives/Entity/list/dict/tuple of
    # those -- a raw `Root`/`Step` is none of those, `encode`'s job is to
    # make it one. Proven by actually attaching it, not just inspecting
    # the shape.
    w = World()
    e = w.spawn()
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Holds:
        payload: tuple

    w.attach(e, Holds(encode(Step(Root("a.py", "f"), "body"))))
    assert decode(w.get(e, Holds).payload) == Step(Root("a.py", "f"), "body")
