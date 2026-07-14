# Absorbing library APIs as data — and the value-domain growth that shares its mechanism

*Design note, 2026-07-14. Prompted by: (a) conformance-strider needs "intake growth" (constants +
comparisons + ground evaluation) to check FOREIGN Python, and (b) the idea of absorbing common-library
APIs (pandas, textual, …) by translating their structure into graph data the rules reason over. The
thesis here is that (a) and (b) are the **same move**, and doing them together is cheaper than either
alone.*

---

## 1. The thesis: analysis KNOWLEDGE belongs in the graph as facts, not baked into rules

Today pystrider hardcodes two kinds of knowledge inside `semantics.cnl` and `intake.py`:

- **The value domain is a hardcoded pair** — `{none, object}` (`VALUE_LATTICE = [("none","is_a","none_value")]`,
  `VALUE_KINDS = {"none","object"}`). There is no `int`, `str`, `bool`, or concrete constant.
- **"What an operation produces" is implicit in the rules** — the semantics knows only None-flow (a
  Name reads its cell; an assign threads a value; a reached attribute on `none` raises). A `Constant`,
  a `Compare`, and *every library call* fall into one bucket: `unknown_expr` (`intake.py` expr() else).
  pystrider cannot know that `d.get(k)` may be `None`, that `df.groupby()` returns a `DataFrameGroupBy`
  with an `.agg()` method, or that `re.match()` returns `Optional[Match]`.

Both are the SAME shortcoming: knowledge the rules need is either absent or frozen into Python, instead
of living in the graph as **matchable facts** that generic rules consume. pystrider already follows the
better pattern elsewhere — the repair operator library is data (`operators.cnl`), the synthesis
realization bank is data (`emit.cnl`), "rules never mint; the tool pre-mints, rules select". The move
is to apply that same discipline to the value domain and to library surface:

> **Represent what-values-are and what-APIs-do as FACTS the existing generic rules reason over.**
> Growing the value domain and absorbing a library's API are two instances of one mechanism.

---

## 2. Two growths that share a mechanism

### A. The value domain (the "intake growth" conformance-strider needs)

Give intake concrete values and comparisons, as data:

- **Constants** → `?e is_a literal`, `?e has_value <v>`, `?e value_kind int|str|bool|none`. A literal
  evaluates to its own concrete value (a one-line rule), instead of being an `unknown_expr`.
- **Comparisons** → `?e is_a compare`, `?e op gt|eq|…`, `?e left ?l`, `?e right ?r`. Its truth in a
  ground scenario is computed at ugm's **§8 comparison-as-calculator boundary** (a tool injects
  `?e evals true/false`), exactly as `experiments/conformance_strider.py` already does — arithmetic in
  the tool, logic in the rules, no path explosion because each swept scenario is fully ground.
- **Booleans / branch selection / return threading** — generic rules over the ground truths.

