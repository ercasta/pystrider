"""Footprint synthesis — derive what a fragment of code writes from the code itself.

grammapy's whole non-interference guarantee (Accumulate's disjoint-writes, and the frame rule the
other combinators share) is decided from **footprints**. When a footprint is HAND-DECLARED it is a
trusted input nothing checks: a fragment can declare it writes `out.shifted` while its code writes
`out.scaled`, and the check — reasoning over the declaration — admits a composition that collides at
runtime. That is the one hand-written link in a chain whose whole point is "trust by checking, not by
claim" (`experiments/footprint_honesty.py` named the gap; this module closes it).

`footprint_of(source)` derives the write footprint from the CODE, two independent ways, cross-checked
(the project's standing two-oracle discipline — each covers the other's blind spot):

  * STATIC  — an AST scan of assignment targets. Branch-complete (sees writes on every arm, even
    untaken ones), but a computed key (`out[k] = …`) it can only mark ``out.<computed>``.
  * DYNAMIC — run the code in an instrumented store and observe the keys actually written. Resolves a
    computed key concretely, but only sees the branch THIS input took.

Their UNION is the sound footprint for a disjointness check (over-approximation is safe — it may flag a
maybe-collision, never miss a real one); their AGREEMENT is a confidence signal.

This is the analysis half's contribution to the composition half's guarantee. The two halves are
decoupled (pystrider does not import grammapy), so this module stays grammapy-free and returns a neutral
``CodeFootprint``; a caller adapts it into a grammapy ``Footprint`` at the seam. Channels are the shared
store's keys, named ``<store>.<key>``.

Scope of this slice: WRITES (the load-bearing input to Accumulate). Reads and control ``emits`` (the
Scope combinator's footprint) are the next extension — same two-oracle shape, a different AST/observe
rule. Honest limit: static synthesis of ARBITRARY code is undecidable (aliasing, computed targets); the
supported scope is self-contained fragments, with the dynamic oracle sound for what it actually ran.
"""
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass
from functools import lru_cache

__all__ = ["CodeFootprint", "footprint_of", "static_writes", "dynamic_writes", "modelable"]


# --- STATIC synthesis: the write channels an AST assigns to -----------------------------------------

def _target_channel(t: ast.expr, consts: "dict[str, frozenset[object]] | None" = None
                    ) -> "tuple[str, ...]":
    """The channels a single assignment target writes. ``out['k'] = …`` -> ``out.k``; a key held by a name
    PROVABLY bound to constants (``k = 'total'``; `consts`) -> that constant's channel, one per possible
    binding; any other computed key ``out[expr] = …`` -> ``out.<computed>`` (static cannot resolve it, and
    the placeholder is a WILDCARD the check must honour); a bare name is a local, not a shared channel, so
    it is not a footprint write."""
    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
        key = t.slice
        if isinstance(key, ast.Constant):
            return (f"{t.value.id}.{key.value}",)
        if isinstance(key, ast.Name) and consts and key.id in consts:
            return tuple(f"{t.value.id}.{v}" for v in sorted(consts[key.id], key=str))
        return (f"{t.value.id}.<computed>",)
    return ()


