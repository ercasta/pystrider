"""Feasibility probe — API ABSORPTION, slice 2: an absorbed library-API fact flows through the
EXISTING None-deref semantics (docs/api_absorption_design.md §2.B, §5 phase 2).

The sharp question: today `x = d.get(k); x.attr` is invisible to the analyzer — a method call is an
opaque value, so nothing knows `dict.get` can return `None`. If we ABSORB that fact from the library's
declared surface (`dict.get returns_optional yes`) and add a TINY bridge (a call to a known-optional
API is a may-None value), does the UNCHANGED None-deref effect then fire on the deref? If so, analyzing
real library-using code is a matter of absorbing facts, not authoring per-library rules.

This probe drives pystrider's REAL operational semantics (`pystrider.semantics.SEMANTICS`) + the real
intake — it adds only (a) the absorbed API facts, (b) a resolution TOOL that names each call's target
(receiver type + method → `dict.get`, the §8 boundary), and (c) TWO bridge rules. The AttributeError
that surfaces is derived by the SAME `?e raises attribute_error …` rule pystrider already ships; the
absorbed fact just gives the call result a `none` value the existing assign/deref rules thread.

Finding: it works, and it is conservative. `x = d.get(k); x.attr` raises when `d` is known to be a
`dict` (so the call resolves to the absorbed-optional `dict.get`); it does NOT raise for a non-optional
method (`str.upper`), nor when the receiver type is unknown (no resolution → no false positive).

Slice 3 (`pystrider.absorb`) GENERATES the fact bank from a real declared surface; slice 4
(`find_method_not_found`) adds a SECOND library-shaped effect — a method absent on a call's returned
type — from the absorbed `has_method` facts, with a one-hop type flow and no per-library rule.
"""
from __future__ import annotations

import ugm as h
from ugm import load_machine_rules, write_rule, AttrGraph, suppose, CONFIRMED

from pystrider.semantics import SEMANTICS          # the REAL operational semantics (CNL text)
from pystrider.intake import intake_function, Intake
from pystrider.analysis import _kb_from


# --- the ABSORBED API bank: facts a real absorber emits from type stubs / typing (docs §3) ------
# `Optional[X]` / `X | None` return annotations -> `returns_optional yes`. These BUILTIN facts stay
# hand-authored because builtins carry their Optional-ness only in typeshed `.pyi` stubs, not live
# annotations (`dict.get` has no readable return hint). Slice 3 — the `absorb(module)` tool
# (`pystrider.absorb`) — GENERATES this shape from any live-annotated surface; see `main()` PART 2.
API_FACTS: list[tuple[str, str, str]] = [
    ("dict.get", "returns_optional", "yes"),
    ("os.environ.get", "returns_optional", "yes"),
    ("re.match", "returns_optional", "yes"),
    ("str.upper", "returns_optional", "no"),        # a NON-optional control
]

# --- the ABSORPTION BRIDGE: TWO rules turning "a call to an optional API" into a may-None value --
# The ONLY new reasoning. Everything downstream (assign threads the value, a reached deref on a
# none-valued base raises) is pystrider's existing semantics, unchanged.
BRIDGE_RULES = "\n".join([
    "?call may_be_none yes when ?call resolves_to ?m and ?m returns_optional yes",
    "?call eval_to none when ?call may_be_none yes",
])

# slice 4 — the method_not_found effect: a method CALL on a base whose TYPE is known but does not
# declare the method raises AttributeError, derived from the absorbed `has_method` facts with NO
# per-library rule. Restricted to CALLED attribute nodes (`?call calls ?attr`), so a plain attribute
# access — which would need `has_attr`, not `has_method` — never trips it (conservative).
METHOD_NOT_FOUND_RULE = (
    "?attr raises method_not_found when ?call calls ?attr and ?attr on_type ?type "
    "and ?attr attr_name ?method and not ?type has_method ?method"
)


def _rule_graph() -> AttrGraph:
    """The real semantics + the absorption-bridge rules (None-flow) + the method_not_found rule."""
    rg = AttrGraph()
    for r in load_machine_rules(SEMANTICS + "\n" + BRIDGE_RULES + "\n" + METHOD_NOT_FOUND_RULE):
        write_rule(rg, r)
    return rg


def _resolve_calls(ik: Intake, receiver_types: dict[str, str]) -> list[tuple[str, str, str]]:
    """The §8 RESOLUTION tool: name each method call's target as `<receiver-type>.<method>`, given the
    receiver variables' types (the binding a caller supplies, or a future type inference provides).
    Reads the reified call — `call calls <attr>`, `attr attr_name get`, `attr attr_of <name>`,
    `name reads <var>` — and emits a `resolves_to` fact the bridge rule keys on. Nothing arithmetic;
    pure structure → the calculator-boundary category (cf. `rules_in_graph`)."""
    f = ik.facts
    out: list[tuple[str, str, str]] = []
    for (s, p, o) in f:
        if p != "calls":
            continue
        call, attrnode = s, o
        method = next((oo for (ss, pp, oo) in f if ss == attrnode and pp == "attr_name"), None)
        recv_expr = next((oo for (ss, pp, oo) in f if ss == attrnode and pp == "attr_of"), None)
        recv_var = next((oo for (ss, pp, oo) in f if ss == recv_expr and pp == "reads"), None) if recv_expr else None
        src = ik.var_source(recv_var) if recv_var else None
        if method and src in receiver_types:
            out.append((call, "resolves_to", f"{receiver_types[src]}.{method}"))
    return out


