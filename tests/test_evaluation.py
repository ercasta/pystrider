"""`pystrider.evaluation` — a receipt is minted without vouching for
itself, `current` is the only thing that ever checks one against a fresh
re-derivation, and staleness (a mutated `Constant`, a forgotten path) is
answered honestly rather than trusted away."""
from __future__ import annotations

from loopingrules.world import World
from pystrider import resolve, symbolic
from pystrider.denotation import Root, Step
from pystrider.evaluation import Evaluation, current, record
from pystrider.intake import Constant, encode_literal


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


SOURCE = "def f(x):\n    return 2 + 3\n"


def denoted_arithmetic(path):
    root = Root(path, "f")
    body = Step(root, "body")
    first_stmt = Step(body, "stmt", 0)
    return Step(first_stmt, "returned")


def test_record_and_current_round_trip(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", SOURCE)
    resolve.reread(w, path)
    d = denoted_arithmetic(path)

    entity = record(w, d, "known_value", 5)
    ev = w.get(entity, Evaluation)
    assert current(w, ev, symbolic.fold) is True


def test_current_is_false_once_the_subject_is_mutated(tmp_path):
    w = World()
    path = write(tmp_path, "a.py", SOURCE)
    resolve.reread(w, path)
    d = denoted_arithmetic(path)

    entity = record(w, d, "known_value", 5)
    ev = w.get(entity, Evaluation)
    assert current(w, ev, symbolic.fold) is True

    # repair.py's own style of in-place mutation -- same entity id, new
    # payload. The receipt was TRUE when minted; it is a stale record now,
    # not something `current` should still vouch for.
    (const, _c), = ((e, c) for e, c in w.each(Constant) if c.literal == "2")
    w.replace(const, Constant(encode_literal(9)))
    assert current(w, ev, symbolic.fold) is False


def test_current_is_false_once_the_file_on_disk_changed(tmp_path):
    # `forget` alone changes nothing observable -- `resolve_function`
    # transparently rereads an unchanged file back to the same answer.
    # Staleness only bites once the SOURCE itself moved under it.
    w = World()
    path = write(tmp_path, "a.py", SOURCE)
    resolve.reread(w, path)
    d = denoted_arithmetic(path)

    entity = record(w, d, "known_value", 5)
    ev = w.get(entity, Evaluation)

    resolve.forget(w, path)
    write(tmp_path, "a.py", "def f(x):\n    return 9 + 3\n")
    assert current(w, ev, symbolic.fold) is False


def test_current_is_false_when_the_deriver_now_abstains(tmp_path):
    w = World()
    path = write(tmp_path, "b.py", "def f(x):\n    return x + 1\n")
    resolve.reread(w, path)
    root = Root(path, "f")
    d = Step(Step(Step(root, "body"), "stmt", 0), "returned")

    # Record a receipt claiming a value `fold` could never actually derive
    # for this expression (it involves a bare `Name`) -- a deliberately
    # WRONG receipt, to prove `current` checks the deriver, not the stamp.
    entity = record(w, d, "known_value", 3)
    ev = w.get(entity, Evaluation)
    assert current(w, ev, symbolic.fold) is False


def test_a_receipt_carries_when_it_was_made():
    w = World()
    entity = record(w, Root("a.py", "f"), "known_value", 1)
    ev = w.get(entity, Evaluation)
    assert ev.at > 0
    assert ev.kind == "known_value"
