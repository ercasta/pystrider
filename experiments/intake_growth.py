"""Feasibility probe — INTAKE GROWTH: constants + comparisons + ground evaluation (docs/
api_absorption_design.md §2.A; the "intake growth" conformance-strider needs to check FOREIGN Python).

The sharp question: can pystrider intake a REAL Python decision function — one with literal constants
and comparisons, the value domain `{none, object}` cannot express — into graph facts, and DERIVE its
return value by reasoning (a §8 calculator grounds each comparison, rules do the boolean logic)? If so,
the value-domain wall the critique names is a value-domain GROWTH, and it is the foundation for
absorbing library APIs as data (the same mechanism, one level up — see the design note).

The oracle is Python itself: for every input in a boundary sweep, the REASONED result must equal the
value the actual function RETURNS when executed. Concrete evaluation, not symbolic — each scenario is
fully ground, one path taken, arithmetic delegated to the calculator (ugm's §8 boundary). No path
explosion, no solver.

Finding: it works. `def discount(tier, total): if tier == "gold" and total > 100: return True; return
False` is intaken from source text into reified compares/constants, and reasoning reproduces the real
function's output on the whole boundary sweep — with the constants (`"gold"`, `100`) living as DATA, so
this is the growth that lets the analyzer see values, not just None-ness.

Next (slice 1b, documented not built): feed a POLICY rule beside the intaken code and reuse
`conformance_strider`'s `diverges` judge — conformance checking on code intaken from real Python text
rather than a hand-reified model.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

import ugm as h
from ugm import load_machine_rules, ask_goal


# --- the ground-evaluation semantics (generic rules; the knowledge is DATA, not in the rules) ---
# A compare's truth is fed per scenario by the calculator; the rules only compose booleans and thread
# the branch to a return value. `holds` unifies "a compare the calculator marked true" and "an AND-gate
# whose children hold", so an arbitrarily nested conjunction reduces with one recursive rule.
RULES = "\n".join([
    "?sc holds ?c when ?sc compare_true ?c",
    "?sc gate_true ?g when ?g is_a andgate and ?g left ?l and ?g right ?r "
    "and ?sc holds ?l and ?sc holds ?r",
    "?sc holds ?g when ?sc gate_true ?g",
    # the function returns its THEN value when the guard holds, else its ELSE value (CWA via the NAC).
    "?sc guard_ok yes when fn guard ?g and ?sc holds ?g",
    "?sc result ?v when ?sc guard_ok yes and fn then_ret ?v",
    "?sc result ?v when fn else_ret ?v and ?sc is_a scenario and not ?sc guard_ok yes",
])


# --- intake: real Python text -> reified value/compare facts (the growth) ----------------------

_OPS = {ast.Eq: "eq", ast.NotEq: "ne", ast.Gt: "gt", ast.Lt: "lt", ast.GtE: "ge", ast.LtE: "le"}


@dataclass
class Decision:
    """An intaken `def fn(params): if COND: return A; return B` — the reified facts plus the maps a
    calculator/oracle need (each compare's (op, var, const) and the two branch return values)."""
    params: list[str]
    facts: list[tuple[str, str, str]] = field(default_factory=list)
    compares: dict[str, tuple[str, str, object]] = field(default_factory=dict)  # cmp id -> (op, var, const)
    value_of: dict[str, object] = field(default_factory=dict)   # lowercase-safe return TOKEN -> py value
    then_val: object = None
    else_val: object = None
    _n: int = 0

    def _fresh(self, p: str) -> str:
        self._n += 1
        return f"{p}{self._n}"


def _reify_bool(d: Decision, node: ast.AST) -> str:
    """Reify a boolean expression to a node id. A `Compare(Name op Constant)` becomes a `compare` node
    carrying its operator + variable + constant (the constant is DATA); an `and` folds to nested
    `andgate` nodes. Anything else is refused loudly (the probe's scope is decision kernels)."""
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        nodes = [_reify_bool(d, v) for v in node.values]
        acc = nodes[0]
        for right in nodes[1:]:                          # fold n-ary AND to nested binary andgates
            g = d._fresh("gate")
            d.facts += [(g, "is_a", "andgate"), (g, "left", acc), (g, "right", right)]
            acc = g
        return acc
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left, op, right = node.left, node.ops[0], node.comparators[0]
        if isinstance(left, ast.Name) and isinstance(right, ast.Constant) and type(op) in _OPS:
            cid = d._fresh("cmp")
            opname = _OPS[type(op)]
            d.facts += [(cid, "is_a", "compare"), (cid, "op", opname),
                        (cid, "reads", left.id), (cid, "const", repr(right.value))]
            d.compares[cid] = (opname, left.id, right.value)
            return cid
    raise ValueError(f"unsupported condition node for this probe: {ast.dump(node)}")


def intake_decision(src: str) -> Decision:
    """Intake `def fn(params): if COND: return A; return B` from real Python text into reified facts.
    The two hard-for-the-None-domain pieces — CONSTANTS and COMPARISONS — become graph data here."""
    fn = ast.parse(src).body[0]
    assert isinstance(fn, ast.FunctionDef), "expected a single function def"
    body = fn.body
    assert isinstance(body[0], ast.If) and isinstance(body[0].body[0], ast.Return) \
        and isinstance(body[-1], ast.Return), "expected `if COND: return A` then `return B`"

    d = Decision(params=[a.arg for a in fn.args.args])
    d.facts.append(("fn", "is_a", "decision_fn"))
    guard = _reify_bool(d, body[0].test)
    d.facts.append(("fn", "guard", guard))
    d.then_val = body[0].body[0].value.value          # the `return A` constant
    d.else_val = body[-1].value.value                 # the `return B` constant
    # return values get LOWERCASE-SAFE tokens (ugm CNL queries case-fold identifiers, feedback #3), with
    # a token->value map to translate the reasoned answer back to the real Python value.
    d.value_of = {"r_then": d.then_val, "r_else": d.else_val}
    d.facts += [("fn", "then_ret", "r_then"), ("fn", "else_ret", "r_else")]
    return d


# --- the §8 CALCULATOR: ground each reified comparison for one fully-bound scenario -------------

def _apply_op(op: str, a: object, b: object) -> bool:
    return {"eq": a == b, "ne": a != b, "gt": a > b, "lt": a < b, "ge": a >= b, "le": a <= b}[op]


def _scenario_facts(d: Decision, sid: str, inputs: dict[str, object]) -> list[tuple[str, str, str]]:
    """Evaluate every reified compare against this scenario's ground inputs (the arithmetic ugm
    delegates to a tool) and emit the boolean facts the rules match on."""
    facts = [(sid, "is_a", "scenario")]
    for cid, (op, var, const) in d.compares.items():
        if var in inputs and _apply_op(op, inputs[var], const):
            facts.append((sid, "compare_true", cid))
    return facts


def _graph(d: Decision, sid: str, inputs: dict[str, object]) -> "h.Graph":
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    for s, p, o in d.facts + _scenario_facts(d, sid, inputs):
        g.add_relation(n(s), p, n(o))
    return g


def evaluate(d: Decision, **inputs: object) -> object:
    """Derive the intaken function's return value for `inputs` BY REASONING (calculator grounds the
    compares, rules thread the branch). Returns the Python value, so it can be checked against the real
    function's output — Python execution as the differential oracle."""
    rules = load_machine_rules(RULES)
    g = _graph(d, "sc", inputs)
    for tok, val in d.value_of.items():                  # which reified return value did we derive?
        if ask_goal(g, f"is sc result {tok}", rules) == ["yes"]:
            return val
    return None


# --- live walkthrough: reason vs. actually running the code ------------------------------------

DISCOUNT = (
    "def discount(tier, total):\n"
    "    if tier == 'gold' and total > 100:\n"
    "        return True\n"
    "    return False\n"
)


def _boundary_inputs() -> list[dict[str, object]]:
    return [{"tier": t, "total": v} for t in ("gold", "silver") for v in (49, 50, 51, 100, 101, 200)]


def main() -> None:
    print("INTAKE GROWTH — reason about a real Python decision function (constants + comparisons)\n")
    print(DISCOUNT)
    d = intake_decision(DISCOUNT)
    print(f"  intaken: params={d.params}, {len(d.compares)} comparison(s), constants as DATA")
    for cid, (op, var, const) in d.compares.items():
        print(f"           {cid}: {var} {op} {const!r}")
    print()

    real = {}
    ns: dict[str, object] = {}
    exec(compile(DISCOUNT, "<probe>", "exec"), ns)
    fn = ns["discount"]
    print(f"  {'scenario':<22} {'reasoned':<10} {'python':<10} match")
    ok = True
    for inp in _boundary_inputs():
        reasoned = evaluate(d, **inp)
        actual = fn(**inp)
        match = reasoned == actual
        ok = ok and match
        real[tuple(inp.items())] = actual
        print(f"  {str(inp):<22} {str(reasoned):<10} {str(actual):<10} {'OK' if match else 'XX'}")
    print(f"\n  => reasoning reproduces Python execution on every input: {ok}")
    print("     (the value domain now sees CONSTANTS and COMPARISONS, not just None/object —")
    print("      the foundation for absorbing library-API return types as data; see the design note.)")


if __name__ == "__main__":
    main()