def analyze_with_absorption(src: str, receiver_types: dict[str, str],
                            api_facts: list[tuple[str, str, str]] | None = None) -> list[str]:
    """Intake `src`, absorb the API facts + resolve each call, then ask the REAL semantics (+ bridge)
    which attribute sites raise — with NO None hypothesis on any parameter (the None comes only from an
    absorbed-optional call result). Returns the source labels of the raising sites. `api_facts` defaults
    to the hand-authored builtins bank; pass `pystrider.absorb(cls).facts` to drive off a GENERATED bank
    (slice 3 — the absorber tool), proving the same mechanism runs on facts read from a real surface."""
    ik = intake_function(src)
    extra = list(api_facts if api_facts is not None else API_FACTS) + _resolve_calls(ik, receiver_types)
    kb = _kb_from(ik, extra)
    rg = _rule_graph()
    hits = [site for site in ik.attributes
            if suppose(kb, [], [("raises", site, "attribute_error")],
                       rules=rg, commit=False).status == CONFIRMED]
    return [ik.label_of.get(s, s) for s in hits]


# --- slice 4: the method_not_found effect — a method absent on a call's returned type -----------
# A NEW library-shaped effect (the mirror of slice C's returns_none): reasoning over the absorbed
# `has_method` facts, with NO per-library rule, flags a method call whose receiver type does not
# declare the method. The receiver TYPE is established by a one-hop flow — a parameter's given type,
# or the absorbed RETURN type of a call assigned to a variable (`r = s.repo()` -> r: _DemoRepo).

def _fact(ik: Intake, subj: str, pred: str) -> str | None:
    """The single object of `(subj, pred, ?)` in intake's facts, or None (a small structural lookup)."""
    return next((o for (s, p, o) in ik.facts if s == subj and p == pred), None)


def infer_types(ik: Intake, receiver_types: dict[str, str],
                api_facts: list[tuple[str, str, str]]) -> dict[str, str]:
    """One-hop TYPE FLOW to a fixpoint: seed each parameter's GIVEN type, then propagate the absorbed
    RETURN type of every resolved call assigned to a variable — `r = s.repo()` with `_DemoSession.repo
    returns _DemoRepo` yields `r: _DemoRepo`. Returns a source-name -> type-name map. Conservative: a
    call on an unknown receiver type, or a method with no absorbed `returns` fact, propagates nothing."""
    returns = {s: o for (s, p, o) in api_facts if p == "returns"}     # 'Type.method' -> ReturnType
    var_types = dict(receiver_types)
    changed = True
    while changed:                                                   # fixpoint -> order-independent
        changed = False
        for (s, p, o) in ik.facts:
            if p != "from_expr":                                    # an assign's RHS expression
                continue
            var, attrnode = _fact(ik, s, "assigns"), _fact(ik, o, "calls")
            if not (var and attrnode):
                continue
            method = _fact(ik, attrnode, "attr_name")
            recv_type = var_types.get(ik.attr_base_var.get(attrnode))
            rt = returns.get(f"{recv_type}.{method}") if (recv_type and method) else None
            if rt and var_types.get(var) != rt:
                var_types[var] = rt
                changed = True
    return var_types


def _on_type_facts(ik: Intake, var_types: dict[str, str]) -> list[tuple[str, str, str]]:
    """Tag each CALLED attribute node with its receiver's inferred type (`?attr on_type ?T`) — the
    binding the method_not_found rule reasons over. Only called nodes are tagged (a plain attribute
    access would need `has_attr`, not `has_method`), so the rule never fires on a bare field read."""
    called = {o for (s, p, o) in ik.facts if p == "calls"}
    return [(attr, "on_type", var_types[ik.attr_base_var[attr]])
            for attr in ik.attributes
            if attr in called and ik.attr_base_var.get(attr) in var_types]


def find_method_not_found(src: str, receiver_types: dict[str, str],
                          api_facts: list[tuple[str, str, str]] | None = None) -> list[str]:
    """Detect method_not_found: a method call whose receiver TYPE (given, or absorbed-inferred through a
    return) does not declare the method. Drives the REAL semantics + the method_not_found rule over the
    absorbed `has_method` facts; returns the offending sites' source labels. Conservative — an unknown
    receiver type yields no `on_type`, so no false positive."""
    bank = list(api_facts if api_facts is not None else API_FACTS)
    ik = intake_function(src)
    var_types = infer_types(ik, receiver_types, bank)
    kb = _kb_from(ik, bank + _on_type_facts(ik, var_types))
    rg = _rule_graph()
    hits = [attr for attr in ik.attributes
            if suppose(kb, [], [("raises", attr, "method_not_found")],
                       rules=rg, commit=False).status == CONFIRMED]
    return [ik.label_of.get(a, a) for a in hits]


