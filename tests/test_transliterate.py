"""Pins for the total reader (`pystrider/transliterate.py`).

The sweep that measures it is `experiments/transliterate_reach.py`; what is here is
the handful of cases that COST something, so they cannot come back quietly. Two of
them were found by the sweep on foreign code after the module looked finished, which
is the argument for both files existing.
"""
from __future__ import annotations

import ast

import pytest

from pystrider.facts import Facts
from pystrider.transliterate import (check_vocabulary, reads_as_literal, render,
                                     transliterate)


def carry(source: str, scope: str) -> str:
    """Round-trip through the graph. Compared against the SOURCE, never a re-render."""
    f = Facts("", scope=scope)
    taken = transliterate(source, f, "<test>")
    return render(f, taken.module)


def unparsed(source: str) -> str:
    """The oracle: what `ast.unparse` makes of the same text."""
    return ast.unparse(ast.parse(source))


# -- the two defects the sweep found ------------------------------------------

@pytest.mark.parametrize("source", [
    "{**a, **b}",           # Dict.keys == [None, None]
    "def f(*, a, b): pass",  # arguments.kw_defaults == [None, None]
])
def test_a_list_holding_the_same_thing_TWICE_keeps_both(source):
    """⚠⚠ Propositions are INTERNED, so `item($s, $c)` twice is ONE proposition.

    Both of these hold a list of two `None`s, and both came back one short — `{**a}`,
    and a function that lost a keyword-only parameter. Silent, and only visible
    against the original source. The position in `item($s, $i, $c)` is what fixes it.
    """
    assert carry(source, "dup:" + source) == unparsed(source)


@pytest.mark.parametrize("source", [
    "x = '[]'",          # a STRING that reads as an empty list
    "x = '14'",          # a STRING that reads as an int
    "x = '\"quoted\"'",  # a STRING that reads as a string, one layer down
    "f'{x:14}'",         # a format spec is a Constant holding "14"
])
def test_a_string_CONSTANT_that_reads_as_a_literal_stays_a_string(source):
    """⚠ The decoder decides by `literal_eval`, so the encoder must guarantee that
    no WORD reads as a literal. Word-encoding every `str` broke exactly these."""
    assert carry(source, "lit:" + source) == unparsed(source)


def test_an_IDENTIFIER_is_still_a_word_a_rule_could_name():
    """⭐ The other half: a name must stay a name, or `facts.py`'s recorded bug
    (`operator` stored as `'gt'`, so `+operator(?g, gt)` never matched) comes back
    for every identifier in the language."""
    f = Facts("", scope="word")
    transliterate("gt = 1", f, "<test>")
    names = [n for n in f.subjects("ast_node") if f.text("syntax", n) == "Name"]
    assert [f.text("id", n) for n in names] == ["gt"]
    assert f.word("gt") == f.one("id", names[0]), "the identifier is the bare word"


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
    """⭐ Every one of these is in `docs/transplant.md`'s backlog — the constructs
    `intake.py` names as gaps, each of which currently costs its whole container.

    ⚠ This does not say the project UNDERSTANDS them. It says they are present, which
    is the only thing a pass needs of the parts it does not match.
    """
    assert carry(source, "total:" + source) == unparsed(source)


def test_a_construct_nobody_wrote_a_handler_for_still_arrives_NAMED():
    """The whole difference from `intake.py`: there is nothing to add per construct."""
    f = Facts("", scope="named")
    taken = transliterate("while x:\n    pass", f, "<test>")
    assert taken.census["While"] == 1
    assert any(f.text("syntax", n) == "While" for n in f.subjects("ast_node"))


def test_an_empty_list_field_still_gets_a_node_to_append_to():
    """⚠ So inserting into an empty body is the same rule as inserting into a full one."""
    f = Facts("", scope="empty")
    taken = transliterate("def f(): pass", f, "<test>")
    fn = next(n for n in f.subjects("ast_node") if f.text("syntax", n) == "FunctionDef")
    decorators = f.one("decorator_list", fn)
    assert decorators is not None and f.has("seq", decorators)
    assert f.of("item", decorators) == []


# -- the membrane that is NOT here ---------------------------------------------

def test_readable_is_NOT_deposited_because_abstention_is_the_CORPUS_S_judgement():
    """⚠ `intake.py` deposits `readable` on everything it modelled and withholds it
    from placeholders, which is how `rules/patterns.ugm` abstains. There are no
    placeholders here, so the judgement has nowhere to hang and belongs in the bridge
    — beside the rules that would refuse, where another author can disagree."""
    f = Facts("", scope="nomembrane")
    transliterate("x = [c for c in ys]", f, "<test>")
    assert f.subjects("readable") == []
    assert f.subjects("partial") == []


# -- the guard -----------------------------------------------------------------

def test_no_relation_this_deposits_is_one_the_ENGINE_reserves():
    """⚠⚠ `Loader.atom` resolves a reserved name to the ENGINE's own node, so a
    collision deposits into engine machinery and says nothing. `Import.names` is the
    live one, renamed; this re-derives the set from this interpreter's `ast` and this
    engine's table, so the next reserved word upstream adds fails by name."""
    check_vocabulary()


def test_the_renamed_field_still_round_trips():
    assert carry("from a import b as c", "renamed") == unparsed("from a import b as c")
    assert carry("global x, y", "renamed2") == unparsed("global x, y")


def test_reads_as_literal_is_the_encoders_promise_to_the_decoder():
    assert reads_as_literal("14") and reads_as_literal("[]") and reads_as_literal("'x'")
    assert not reads_as_literal("gt") and not reads_as_literal("os.path")
