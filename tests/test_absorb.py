"""Pins for the API absorber (`pystrider.absorb`) — API absorption Track A, slice 3.

Slice 2 (`experiments/api_absorption.py`) proved a hand-authored `returns_optional` fact flows through
the None-deref semantics. These pins hold the tool that GENERATES that bank from a real declared surface:
it reads only declared type hints (never runs library code), classifies Optional-ness conservatively
(undecidable returns are OMITTED, not guessed), and its generated facts drive the SAME deref effect —
including on a real installed library (textual), so "absorb a library" is dependency-free and real.
"""
from typing import Optional, Generator, Any

import pytest

from pystrider import absorb, absorb_class, FactBank
from experiments.api_absorption import analyze_with_absorption


# --- a representative annotated surface (the general mechanism, independent of any real library) ---

class _Item: ...


class _Repo:
    def find(self, k) -> "Optional[_Item]": ...      # Optional[X]        -> yes
    def lookup(self, k) -> "_Item | None": ...        # PEP-604 X | None   -> yes
    def load(self, k) -> _Item: ...                   # concrete non-None  -> no
    def name(self) -> str: ...                        # concrete non-None  -> no
    def close(self) -> None: ...                      # bare None return   -> yes (deref-unsafe)
    def stream(self) -> "Generator[None, None, None]": ...   # generic w/ None, NOT a union -> no
    def raw(self, k): ...                             # no annotation      -> OMITTED
    def dynamic(self, k) -> Any: ...                  # Any                -> OMITTED
    def _internal(self): ...                          # private            -> excluded entirely


def _opt(bank: FactBank, key: str) -> str | None:
    return next((o for (s, p, o) in bank.facts if s == key and p == "returns_optional"), None)


def test_optional_returns_are_classified_yes():
    bank = absorb(_Repo)
    assert _opt(bank, "_Repo.find") == "yes"          # Optional[X]
    assert _opt(bank, "_Repo.lookup") == "yes"        # X | None
    assert _opt(bank, "_Repo.close") == "yes"         # -> None is deref-unsafe (a fortiori optional)
    assert bank.optional_methods == {"_Repo.find", "_Repo.lookup", "_Repo.close"}


def test_non_optional_returns_are_classified_no():
    bank = absorb(_Repo)
    assert _opt(bank, "_Repo.load") == "no"
    assert _opt(bank, "_Repo.name") == "no"


def test_a_generic_carrying_none_is_not_mistaken_for_optional():
    # Generator[None, None, None] has NoneType in its args but is NOT a union -> not optional.
    assert _opt(absorb(_Repo), "_Repo.stream") == "no"


def test_undecidable_returns_are_omitted_not_guessed():
    # a missing annotation and `Any` are UNDECIDABLE -> no returns_optional fact, surfaced in `omitted`.
    bank = absorb(_Repo)
    assert _opt(bank, "_Repo.raw") is None and _opt(bank, "_Repo.dynamic") is None
    assert set(bank.omitted) == {"_Repo.raw", "_Repo.dynamic"}


def test_has_method_covers_every_public_method_and_excludes_private():
    bank = absorb(_Repo)
    methods = {o for (s, p, o) in bank.facts if p == "has_method"}
    assert methods == {"find", "lookup", "load", "name", "close", "stream", "raw", "dynamic"}
    assert "_internal" not in methods                 # the private surface is not absorbed


def test_bank_records_a_version_for_cache_invalidation():
    bank = absorb(_Repo)
    assert isinstance(bank.version, str) and bank.version    # keyed so a bump re-absorbs (design §6)


# --- the absorbed bank drives the SAME None-deref effect (integration with slice 2) --------------

def test_a_generated_optional_fact_drives_the_deref():
    bank = absorb(_Repo)
    # deref of an absorbed-OPTIONAL method's result raises, via the UNCHANGED semantics + generated fact.
    src = "def f(r, k):\n    x = r.find(k)\n    return x.rows\n"
    assert analyze_with_absorption(src, {"r": "_Repo"}, bank.facts) == ["x.rows"]


def test_a_generated_non_optional_fact_does_not_false_positive():
    bank = absorb(_Repo)
    src = "def g(r, k):\n    x = r.load(k)\n    return x.rows\n"
    assert analyze_with_absorption(src, {"r": "_Repo"}, bank.facts) == []      # load is not optional
    # and an unknown receiver type never resolves -> conservative, no phantom None.
    opt = "def f(r, k):\n    x = r.find(k)\n    return x.rows\n"
    assert analyze_with_absorption(opt, {}, bank.facts) == []


# --- a REAL installed library, live-absorbed (dependency-free: textual is already required) --------

def test_absorbing_a_real_library_yields_real_optional_facts():
    from textual.widget import Widget
    bank = absorb(Widget)
    # real Optional-returning methods on a real annotated class (textual ships inline annotations).
    assert "Widget.check_action" in bank.optional_methods    # -> bool | None
    assert "Widget.get_selection" in bank.optional_methods   # -> tuple[str, str] | None
    # invariants: every optional key is a known method, and omitted keys carry NO returns_optional fact.
    has_method_keys = {s for (s, p, o) in bank.facts if p == "has_method"}
    assert bank.optional_methods <= has_method_keys
    assert all(_opt(bank, k) is None for k in bank.omitted)


def test_absorb_rejects_a_non_class_non_module():
    with pytest.raises(TypeError):
        absorb(42)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