def _const_bindings(root: ast.AST) -> "dict[str, frozenset[object]]":
    """Names in this scope bound ONLY to literal constants, mapped to every constant they can hold.

    This is what lets static name a key it would otherwise have to write off as ``<computed>``: in
    ``k = 'total'`` / ``out[k] = x`` the key IS statically known, and proving it beats guessing it from a
    single run. A name is admitted only when EVERY binding of it in the scope is a constant — one
    non-constant or non-assignment binding (an ``AugAssign``, a loop/``with``/``except`` target, a
    comprehension variable, a function parameter) poisons it back to unknown. Multiple constant bindings
    keep them ALL, so the resulting channel set is a branch-complete over-approximation (sound), never a
    pick. Deliberately NOT constant propagation: no arithmetic, no aliasing, no cross-scope flow — the
    provable sliver only, everything else abstains to the wildcard."""
    values: "dict[str, set[object]]" = {}
    poisoned: set[str] = set()

    def bind(target: ast.expr, value: "ast.expr | None") -> None:
        for leaf in (target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target]):
            if not isinstance(leaf, ast.Name):
                continue
            # only a whole-name assignment of a bare literal is provable; unpacking splits the value, so
            # the leaf's own value is not this node's `value` -> unknown.
            if (value is not None and isinstance(value, ast.Constant)
                    and not isinstance(target, (ast.Tuple, ast.List))):
                values.setdefault(leaf.id, set()).add(value.value)
            else:
                poisoned.add(leaf.id)

    if isinstance(root, (ast.FunctionDef, ast.AsyncFunctionDef)):
        a = root.args
        poisoned.update(p.arg for p in a.posonlyargs + a.args + a.kwonlyargs)
        poisoned.update(p.arg for p in (a.vararg, a.kwarg) if p)
    for node in _walk_own_scope(root):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                bind(t, node.value)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            bind(node.target, node.value if isinstance(node, ast.AnnAssign) else None)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            bind(node.target, None)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            bind(node.optional_vars, None)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            poisoned.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            poisoned.update((al.asname or al.name).split(".")[0] for al in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node is not root:
                poisoned.add(node.name)
    return {n: frozenset(vs) for n, vs in values.items() if n not in poisoned}


# Known container in-place MUTATORS — they write the whole container (no key), so their effect is the
# coarse channel ``<store>.<items>`` (a list/set/deque has no key to name). READERS write nothing. Any
# OTHER method is unknown — it could mutate in a way we don't model, so it abstains.
_MUTATOR_METHODS = frozenset({
    "append", "appendleft", "extend", "extendleft", "insert", "add", "update", "setdefault",
    "pop", "popitem", "remove", "discard", "clear", "sort", "reverse", "rotate",
    "intersection_update", "difference_update", "symmetric_difference_update",
})
_READER_METHODS = frozenset({"get", "keys", "values", "items", "copy", "count", "index", "fromkeys"})


# --- INTER-PROCEDURAL: follow the store into a LOCAL helper -----------------------------------------
# A store passed to a callee (`h(out)`) is normally an out-of-view write. But when the callee is a
# function DEFINED IN VIEW (a local helper), the write is not out of view at all — it can be modelled
# EXACTLY by mapping the store onto the callee's parameter and deriving the callee's footprint. This is
# the write-side analog of `session.link_calls` (arg cell -> param cell): the argument the store lands
# on IS the store, under the callee's local name. Opaque callees (builtins, imports, a name with no
# local def) stay an honest escape — this only ever follows a def it can see.

def _local_helpers(tree: ast.AST) -> "dict[str, ast.FunctionDef]":
    """Every function DEFINED in this source, by name — the callees whose bodies are in view and so can
    be followed EXACTLY (not guessed at). A later def wins on a duplicate name (last binding), matching
    Python's own rebind order."""
    helpers: "dict[str, ast.FunctionDef]" = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            helpers[n.name] = n
    return helpers


def _passed_to_local(call: ast.AST, store: str, helpers: "dict[str, ast.FunctionDef]"
                     ) -> "tuple[ast.FunctionDef, str] | None":
    """If `call` passes the bare store name DIRECTLY to a local helper, return `(callee, param_name)` —
    the callee and the local name the store lands on inside it. Only a direct positional/keyword `Name`
    argument is followed; a starred arg, or the store buried in a sub-expression (`h(out or {})`), is
    NOT a clean hand-off and stays an escape (returns None -> caller abstains)."""
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
        return None
    h = helpers.get(call.func.id)
    if h is None:
        return None
    params = h.args.posonlyargs + h.args.args
    for i, a in enumerate(call.args):
        if isinstance(a, ast.Name) and a.id == store and i < len(params):
            return h, params[i].arg
    for kw in call.keywords:
        if kw.arg and isinstance(kw.value, ast.Name) and kw.value.id == store:
            return h, kw.arg
    return None


def _analysis_root(tree: ast.Module) -> ast.AST:
    """The scope whose writes `static_writes` reports. When the whole source is a SINGLE function (the
    corpus convention — one `def foo(): …`), that function IS the scope; otherwise the module. Either way,
    a NESTED helper def below the root is not part of it — its writes are the callee's internal frame,
    surfaced (renamed) only when a call actually follows into it (`_followed_static_writes`)."""
    body = tree.body
    if len(body) == 1 and isinstance(body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return body[0]
    return tree


def _walk_own_scope(root: ast.AST):
    """`root` and its descendants, WITHOUT descending into nested function/lambda bodies (a separate
    scope, followed explicitly through calls rather than merged in blind)."""
    yield root
    for child in ast.iter_child_nodes(root):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield from _walk_own_scope(child)


def static_writes(source: str) -> "frozenset[str]":
    """Scan the AST for every channel written on ANY path (both arms of a branch): assignment targets
    (including tuple/list unpacking and augmented assignment) AND recognized container MUTATOR methods
    (``lst.append(x)`` / ``s.add(x)`` / ``d.update(…)`` -> the whole-container channel ``<store>.<items>``).
    Branch-complete; a computed subscript key stays unresolved as ``<store>.<computed>``. Writes inside a
    NESTED helper def are excluded (they are the callee's frame — surfaced only when a call follows in)."""
    tree = ast.parse(textwrap.dedent(source))
    root = _analysis_root(tree)
    consts = _const_bindings(root)
    writes: set[str] = set()
    for node in _walk_own_scope(root):
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AugAssign) else [])
        for t in targets:
            for leaf in (t.elts if isinstance(t, (ast.Tuple, ast.List)) else [t]):
                writes.update(_target_channel(leaf, consts))
        writes.update(_method_write_channels(node))          # lst.append(x) / d.update({...}) / d.setdefault(k)
    return frozenset(writes)


