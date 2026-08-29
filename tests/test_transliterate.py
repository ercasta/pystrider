"""Pins for the total reader (`pystrider/transliterate.py`).

What is here is the handful of cases that COST something, so they cannot come back
quietly. Two of them were found by a sweep on foreign code after the module looked
finished.

⚠⚠ 2026-08-29: rewritten off `Facts` onto `loopingrules.world.World` and the
typed/dynamic components `transliterate.py` now declares — see its own note.
"""
from __future__ import annotations

import ast

import pytest

from loopingrules.world import World
from pystrider.transliterate import (AstNode, Item, SeqNode, Syntax,
                                     check_vocabulary, field_component,
                                     reads_as_literal, render, transliterate)


def carry(source: str) -> str:
    """Round-trip through the world. Compared against the SOURCE, never a re-render."""
    w = World()
    taken = transliterate(source, w, "<test>")
    return render(w, taken.module)


def unparsed(source: str) -> str:
    """The oracle: what `ast.unparse` makes of the same text."""
    return ast.unparse(ast.parse(source))


def _nodes_of_kind(w, kind: str):
    return [e for e, _tag in w.each(AstNode) if w.get(e, Syntax).kind == kind]


# -- the two defects a sweep found --------------------------------------------

@pytest.mark.parametrize("source", [
    "{**a, **b}",            # Dict.keys == [None, None]
    "def f(*, a, b): pass",  # arguments.kw_defaults == [None, None]
])
def test_a_list_holding_the_same_thing_TWICE_keeps_both(source):
    """⚠⚠ Both of these hold a list of two `None`s, and both came back one short —
    `{**a}`, and a function that lost a keyword-only parameter. Silent, and only
    visible against the original source.

    The cause was an earlier engine's interning: two attaches of the SAME value
    were one proposition. ⭐ `World.attach` dedupes here for the same reason (it
    is what makes a rule idempotent, and therefore what lets the loop settle), so
    the position on `Item` is still exactly what fixes it. The hazard moved
    substrate without changing shape.
    """
    assert carry(source) == unparsed(source)


@pytest.mark.parametrize("source", [
    "x = '[]'",          # a STRING that reads as an empty list
    "x = '14'",          # a STRING that reads as an int
    "x = '\"quoted\"'",  # a STRING that reads as a string, one layer down
    "f'{x:14}'",         # a format spec is a Constant holding "14"
])
def test_a_string_CONSTANT_that_reads_as_a_literal_stays_a_string(source):
    """⚠ The decoder decides by `literal_eval`, so the encoder must guarantee that
    no WORD reads as a literal. Word-encoding every `str` broke exactly these."""
    assert carry(source) == unparsed(source)


def test_an_IDENTIFIER_is_still_a_word_a_rule_could_name():
    """⭐ The other half: a name must stay a name, or `intake.py`'s recorded bug
    (`operator` stored as `'gt'`, so a rule naming the bare `gt` never matched)
    comes back for every identifier in the language."""
    w = World()
    transliterate("gt = 1", w, "<test>")
    names = _nodes_of_kind(w, "Name")
    assert [w.get(n, field_component("id")).value for n in names] == ["gt"]
    # ⭐ The identifier is the bare word — not `repr`-encoded, unlike a literal.
    assert not reads_as_literal(w.get(names[0], field_component("id")).value)


# -- totality ------------------------------------------------------------------

@pytest.mark.parametrize("source", [
    "xs = [c for c in ys if c > 2]",
    "d = {k: v for k, v in items}",
    "async def f():\n    async with a as b:\n        await c",
    "def f(a: int, /, b: str = 'x', *args, c: bool = False, **kw) -> 'R': pass",
    "class A(B, metaclass=M):\n    x: int = 1",
    "try:\n    pass\nexcept OSError as e:\n    raise RuntimeError(f'bad {e!r:>10}') from e\nfinally:\n    pass",
    "match x:\n    case [1, *rest]:\n        pass\n    case {'k': v}:\n        pass\n    case _:\n        pass",
    "assert (y := f(x)) > 0, 'msg'",
    "del a[1:2, ::3]",
    "@deco(1)\ndef f(): yield from g()",
    "lambda *a, **k: (yield)",
    "global g\n",
])
def test_the_reader_carries_what_intake_REFUSES(source):
    """⭐ Every one of these is a construct `intake.py` names as a gap, each of
    which currently costs its whole container.

    ⚠ This does not say the project UNDERSTANDS them. It says they are PRESENT,
    which is the only thing a pass needs of the parts it does not match.
    """
    assert carry(source) == unparsed(source)


def test_a_construct_nobody_wrote_a_handler_for_still_arrives_NAMED():
    """The whole difference from `intake.py`: there is nothing to add per construct."""
    w = World()
    taken = transliterate("while x:\n    pass", w, "<test>")
    assert taken.census["While"] == 1
    assert _nodes_of_kind(w, "While")


def test_an_empty_list_field_still_gets_a_node_to_append_to():
    """⚠ So inserting into an empty body is the same rule as into a full one."""
    w = World()
    transliterate("def f(): pass", w, "<test>")
    (fn,) = _nodes_of_kind(w, "FunctionDef")
    decorators = w.get(fn, field_component("decorator_list"))
    assert decorators is not None and w.has(decorators.value, SeqNode)
    assert w.get_all(decorators.value, Item) == []


# -- the membrane that is NOT here ---------------------------------------------

def test_readable_is_NOT_deposited_because_abstention_is_the_DESCRIPTION_S_judgement():
    """⚠ `intake.py` deposits `Readable` on everything it modelled and withholds
    it from placeholders, which is how `patterns.py` abstains. There are no
    placeholders here, so the judgement has nowhere to hang and belongs beside
    the descriptions that would refuse."""
    from pystrider.intake import Partial, Readable
    w = World()
    transliterate("x = [c for c in ys]", w, "<test>")
    assert w.all(Readable) == []
    assert w.all(Partial) == []


# -- the guard -----------------------------------------------------------------

def test_no_relation_this_deposits_COLLIDES_with_its_own_vocabulary():
    """⚠⚠ RETARGETED, TWICE OVER. It used to guard an earlier engine's reserved
    table; then `harneskills` retargeted it to guard this module's own fixed
    vocabulary as a real hazard. `loopingrules` retires even that: every AST
    field is its OWN dynamically-built class now, never the same Python object
    as `AstNode`/`Syntax`/`SeqNode`/`Item` even when the strings coincide, so
    nothing can actually collide any more — see the module note. This call is
    now a human-readability diagnostic, kept rather than deleted."""
    check_vocabulary()


def test_the_field_that_NEEDED_renaming_now_round_trips_under_its_own_name():
    """`Import.names`, `Global.names`, `Nonlocal.names` — the collision that was."""
    assert carry("from a import b as c") == unparsed("from a import b as c")
    assert carry("global x, y") == unparsed("global x, y")
    w = World()
    taken = transliterate("global x, y", w, "<test>")
    body = w.get(taken.module, field_component("body"))
    (item,) = w.get_all(body.value, Item)
    assert w.get(item.value, field_component("names")) is not None, \
        "deposited under `names`, unrenamed"


def test_reads_as_literal_is_the_encoders_promise_to_the_decoder():
    assert reads_as_literal("14") and reads_as_literal("[]") and reads_as_literal("'x'")
    assert not reads_as_literal("gt") and not reads_as_literal("os.path")