# --- live walkthrough -------------------------------------------------------------------------

OPTIONAL_GET = "def f(d, k):\n    x = d.get(k)\n    return x.rows\n"          # dict.get -> Optional
NON_OPTIONAL = "def g(s):\n    x = s.upper()\n    return x.rows\n"            # str.upper -> not optional


# a representative annotated surface at MODULE scope (so `get_type_hints` resolves the forward ref, as
# it does for a real library's module-level classes) — `absorb` reads these declared hints in PART 2.
class _DemoItem: ...


class _DemoRepo:
    def find(self, k) -> "_DemoItem | None": ...     # Optional -> absorbed `returns_optional yes`
    def load(self, k) -> _DemoItem: ...              # non-optional -> `returns_optional no`
    # note: NO `delete` method -> a call to it is method_not_found


class _DemoSession:
    def repo(self) -> _DemoRepo: ...                 # concrete return -> absorbed `returns _DemoRepo`


def main() -> None:
    print("API ABSORPTION (slice 2) — an absorbed library fact flows through the EXISTING None-deref\n")
    print("  absorbed:  dict.get returns_optional yes | str.upper returns_optional no")
    print("  bridge:    a call resolving to a returns_optional API -> its result may be none\n")

    print("  def f(d, k): x = d.get(k); return x.rows      # d is a dict")
    hits = analyze_with_absorption(OPTIONAL_GET, {"d": "dict"})
    print(f"    -> raises: {hits}")
    print("       (the absorbed `dict.get returns_optional` gave x a none value, and pystrider's")
    print("        UNCHANGED deref rule raised on `x.rows` — no None hypothesis on any parameter.)\n")

    print("  def g(s): x = s.upper(); return x.rows        # s is a str")
    hits2 = analyze_with_absorption(NON_OPTIONAL, {"s": "str"})
    print(f"    -> raises: {hits2}   (str.upper is NOT optional -> no false positive)\n")

    print("  def f(d, k): x = d.get(k); return x.rows      # receiver type UNKNOWN")
    hits3 = analyze_with_absorption(OPTIONAL_GET, {})
    print(f"    -> raises: {hits3}   (unresolved call -> conservative, no false positive)")

    print("\nPART 2 (slice 3) — the fact bank is now GENERATED by `absorb`, not hand-authored\n")
    from pystrider import absorb
    from textual.widget import Widget
    bank = absorb(Widget)                      # a REAL installed library, live-absorbed (reads hints only)
    print(f"  absorb(textual.Widget): {bank.summary()}")
    print(f"    e.g. Widget.check_action returns_optional yes  (from `-> bool | None`), "
          f"Widget.get_selection yes  (from `-> tuple[str,str] | None`)")
    print(f"    omitted (undecidable return, surfaced not guessed): {len(bank.omitted)} method(s)\n")

    # the generated bank drives the SAME deref effect, on a representative annotated class:
    rbank = absorb(_DemoRepo)
    src = "def f(r, k):\n    x = r.find(k)\n    return x.rows\n"
    print(f"  absorb(_DemoRepo).facts -> {rbank.facts}")
    print(f"    def f(r,k): x = r.find(k); return x.rows   ({{'r':'_DemoRepo'}}) -> raises: "
          f"{analyze_with_absorption(src, {'r': '_DemoRepo'}, rbank.facts)}")
    print("    (a GENERATED `_DemoRepo.find returns_optional yes` flowed through the UNCHANGED deref")
    print("     rule — absorbing a library is now reading its declared surface, not authoring rules.)")

    print("\nPART 3 (slice 4) — a NEW effect from the same facts: method_not_found\n")
    bank = absorb(_DemoSession).facts + absorb(_DemoRepo).facts
    print("  absorbed: _DemoSession has_method repo | _DemoSession.repo returns _DemoRepo |")
    print("            _DemoRepo has_method {find, load}   (NO `delete`)\n")
    chained = "def f(s, k):\n    r = s.repo()\n    return r.delete(k)\n"
    print("  def f(s, k): r = s.repo(); return r.delete(k)     # s is a _DemoSession")
    print(f"    -> method_not_found: {find_method_not_found(chained, {'s': '_DemoSession'}, bank)}")
    print("       (r's type is INFERRED _DemoRepo from the absorbed return of s.repo(); _DemoRepo has no")
    print("        `delete` -> the method access raises, from `has_method` facts, no per-library rule.)\n")
    ok = "def h(t, k):\n    return t.find(k)\n"
    print(f"  def h(t, k): return t.find(k)  (t: _DemoRepo)      -> "
          f"{find_method_not_found(ok, {'t': '_DemoRepo'}, bank) or '[]  (find exists -> no false positive)'}")
    print(f"  same call, receiver type UNKNOWN                   -> "
          f"{find_method_not_found(chained, {}, bank) or '[]  (unresolved -> conservative)'}")


if __name__ == "__main__":
    main()