def _method_write_channels(node: ast.AST) -> "tuple[str, ...]":
    """Channels a recognized container MUTATOR call writes. A dict method with LITERAL keys is named
    exactly (``d.update({'a': 1})`` -> ``d.a``; ``d.setdefault('k', …)`` -> ``d.k``); everything else — a
    list/set mutation (``lst.append`` / ``s.add``) or a non-literal dict update — is the coarse whole-
    container channel ``<store>.<items>`` (no key to name)."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.attr in _MUTATOR_METHODS):
        return ()
    base, meth = node.func.value.id, node.func.attr
    if meth == "setdefault" and node.args:
        k = node.args[0]
        return (f"{base}.{k.value}" if isinstance(k, ast.Constant) else f"{base}.<items>",)
    if meth == "update":
        chans: list[str] = []
        for a in node.args:
            if isinstance(a, ast.Dict) and all(isinstance(k, ast.Constant) for k in a.keys):
                chans += [f"{base}.{k.value}" for k in a.keys]     # d.update({'a':1}) — literal keys, exact
            else:
                chans.append(f"{base}.<items>")                    # d.update(var) / set.update — whole container
        chans += [f"{base}.{kw.arg}" if kw.arg else f"{base}.<items>" for kw in node.keywords]
        return tuple(chans) if (node.args or node.keywords) else ()
    return (f"{base}.<items>",)                                    # append / add / extend / insert / pop / …


# --- ABSTENTION: when can this even be modelled? (know when you don't know) -------------------------

def _subscript_base(node: ast.expr) -> ast.expr:
    """Peel `store[a][b]…` down to its base expression (`store`)."""
    while isinstance(node, ast.Subscript):
        node = node.value
    return node


def _is_fresh_container(value: ast.expr) -> bool:
    """A value that binds the store to a NEW empty/literal mutable container — a clean (re)init that
    introduces no alias: ``{}`` / ``[]`` / ``{1}`` literals, or ``dict()`` / ``list()`` / ``set()``.
    A *comprehension* (`{k: v for …}`) is deliberately NOT fresh: it builds the container by writes the
    subscript model never sees, so an accumulator bound that way must abstain."""
    if isinstance(value, (ast.Dict, ast.List, ast.Set)):     # {} [] {..}  (NOT DictComp/ListComp/SetComp)
        return True
    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id in ("dict", "list", "set")):
        return True
    return False


def _store_ref_is_safe(node: ast.Name, parent: "ast.AST | None") -> bool:
    """Is this reference to the store harmless for footprint derivation? A store reference is safe when it
    is subscripted, cleanly (re)bound, or merely READ — and unsafe when it could carry an out-of-view
    WRITE (a method mutation, a callee, an alias, an operator-mutation)."""
    if isinstance(parent, ast.Subscript) and parent.value is node:
        return True                                          # store[...]          (the visible write/read)
    if (isinstance(parent, ast.Attribute) and parent.value is node
            and parent.attr in (_MUTATOR_METHODS | _READER_METHODS)):
        return True                                          # store.append(...) / store.get(...)  (a KNOWN method)
    if isinstance(parent, ast.Assign) and node in parent.targets and _is_fresh_container(parent.value):
        return True                                          # store = {}          (a clean init, not an alias)
    if isinstance(parent, (ast.Return, ast.Yield, ast.YieldFrom)) and getattr(parent, "value", None) is node:
        return True                                          # return store        (leaves scope; no in-scope write)
    if isinstance(parent, ast.Compare) and (node is parent.left or node in parent.comparators):
        return True                                          # k in store / store == y   (a read)
    if isinstance(parent, (ast.For, ast.AsyncFor, ast.comprehension)) and parent.iter is node:
        return True                                          # for k in store      (a read)
    return False


def modelable(source: str, *, store: str = "out", helpers: "dict[str, ast.FunctionDef] | None" = None
              ) -> bool:
    """Statically decide whether `footprint_of` can SOUNDLY derive this code's write footprint for
    ``store``. The static/dynamic oracles only capture writes made by **subscripting the store directly**
    (``store[k] = …``). If a write could reach the store any OTHER way — out of view of that model — a
    derived footprint may silently MISS it, so the honest answer is *unknown*, not a confident under-approx.

    A reference to the store is SAFE when it is subscripted (`store[...]`), a KNOWN container method — a
    MUTATOR (`store.append/.add/.extend/.update/.setdefault/.pop/…` -> the whole-container `<items>`
    channel) or a READER (`store.get/.keys/.items/…` -> nothing) — cleanly (re)bound to a fresh container
    (`store = {}`), or merely READ (`return store`, `k in store`, `for k in store`). It is an ESCAPE — and
    abstains — when it could carry an out-of-view write:

      * an UNKNOWN method on it        ``store.some_custom_method(...)``        (might mutate in a way we don't model)
      * an operator-mutation           ``store |= {...}``                      (an aug-assign to the bare name)
      * passed to an OPAQUE callee     ``ext(store)`` (no local def)           (writes happen out of view)
      * the store aliased              ``d = store`` / ``box = [store]``        (writes through the alias are unseen)
      * a chained subscript on it      ``store[a][b] = …``                     (writes through the inner object)
      * built by a comprehension       ``store = {k: v for …}``                (comprehension writes are unseen)

    This is a **sound over-refusal**, an enumerated boundary (not a full alias analysis): it never blesses
    a construct it cannot see through, and hands off — the membrane where the core says 'I don't know'. A
    call argument is refused conservatively even for a pure read (`len(store)`): the callee is opaque.

    A store passed to a LOCAL HELPER — a callee whose def is in view (``h(out)`` with ``def h(o): …`` in
    the same source) — is NOT an escape: it is followed EXACTLY, mapping the store onto ``h``'s parameter
    and requiring ``h`` modelable on it (recursively, cycle-guarded). Only an OPAQUE callee (a builtin, an
    import, an undefined name) stays an escape.

    BOUNDARY on the whole-container channel: a mutator write is the coarse ``<items>`` (a list/set has no
    key to name). A consuming disjointness check MUST treat ``<items>`` / ``<computed>`` as store-WILDCARDS
    — conflicting with any same-store write by a distinct item — or a store mixed between keyed and
    whole-container writes is certified disjoint while one write clobbers the other. `modelable` is
    therefore NOT the only gate a consumer owes: a modelable footprint can still be coarse.
    `grammapy.disjoint_writes` honours the wildcard reading; a different consumer must do the same.

    ``helpers`` supplies callees defined OUTSIDE ``source`` (a module's sibling functions when ``source``
    is one function of it) so a store passed to a sibling is followed too; defs local to ``source`` win on
    a name clash. Omit it and only in-``source`` callees are followed (the self-contained-fragment case)."""
    tree = ast.parse(textwrap.dedent(source))
    table = _local_helpers(tree)
    if helpers:
        table = {**helpers, **table}                         # a def local to `source` shadows a sibling
    return _scope_modelable(tree, store, table, frozenset())


def _scope_modelable(tree: ast.AST, store: str, helpers: "dict[str, ast.FunctionDef]",
                     visited: "frozenset[str]") -> bool:
    """The recursive core of `modelable`: is every reference to `store` in `tree` one the write model can
    see through? Follows a clean hand-off to a local helper (via `helpers`) by re-asking the question of
    the callee's parameter; `visited` guards a helper-call cycle (a name already being proven up-stack is
    taken as safe — sound, since the whole cycle is on the hook for its own modelability)."""
    parent: "dict[int, ast.AST]" = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node
    # a chained subscript on the store (`store[a][b] = …`) writes through the inner object — out of model.
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Subscript):
            base = _subscript_base(node.value)
            if isinstance(base, ast.Name) and base.id == store:
                return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == store:
            p = parent.get(id(node))
            if _store_ref_is_safe(node, p):
                continue
            # a clean hand-off to a local helper: follow it (an exact model), don't abstain.
            if isinstance(p, ast.Call):
                res = _passed_to_local(p, store, helpers)
                if res is not None:
                    h, param = res
                    if h.name in visited or _scope_modelable(h, param, helpers, visited | {h.name}):
                        continue
            return False
    return True


# --- DYNAMIC synthesis: the channels the code actually writes when run ------------------------------

class _RecordingStore(dict):
    """An instrumented store: it records the channel name (``<store>.<key>``) of every key written to
    it. The observable boundary the fragment's execution is watched through (the concrete-exec oracle)."""
    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.written: set[str] = set()

    def __setitem__(self, key: object, value: object) -> None:
        self.written.add(f"{self._name}.{key}")
        super().__setitem__(key, value)


