"""Pins for the base-tier demonstration (experiments/base_tier.py).

The residual (loops with no named value-concept) is not a hole: it is base-tier code, fully operable
by footprint + execution and reusable by a derived interface — no concept name. These pins hold:
(1) a base-tier footprint is derivable from any loop AST (reads / writes / effects / iterates);
(2) a bespoke unnamed loop's interface (inputs / produced state) is derived without naming it; and
(3) it is reusable as a black-box fragment — invoked on real input, it produces the right output.
"""
import ast

from experiments.base_tier import footprint, interface, invoke, RESIDUAL_SRC


def _loop(src: str) -> ast.For:
    return next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.For))


def test_footprint_is_derivable_from_any_loop():
    fp = footprint(_loop(
        "for line in lines:\n"
        "    line = line.strip()\n"
        "    result[key] = line\n"
        "    logger.info(line)"))
    assert fp["iterates"] == {"lines"}
    assert fp["binds"] == {"line"}
    assert "result[]" in fp["writes"]                    # an index-set is a write
    assert "logger.info" in fp["effects"]                # a non-mutating call is an external effect
    assert "key" in fp["reads"]                          # a free name is an input


def test_mutating_method_counts_as_a_write():
    fp = footprint(_loop("for x in xs:\n    acc.append(x)"))
    assert "acc.append()" in fp["writes"]                # append mutates the receiver
    assert not fp["effects"]                             # ... so it is not an external effect


def test_interface_is_derived_without_a_name():
    iface = interface(RESIDUAL_SRC)
    assert "out" in iface["produces"] and "buf" in iface["produces"]   # the state it builds
    assert isinstance(iface["inputs"], list)


def test_bespoke_loop_is_reusable_as_a_black_box():
    # a line-continuation joiner — no sum/map/filter name fits, yet it reuses by interface + execution.
    out = invoke(RESIDUAL_SRC, {"lines": ["foo=1 \\", "bar", "baz=2"]}, want="out")
    assert out == ["foo=1 bar", "baz=2"]
    # and a different input, same black box
    assert invoke(RESIDUAL_SRC, {"lines": ["a", "b"]}, want="out") == ["a", "b"]
