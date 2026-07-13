"""The §8 EMIT boundary — intake in reverse, productized (docs/critique.md weakness #8).

The five synthesis probes (`experiments/*_synthesis.py`, `codegen_understand`) each re-implemented the
same selection loop: a spec's required features + a candidate library -> the candidates that REALIZE
the spec (provide every required feature) -> CHOOSE the graded-best -> the winner's emit + verify.
This module lifts that shared scaffolding into the package so a synthesis consumer *selects*, rather
than re-deriving the loop — the mirror of how `analyze` owns the hypothesis loop and `semantics.cnl`,
while intake facts are the data.

The split matches intake/analysis exactly:
  * the LOOP (realize -> choose -> trace) and the realization rule bank (`emit.cnl`) live here;
  * the candidate library, the source-emitting templates, and the verification are DATA/domain the
    caller supplies (a `Candidate` carries its own `emit`; the caller derives which features the spec
    requires and how to verify the emitted source).

Built the ugm-vision-aligned way: fact graphs are authored with `load_fact_triples` (interning by
name through the ISA — ugm feedback #8b), not a hand-rolled `ids` cache, so a re-mentioned name never
splits across duplicate nodes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import ugm as h
from ugm import (load_machine_rules, load_fact_triples, ask_goal,
                 set_candidate, choose, explain_choice)

from .intake import intake_function
from .analysis import Outcome, Caveat, analyze_all, caveats


_CNL_PATH = Path(__file__).with_name("emit.cnl")
REALIZATION = _CNL_PATH.read_text(encoding="utf-8")   # the authored realization bank (CNL data)


@dataclass(frozen=True)
class Candidate:
    """One pre-minted candidate the rules SELECT among (a skeleton / recipe / plan / shape). `provides`
    are the features it guarantees, matched against the spec's required features; `fit` grades it for
    CHOOSE (higher = preferred); `emit` turns a spec into real source (the domain's template)."""
    name: str
    provides: frozenset[str]
    fit: float
    emit: "Callable[..., str] | None" = None


@dataclass
class Selection:
    """The result of selecting a realizing candidate: which realized, the graded winner, and the two
    provenance traces (why it realizes, why it beat the alternatives). Emission + verification are the
    caller's — `winner_candidate.emit(...)` then a domain verify."""
    required: set[str]
    realizing: list[str]
    winner: str | None
    winner_candidate: Candidate | None
    choose_trace: list[str] = field(default_factory=list)
    realize_trace: list[str] = field(default_factory=list)


def _facts(spec: str, required: "set[str]", candidates: "list[Candidate]") -> "list[tuple[str, str, str]]":
    """The spec + candidate library + feature vocabulary as `(s, p, o)` name-triples — the one
    direct-authoring boundary (the reverse of intake), loaded through the interning ISA loader."""
    feats = set(required) | {f for c in candidates for f in c.provides}
    facts = [(f, "is_a", "feature") for f in feats]
    facts += [(spec, "requires", f) for f in required]
    for c in candidates:
        facts.append((c.name, "is_a", "candidate"))
        facts += [(c.name, "provides", f) for f in c.provides]
    return facts


def _fact_graph(spec: str, required: "set[str]", candidates: "list[Candidate]") -> "h.Graph":
    g = h.Graph()
    load_fact_triples(g, _facts(spec, required, candidates))   # interns by name (ugm #8b) — no cache
    return g


def realizing(spec: str, required: "set[str]", candidates: "list[Candidate]") -> "list[Candidate]":
    """The candidates that REALIZE the spec — backward-CHAIN `who realizes <spec>` over the shared
    realization bank (a candidate realizes iff it misses no required feature). The mirror of
    `operators.retrieve` / each probe's `retrieve`, now in one place."""
    g = _fact_graph(spec, required, candidates)
    names = {a.split(" ", 1)[0] for a in ask_goal(g, f"who realizes {spec}", load_machine_rules(REALIZATION))}
    return [c for c in candidates if c.name in names]


def realize_trace(spec: str, required: "set[str]", candidates: "list[Candidate]", winner: str) -> "list[str]":
    """RECORD provenance for WHY the winner realizes the spec — the spec->code rationale."""
    g = _fact_graph(spec, required, candidates)
    return ask_goal(g, f"why {winner} realizes {spec}", load_machine_rules(REALIZATION))


def choose_best(candidates: "list[Candidate]") -> "tuple[Candidate | None, list[str]]":
    """Run the public CHOOSE firmware over candidates, graded by `fit`; return the winner + the
    auditable `explain_choice` trace (losers retained)."""
    g = h.Graph()
    goal = g.add_node("emit_goal")
    by_name: "dict[str, Candidate]" = {}
    for c in candidates:
        by_name[c.name] = c
        set_candidate(g, goal, g.add_node(c.name), c.fit)
    winners = choose(g, goal, alpha=0.01)
    return (by_name[g.name(winners[0])] if winners else None), explain_choice(g, goal)


def select(spec: str, required: "set[str]", candidates: "list[Candidate]") -> Selection:
    """The whole selection loop: REALIZE (which candidates provide every required feature) -> CHOOSE
    the graded-best -> RECORD both traces. Emission and verification stay with the caller. This is the
    productized surface a synthesis consumer calls instead of re-deriving realize/choose/rules."""
    cands = realizing(spec, required, candidates)
    winner, choose_tr = choose_best(cands)
    return Selection(
        required=set(required), realizing=sorted(c.name for c in cands),
        winner=winner.name if winner else None, winner_candidate=winner,
        choose_trace=choose_tr,
        realize_trace=realize_trace(spec, required, candidates, winner.name) if winner else [])


def verify_clean(source: str, hypothesis: "dict[str, str]") -> "tuple[list[Outcome], list[Caveat]]":
    """Verify emitted source through the PRODUCTIZED analyzer: `(outcomes, caveats)` under
    `hypothesis`. Empty outcomes AND empty caveats == checked and clear; non-empty caveats == clear
    only on what was modelled (docs/critique.md #5 — surface the silence in synthesis verification
    too, not just repair). The shared 're-intake + analyze the emitted code' the probes hand-rolled."""
    ik = intake_function(source)
    return analyze_all(ik, hypothesis), caveats(ik)