def dynamic_writes(source: str, *, store: str = "out", x: int = 5) -> "frozenset[str]":
    """RUN the code against an instrumented ``store`` and return the channels it wrote for THIS input.
    Resolves computed keys concretely, but only sees the branch this input takes. Safe for self-contained
    fragments (their bodies write only the store); the caller owns what code it hands in."""
    out = _RecordingStore(store)
    # ONE namespace (globals only): a local helper the store is passed into is looked up here, and its
    # body's free vars (`x`) resolve here too — a split globals/locals would hide both from the callee.
    try:
        exec(compile(textwrap.dedent(source), "<fragment>", "exec"), {store: out, "x": x})
    except Exception:
        # This input's run diverged before completing — the store is used as a shape the dict-backed
        # recorder can't be (`out.append`, a list mutator), or a free var this seed doesn't supply. Keep
        # the channels observed UP TO the failure: dynamic is only the confirming oracle, and the static
        # oracle + the union carry branch-completeness, so a partial observation is sound (never a MISS).
        pass
    return frozenset(out.written)


def _followed_static_writes(tree: ast.AST, store: str, helpers: "dict[str, ast.FunctionDef]",
                            visited: "frozenset[str]") -> "frozenset[str]":
    """The store's write channels that flow THROUGH calls to local helpers, renamed from the callee's
    parameter back to `store` (`o.total` inside `def h(o)` -> `out.total` at a `h(out)` call). Keeps the
    static oracle branch-complete across the call — static sees every arm of a branch INSIDE the callee,
    where the dynamic oracle only sees the arm this input took. Recurses through chained hand-offs."""
    writes: set[str] = set()
    for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
        res = _passed_to_local(call, store, helpers)
        if res is None:
            continue
        h, param = res
        if h.name in visited:
            continue
        # the callee's channels for its parameter — its own direct writes AND anything IT hands on —
        # all in the callee's `param` view, then renamed once to the caller's `store`.
        callee = set(static_writes(ast.unparse(h))) | _followed_static_writes(
            h, param, helpers, visited | {h.name})
        for w in callee:
            base, _, rest = w.partition(".")
            if base == param:
                writes.add(f"{store}.{rest}")
    return frozenset(writes)