This is the foundation conformance-strider needs to check code intaken from **real Python text**
instead of a hand-reified model. It is slice 1 because it is small, self-contained, and independently
useful (it also unblocks equality/boundary reasoning the None-only domain can't express).

### B. Library API surface (the absorption idea)

The far bigger unlock. Code using a real library is opaque to pystrider today. Absorb the API as facts
keyed by qualified name:

```
pandas.DataFrame        has_method   groupby
DataFrame.groupby       returns       pandas.core.groupby.DataFrameGroupBy
dict.get                returns_optional  yes          # may be None
os.environ.get          returns_optional  yes
re.match                returns_optional  yes
DataFrame               has_attr      columns
```

Then **generic rules consume them, and the EXISTING effects fire with no per-library authoring**:

```
# a call to a known-optional API is a may-None source -> the existing None-deref rule does the rest
?call may_be_none  when ?call resolves_to ?m and ?m returns_optional yes
?e has_value none  when ?e eval_to ?call and ?call may_be_none        # feeds semantics.cnl rule (6)
```

So `x = d.get(k); x.foo` raises `attribute_error` in the analysis — because the *absorbed fact*
`dict.get returns_optional yes` flowed through the *unchanged* None-deref semantics. A NEW effect
(`method_not_found`: calling a method the returned type doesn't have) falls out of the `has_method`
facts the same way. **Absorption is the §8 boundary run at the TYPE level**: a tool reflects a library's
declared surface into matchable facts, exactly as `rules_in_graph` reflects rule-nodes into rules, or
as intake reflects Python text into fact structure.

---

## 3. Where the absorbed facts come from

Three sources, richest first — all pure introspection, no execution of library code paths:

1. **Type stubs (`.pyi`) / `typing`** — the authoritative surface. `Optional[X]` / `X | None` return
   annotations → `returns_optional yes`; method + attribute names → `has_method` / `has_attr`; the
   class MRO → `is_subtype`. Typeshed ships stubs for the stdlib and many libraries; pandas/textual
   ship their own inline annotations.
2. **`inspect` + `typing.get_type_hints`** on the live module — signatures, return annotations,
   class members — for libraries without separate stubs.
3. **Hand-authored overrides** — a small CNL bank for the cases stubs get wrong or omit (the escape
   hatch, mirroring `codegen_understand`'s "supply the fact in CNL when there is no fingerprint").

The absorber is a `pystrider.absorb` tool (the reverse-intake boundary, like `emit.py`): `absorb(module)
-> list[(s,p,o)]`, cached per library version. It NEVER runs library code; it reads declared types.

---

## 4. Why this is the same move twice (and why that's the point)

- Both replace hardcoded/opaque knowledge with **matchable facts** a generic rule consumes.
- Both keep the **"rules never mint; knowledge is data"** invariant: intake pre-mints value/compare
  facts; the absorber pre-mints API facts; the rules only *reason*.
- Both are **§8 boundaries** (a Python tool produces facts; the firmware reasons) — the designed
  extension point, run in a new direction.
- The provenance story extends for free: a None-deref trace on library code will cite the absorbed
  fact (`because dict.get returns Optional`), which is exactly the auditable artifact pystrider sells.

The value-domain growth (A) is the small, urgent slice; the API absorption (B) is where it pays off —
once a call's value/None-ness/return-type is DATA, generic rules analyze library-using code that is
today a wall of `unknown_expr`.

---

## 4b. Bridge rules — the vocabulary crosswalk between business terms and code/API names

Business rules and code never share a vocabulary: the policy says *"premium member"*, the code says
`rank == "gold"`. conformance-strider's first cut CHEATED — policy and code both used `tier`/`total`/
`gold`, so the join was by fiat. The fix is a first-class **bridge**: a small set of declarative facts
that map business terminology onto code (or absorbed-library) names, and nothing else connects the two
worlds.

```
member_tier    bridges_attr     rank             # business attribute -> code parameter
order_spend    bridges_attr     amount
premium        bridges_value    gold             # business enum value -> code constant
discount_true  bridges_outcome  gets_discount    # code return -> business predicate
discount_false bridges_outcome  no_discount
```

The split that keeps this honest w.r.t. ugm's §8 comparison boundary:

- **The bridge is declarative data** (facts in the graph — so *"premium bridged to gold"* is visible in
  the proof).
- **The §8 calculator consults the bridge** to translate a business-term scenario into code inputs
  before grounding each comparison (arithmetic stays in the tool): `member_tier=premium` →(bridges_attr,
  bridges_value)→ `rank=gold`; `order_spend=75` → `amount=75`.
- **A genuine bridge RULE** maps the code's outcome back to the business predicate, so the crosswalk is
  in the derivation, not just the harness:
  `?sc code_outcome ?biz when ?sc code_return ?cr and ?cr bridges_outcome ?biz`.

The payoff is composability the hardcoded version can't have: swap the bridge and the same policy
re-targets a different implementation; the same business rule is checked against many codebases. And it
connects to §3 — **absorption supplies the code/library vocabulary (`DataFrame.groupby`, `dict.get`),
and bridge facts map business terms onto those absorbed names** — one crosswalk, two targets (hand-
written code, or a library surface). This is the critique's "binding layer" made first-class.

## 5. Phasing (probe-first, per the spike discipline)

1. **Value-domain growth (slice 1).** Reify constants + comparisons; ground-evaluate at the §8
   calculator; prove by porting `conformance_strider` to intake the discount function from REAL Python
   text and reproduce the same `diverges` set. *Foundation; independently useful.*
2. **Return-ness as data (slice 2).** ✅ BUILT — `experiments/api_absorption.py` (+
   `tests/test_api_absorption.py`). An absorbed `dict.get returns_optional yes` + a §8 resolution tool
   (receiver type + method → `dict.get`) + TWO bridge rules drive pystrider's REAL semantics so
   `x = d.get(k); x.attr` raises via the UNCHANGED `raises attribute_error` rule — no None hypothesis on
   any parameter, and conservative (a non-optional method or an unknown receiver type → no false
   positive). The absorbed fact just gives the call result a `none` value the existing assign/deref
   rules thread; no new None machinery.
3. **The absorber tool (slice 3).** `absorb(module)` from stubs/`typing` for a NARROW surface
   (Optional-returning methods + `has_method`) of one real library; the fact bank generated, not
   hand-authored.
4. **A library-shaped effect (slice 4).** `method_not_found` — an AttributeError from a method absent
   on a call's returned type — derived from `has_method` facts, reusing retrieval + CHOOSE + verify.

---

## 6. Honest edges (the walls, named up front)

- **Stubs are enormous and imperfect.** Scope to a surface (Optional returns + `has_method`), absorb
  conservatively, and emit UNKNOWN (the `not_modelled` / caveat discipline) rather than guess — a
  wrong absorbed fact is worse than an absent one.
- **Dynamic typing, overloads, duck typing, generics.** `Optional`-ness and member presence are the
  tractable, high-value subset; full generic/overload resolution is out of scope. When the declared
  type is `Any`/unknown, the value stays `object`/UNKNOWN — no false positives.
- **The heap/aliasing wall is unchanged.** Absorption tells us what an API *returns*; it does not model
  container contents or mutation. This stays a value-flow analysis (the deliberate scope from day one).
- **Versioning.** Absorbed facts are keyed on library version; a version bump re-absorbs (cache
  invalidation, the same shape as the rule-bank cache we just added).
