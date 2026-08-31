"""`pystrider.symbolic` — constant folding, in isolation. No `Case`, no
`Given`, no request: `KnownValue` is either derivable from structure alone or
it is silently absent."""
from __future__ import annotations

from loopingrules.loop import Loop
from pystrider import symbolic
from pystrider.intake import (Arithmetic, Assign, Assigned, Body, Call,
                              Callee, Comparison, Constant, Function, Name,
                              Stmt, Value, intake)
from pystrider.symbolic import BoundTo, KnownValue


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


# -- `bound_to`/`BoundTo` -- the second slice, thread 6's motivating case --

def _callee_name(w):
    """The `Name` entity a source's single bare-call statement's `Callee`
    names -- every binding test below reads a `Call`'s target this way."""
    (call, _c), = w.each(Call)
    callee = w.get(call, Callee)
    return callee.entity


def test_a_straight_line_binding_resolves_to_the_assigned_value():
    # The motivating case, named directly in `docs/TODO.md`: finding a call
    # site through indirection.
    w = load("def helper():\n    return 1\n\n\ndef f():\n    g = helper\n    g()\n")
    name = _callee_name(w)
    assert w.get(name, Name).id == "g"
    bound = w.get(name, BoundTo)
    assert bound is not None
    assert w.get(bound.entity, Name) == Name("helper")


def test_reassignment_anywhere_in_the_function_abstains():
    w = load("def f():\n    g = helper\n    g = other\n    g()\n")
    assert w.get(_callee_name(w), BoundTo) is None


def test_a_binding_in_a_different_branch_abstains():
    # Assigned inside the `if`, used after it -- one candidate, but not
    # provably on the path to the use; refused by POSITION (different
    # block), not by guessing whether `cond` is true.
    w = load("def f(cond):\n    if cond:\n        g = helper\n    g()\n")
    assert w.get(_callee_name(w), BoundTo) is None


def test_a_use_before_its_assignment_abstains():
    w = load("def f():\n    g()\n    g = helper\n")
    assert w.get(_callee_name(w), BoundTo) is None


def test_a_name_with_no_assignment_at_all_gets_no_bound_to():
    w = load("def f(g):\n    g()\n")
    assert w.get(_callee_name(w), BoundTo) is None


def test_bound_to_is_pure_and_never_reads_bound_to():
    # Same discipline as `fold`: must answer correctly even if
    # `resolved_binding` never ran, or already ran and was detached.
    w = load("def f():\n    g = helper\n    g()\n")
    name = _callee_name(w)
    w.detach(name, BoundTo)
    target = symbolic.bound_to(w, name)
    assert target is not None
    assert w.get(target, Name) == Name("helper")


def test_recognizing_an_already_known_binding_is_not_a_change():
    w = load("def f():\n    g = helper\n    g()\n")
    before = w.revision
    symbolic.resolved_binding(w)
    assert w.revision == before


def test_a_binding_added_later_makes_a_stale_binding_reconsidered():
    # The same TMS shape `KnownValue` pins above, for `BoundTo`: a second
    # `Assign` to the same name, added after the fact (e.g. by a future
    # generator/repair), must drop the now-ambiguous binding the very next
    # tick, not leave a confidently-wrong `BoundTo` standing.
    w = load("def f():\n    g = helper\n    g()\n")
    name = _callee_name(w)
    assert w.get(name, BoundTo) is not None
    (func, _f), = ((e, c) for e, c in w.each(Function) if c.name == "f")
    block = w.get(func, Body).entity
    target = w.spawn(Name("g"))
    value = w.spawn(Name("other"))
    second_assign = w.spawn(Assign())
    w.attach(second_assign, Assigned(target))
    w.attach(second_assign, Value(value))
    w.attach(block, Stmt(second_assign))
    symbolic.resolved_binding(w)
    assert w.get(name, BoundTo) is None
