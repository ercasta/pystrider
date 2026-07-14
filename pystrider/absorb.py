"""The API absorber — reflect a library's DECLARED surface into matchable facts (Track A, slice 3).

`docs/api_absorption_design.md` §3, §5 phase 3. Slice 2 (`experiments/api_absorption.py`) proved that
an absorbed `dict.get returns_optional yes` fact flows through pystrider's UNCHANGED None-deref
semantics — but that fact bank was hand-authored. This tool GENERATES it from a real module's declared
type surface, so analysing a library is a matter of absorbing facts, not authoring per-library rules.

The absorber is a §8 boundary run at the TYPE level (the mirror of intake, which reflects Python *text*
into facts): it reads only DECLARED type hints via `typing.get_type_hints` and NEVER runs library code
paths. For each public method it emits:

    <Type>.<method>   has_method        <method>          # member presence (feeds a method_not_found effect)
    <Type>.<method>   returns_optional  yes | no          # decidably Optional[X] / X | None  ->  yes

and it is CONSERVATIVE by construction (design §6): a return annotation that is `Any`, absent, or
unresolvable is OMITTED (surfaced in `FactBank.omitted`, never guessed) — a wrong absorbed fact is worse
than an absent one. Facts key on the SHORT class name (`Widget.check_action`), matching the resolution
tool's `<receiver-type>.<method>` output; the bank carries the library `version` so a bump re-absorbs
(the same cache-invalidation shape as the rule-bank cache).

Source (design §3, richest first): this slice uses **live introspection** (`typing.get_type_hints` on
an installed, annotated module) — which works for pure-Python annotated libraries (textual, attrs, …).
Builtins and the stdlib carry their Optional-ness only in typeshed `.pyi` stubs, not live annotations
(`dict.get` has no readable return hint); a stub-parsing source is the named follow-on (design §3.1).
"""
from __future__ import annotations

import inspect
import types
import typing
from dataclasses import dataclass, field
from platform import python_version

_NoneType = type(None)


def _is_union(annotation: object) -> bool:
    """True for a `typing.Union[...]` or a PEP-604 `X | Y` annotation — the only shape Optional lives in."""
    origin = typing.get_origin(annotation)
    return origin is typing.Union or origin is getattr(types, "UnionType", ())


def _optionality(annotation: object) -> str | None:
    """Classify a resolved return annotation: 'yes' (may be / is None — Optional[X], X | None, or a bare
    None return), 'no' (a decidable non-None concrete type), or None == UNDECIDABLE (`Any`) so the caller
    OMITS the fact. This is the whole conservatism guarantee: only a decided annotation yields a fact.

    NB a `Union`/`Generator` distinction matters — `Generator[None, None, None]` carries `NoneType` in
    its args but is NOT a union, so it is correctly non-optional (a generator, not a maybe-None value)."""
    if annotation is _NoneType:
        return "yes"                                   # always None -> deref-ing it always raises (a fortiori)
    if annotation is typing.Any:
        return None                                    # undecidable -> omit (no false fact)
    if _is_union(annotation):
        return "yes" if _NoneType in typing.get_args(annotation) else "no"
    return "no"                                        # a concrete, non-union, non-None type


def _return_annotation(fn: object) -> object:
    """The resolved `return` type hint of `fn`, or `_MISSING` when absent/unresolvable (forward refs that
    don't resolve, C builtins with no hints). Never raises — an unreadable hint is an omission, not a crash."""
    try:
        hints = typing.get_type_hints(fn)
    except Exception:
        return _MISSING
    return hints.get("return", _MISSING)


_MISSING = object()


@dataclass
class FactBank:
    """The absorbed surface of one type or module: the generated `facts` (ready for `_kb_from`), the
    library `version` they were read at, and `omitted` — the public methods whose return type was
    UNDECIDABLE, so no `returns_optional` fact was emitted. `omitted` is the caveat discipline made
    first-class: the absence of a fact is surfaced, never silently equated with 'not optional'."""
    qual: str
    version: str
    facts: list[tuple[str, str, str]] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)

    @property
    def optional_methods(self) -> set[str]:
        """The `<Type>.<method>` keys absorbed as Optional-returning — the may-None API vocabulary."""
        return {s for (s, p, o) in self.facts if p == "returns_optional" and o == "yes"}

    def summary(self) -> str:
        opt = len(self.optional_methods)
        meth = sum(1 for (_s, p, _o) in self.facts if p == "has_method")
        return (f"{self.qual} @ {self.version}: {meth} public method(s), {opt} optional-returning, "
                f"{len(self.omitted)} omitted (undecidable return)")


def _version_of(target: object) -> str:
    """The library version to key the bank on: the module's `__version__` if declared, else the running
    interpreter version (the honest fallback for the stdlib, which has no per-module version)."""
    module = inspect.getmodule(target)
    return getattr(module, "__version__", None) or f"python-{python_version()}"


def absorb_class(cls: type, *, version: str | None = None) -> FactBank:
    """Absorb one class's public method surface into a `FactBank`. Reads declared return hints only —
    never runs the class's code. Emits `has_method` for every public method and `returns_optional`
    for every method whose return type is DECIDABLY optional-or-not; undecidable returns are omitted."""
    qual = cls.__name__
    version = version or _version_of(cls)
    bank = FactBank(qual=qual, version=version)
    for name, fn in inspect.getmembers(cls, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue                                   # the PUBLIC declared surface only
        key = f"{qual}.{name}"
        bank.facts.append((key, "has_method", name))
        ann = _return_annotation(fn)
        opt = None if ann is _MISSING else _optionality(ann)
        if opt is None:
            bank.omitted.append(key)                   # surfaced, not guessed (design §6)
        else:
            bank.facts.append((key, "returns_optional", opt))
    return bank


def absorb(target: object, *, version: str | None = None) -> FactBank:
    """Absorb a class OR a module. A module absorbs every class DEFINED in it (not re-exported imports),
    merging their surfaces into one bank keyed on the module name + version. The reverse-intake boundary:
    `absorb(module) -> facts`, cached per version, reading declared types only (design §3)."""
    if inspect.isclass(target):
        return absorb_class(target, version=version)
    if inspect.ismodule(target):
        version = version or _version_of(target)
        merged = FactBank(qual=target.__name__, version=version)
        for _name, cls in inspect.getmembers(target, inspect.isclass):
            if inspect.getmodule(cls) is not target:
                continue                               # only classes DEFINED here, not imported surface
            sub = absorb_class(cls, version=version)
            merged.facts.extend(sub.facts)
            merged.omitted.extend(sub.omitted)
        return merged
    raise TypeError(f"absorb expects a class or module, got {type(target).__name__}")