# --- the DERIVED footprint: cross-check the two oracles ---------------------------------------------

@dataclass(frozen=True)
class CodeFootprint:
    """A write footprint DERIVED from code: the static and dynamic write-sets, their reconciliation, and
    — crucially — whether the code was **modelable** at all. ``writes`` is the derived footprint, sound to
    consume **only when** ``not unknown``; when ``unknown`` the derivation may have missed a write, so a
    check must REFUSE rather than trust it (the honest-unknown membrane)."""
    static: frozenset[str]
    dynamic: frozenset[str]
    modelable: bool = True

    @property
    def unknown(self) -> bool:
        """The store escaped the subscript model, so the derived ``writes`` may silently miss a write —
        an honest 'I don't know this footprint'. A disjointness check must treat this as *refuse*, never
        certify a composition on a footprint that could be an under-approximation."""
        return not self.modelable

    @property
    def writes(self) -> "frozenset[str]":
        """The sound footprint: the UNION of the two oracles (over-approximation — never miss a real
        write).

        The union is taken WHOLE — in particular an unresolved ``<computed>`` channel SURVIVES a dynamic
        run that named a concrete key. Dropping it (as this once did, to avoid a 'spurious' placeholder)
        was the one under-approximating step in the derivation: the dynamic oracle resolves the key THIS
        input produced, and says nothing about the key another input produces, so a run that observed
        ``out.a`` cannot license the claim that ``out[k]`` never writes ``out.total``. The placeholder is
        a WILDCARD, and a consuming check must treat it as one (`grammapy.disjoint_writes`). Precision is
        recovered where it can be PROVEN instead of observed: a key bound to a literal is resolved
        statically (`_const_bindings`), so it never becomes a placeholder in the first place."""
        return frozenset(set(self.static) | set(self.dynamic))

    @property
    def agree(self) -> bool:
        """The two oracles derived the same channels — a confidence signal (no branch missed, no key
        left unresolved)."""
        return self.static == self.dynamic

    @property
    def dynamic_missed(self) -> "frozenset[str]":
        """Channels static saw that this input's run did not — untaken branches (dynamic's blind spot)."""
        return frozenset(self.static - self.dynamic)

    @property
    def static_unresolved(self) -> "frozenset[str]":
        """Computed keys static could not name (``<store>.<computed>``) — static's blind spot, which the
        dynamic oracle resolves."""
        return frozenset(w for w in self.static if w.endswith(".<computed>"))


@lru_cache(maxsize=None)
def footprint_of(source: str, *, store: str = "out", x: int = 5) -> CodeFootprint:
    """Derive a fragment's write footprint from its CODE — statically and dynamically, cross-checked, and
    flagged ``unknown`` when the store escapes the analyzable model (``modelable`` is False). A caller MUST
    check ``.unknown`` and refuse before trusting ``.writes``. Cached on ``(source, store, x)`` (a
    fragment's code is immutable, so its footprint is a pure function of it)."""
    tree = ast.parse(textwrap.dedent(source))
    helpers = _local_helpers(tree)
    static = static_writes(source) | _followed_static_writes(tree, store, helpers, frozenset())
    return CodeFootprint(static, dynamic_writes(source, store=store, x=x),
                         modelable(source, store=store))
