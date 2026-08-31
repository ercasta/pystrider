"""`pystrider.symbolic` — constant folding, in isolation. No `Case`, no
`Given`, no request: `KnownValue` is either derivable from structure alone or
it is silently absent."""
from __future__ import annotations

from loopingrules.loop import Loop
from pystrider import symbolic
from pystrider.intake import Arithmetic, Comparison, Constant, intake
from pystrider.symbolic import KnownValue


def load(source: str, origin: str = "<test>"):
    loop = Loop()
    symbolic.install(loop)
    intake(source, loop.world, origin)
    loop.run()
    return loop.world


def test_a_bare_constant_knows_its_own_value():
    w = load("def f():\n    return 1\n")
    (entity, _c), = w.each(Constant)
    assert w.get(entity, KnownValue) == KnownValue("1")


def test_arithmetic_of_two_constants_folds():
    w = load("def f():\n    return 2 + 3\n")
    (entity, _a), = w.each(Arithmetic)
    assert w.get(entity, KnownValue) == KnownValue("5")


def test_nested_arithmetic_folds():
    w = load("def f():\n    return (2 + 3) * 4\n")
    # The outer `*` needs the inner `+` folded FIRST — `fold` recurses
    # internally (Python recursion, not an engine tick per nesting level),
    # so this settles in one pass. Found by its own operator, not entity
    # order, since `Entity` carries no ordering.
    outer, = (e for e, a in w.each(Arithmetic) if a.operator == "mul")
    assert w.get(outer, KnownValue) == KnownValue("20")


def test_division_folds_to_a_float():
    w = load("def f():\n    return 10 / 2\n")
    (entity, _a), = w.each(Arithmetic)
    assert w.get(entity, KnownValue) == KnownValue("5.0")


def test_division_by_a_literal_zero_abstains_rather_than_crashing():
    w = load("def f():\n    return 1 / 0\n")
    (entity, _a), = w.each(Arithmetic)
    assert w.get(entity, KnownValue) is None


def test_an_arithmetic_over_an_unbound_name_abstains():
    w = load("def f(x):\n    return x + 1\n")
    (entity, _a), = w.each(Arithmetic)
    assert w.get(entity, KnownValue) is None


def test_a_comparison_of_two_constants_folds_to_a_bool():
    w = load("def f():\n    return 1 < 2\n")
    (entity, _c), = w.each(Comparison)
    assert w.get(entity, KnownValue) == KnownValue("True")


def test_identity_and_containment_operators_are_never_folded():
    # `_COMPARE`'s own membrane -- `is`/`in` are refused by name, not guessed.
    w = load("def f():\n    return 1 is 1\n")
    (entity, _c), = w.each(Comparison)
    assert w.get(entity, KnownValue) is None


def test_a_name_never_gets_a_known_value_here():
    # The ceiling this slice sits at, pinned directly: even a parameter with
    # an obviously-knowable-looking use gets nothing -- binding is next, not
    # this.
    from pystrider.intake import Name
    w = load("def f(x):\n    return x\n")
    (entity, _n), = w.each(Name)
    assert w.get(entity, KnownValue) is None


def test_recognizing_an_already_known_constant_is_not_a_change():
    w = load("def f():\n    return 1\n")
    before = w.revision
    symbolic.known_value(w)
    assert w.revision == before


def test_a_replaced_constant_is_reconsidered_not_left_stale():
    # The bug the module note names: `repair.py`'s `apply` mutates a
    # `Constant`/`Comparison` IN PLACE (`w.replace`, same entity id). A
    # `KnownValue` cached before that must not go on saying the old value.
    w = load("def f():\n    return 18\n")
    (entity, _c), = w.each(Constant)
    assert w.get(entity, KnownValue) == KnownValue("18")
    from pystrider.intake import encode_literal
    w.replace(entity, Constant(encode_literal(17)))
    symbolic.known_value(w)
    assert w.get(entity, KnownValue) == KnownValue("17")


def test_fold_is_pure_and_never_reads_known_value():
    # `fold` must answer correctly even if `KnownValue` was never run at
    # all -- it is the source `known_value` feeds, not the other way round.
    w = load("def f():\n    return 2 + 3\n")
    (entity, _a), = w.each(Arithmetic)
    w.detach(entity, KnownValue)
    assert symbolic.fold(w, entity) == 5
