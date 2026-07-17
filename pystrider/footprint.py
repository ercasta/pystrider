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

def _target_channel(t: ast.expr) -> "str | None":
    """The channel a single assignment target writes. ``out['k'] = …`` -> ``out.k``; a computed key
    ``out[expr] = …`` -> ``out.<computed>`` (static cannot resolve it); a bare name is a local, not a
    shared channel, so it is not a footprint write."""
    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
        key = t.slice
        if isinstance(key, ast.Constant):
            return f"{t.value.id}.{key.value}"
        return f"{t.value.id}.<computed>"
    return None


def static_writes(source: str) -> "frozenset[str]":
    """Scan the AST for every channel written on ANY path (both arms of a branch), across all
    assignment targets (including tuple/list unpacking and augmented assignment). Branch-complete; a
    computed key stays unresolved as ``<store>.<computed>``."""
    tree = ast.parse(textwrap.dedent(source))
    writes: set[str] = set()
    for node in ast.walk(tree):
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AugAssign) else [])
        for t in targets:
            for leaf in (t.elts if isinstance(t, (ast.Tuple, ast.List)) else [t]):
                ch = _target_channel(leaf)
                if ch:
                    writes.add(ch)
    return frozenset(writes)


# --- ABSTENTION: when can this even be modelled? (know when you don't know) -------------------------

def _subscript_base(node: ast.expr) -> ast.expr:
    """Peel `store[a][b]…` down to its base expression (`store`)."""
    while isinstance(node, ast.Subscript):
        node = node.value
    return node


def modelable(source: str, *, store: str = "out") -> bool:
    """Statically decide whether `footprint_of` can SOUNDLY derive this fragment's write footprint. The
    static/dynamic oracles only capture writes made by **subscripting the store directly** (``store[k] =
    …``). The moment the store is reached any other way, its writes escape that model and a derived
    footprint may silently MISS one — so the honest answer is *unknown*, not a confident under-approx.

    Concretely, the fragment is modelable **iff every reference to the store is the object of a
    subscript** (``store[...]``). Any other reference is a store-escape and abstains:

      * a method call on it            ``store.update(...)`` / ``store.setdefault(...)`` (bypasses ``__setitem__``)
      * an operator-mutation           ``store |= {...}``                      (an aug-assign to the bare name)
      * the store passed to a callee   ``h(store)``                            (writes happen out of view)
      * the store aliased              ``d = store`` / ``box = [store]``        (writes through the alias are unseen)
      * a chained subscript on it      ``store[a][b] = …``                     (writes through the inner object)

    This is a **sound over-refusal**, an enumerated boundary (not a full alias analysis): it never blesses
    a construct it cannot see through, and hands off — the membrane where the core says 'I don't know'."""
    tree = ast.parse(textwrap.dedent(source))
    # Name nodes that sit in a SAFE position: the immediate object of a subscript, `store[...]`.
    safe: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                safe.add(id(node.value))
            else:                                            # a chained subscript — `store[a][b]` writes
                base = _subscript_base(node.value)           # through the inner object, out of the model
                if isinstance(base, ast.Name) and base.id == store:
                    return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == store and id(node) not in safe:
            return False                                     # a store reference that is not `store[...]`
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
    exec(compile(textwrap.dedent(source), "<fragment>", "exec"), {}, {store: out, "x": x})
    return frozenset(out.written)


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
        write). A ``<computed>`` static placeholder is dropped once the dynamic run named a concrete key,
        so a resolved computed write does not leave a spurious unresolved channel behind."""
        union = set(self.static) | set(self.dynamic)
        if self.static_unresolved and self.dynamic:
            union = {w for w in union if not w.endswith(".<computed>")} | set(self.dynamic)
        return frozenset(union)

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
    return CodeFootprint(static_writes(source), dynamic_writes(source, store=store, x=x),
                         modelable(source, store=store))
