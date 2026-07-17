"""Feasibility probe — COMPOSE -> CHECK -> RECOVER as a rule-driven, SUPPOSE-scoped loop.

This is the first slice of the "first-principle rules" direction. Rather than SELECTING a whole
pre-authored skeleton and emitting it, this ASSEMBLES a program from small fragments, and — the new
part — when the assembly is UNSOUND it does not crash or silently ship the bug: it reifies the conflict
and lets a **recovery rule** derive the repair, validated hypothetically before it is adopted. Three
things it leans on are only now possible in `../ugm` (see the `ugm-blockers-cleared` finding):

    describe (CNL pattern facts) ─▶ COMPOSE ─▶ CHECK ─┬─ clean ─▶ EMIT + VERIFY (run it)
       provides / writes            pick 1 per         │
                                    required feature    └─ CONFLICT (grammapy disjoint-writes,
                                                              the real frame rule, reified)
                                                              │
                                        RECOVER: a CNL recovery rule PROPOSES swaps off the
                                        reified conflict; each candidate is DISPOSED by SUPPOSE
                                        (entertain the swap, predict the channel is conflict-free,
                                        commit=False so nothing inks) ─▶ re-COMPOSE ─▶ re-CHECK
                                                              │
                                        no disjoint provider ─▶ a NAMED Refusal (the honest gap),
                                                                not a guessed or clobbering program.

The epistemic move is unchanged and is the whole point: the composer PROPOSES, the check + the Pilot
(here: re-execution) DISPOSE. A fragment only *claims* it writes channel C; the conflict is DERIVED
by grammapy's own `disjoint_writes` CNL rule, and the repaired program is trusted only because it is
RUN and observed to be correct — never because the recovery rule says so.

What is genuinely new — a rule-driven recovery, not hand-written repair control flow:

  * the RECOVERY is a RULE over the reified conflict (`_RECOVERY_RULE`), not hand-written control flow
    — the GAP-FILL shape ugm's new `procedures` arc uses at the planning level, applied to fragments;
  * each proposed repair is validated by SUPPOSE (`suppose(commit=False)`) — entertain it, predict the
    formerly-conflicted channel is now clean, drop the scope. Rule proposes, SUPPOSE disposes;
  * the conflict is a genuine EXECUTABLE bug: two fragments that write the same channel are two
    statements assigning the same dict key, so the second silently CLOBBERS the first at runtime — the
    `verify` step RUNS the program and catches exactly that (a missing field), the trust-by-execution
    the safety-only checks could never give.

Run it: `python -m experiments.compose_recover`
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

import ugm as h
from ugm import ask_goal, load_machine_rules, write_rule, suppose, AttrGraph

from grammapy.channels import Footprint, Channel

from pystrider import footprint_of, modelable
from grammapy.combinators import Accumulate, Item, CompositionError


# --- the fragment catalog: PATTERNS described as data (provides a feature, writes a channel) --------

@dataclass(frozen=True)
class Fragment:
    """One assemblable pattern. `provides` is the spec feature it realizes; `stmt` is the real Python
    statement that does it. Its write footprint — the channels it touches — is DERIVED from `stmt` by
    `pystrider.footprint_of` (the `writes` property), NOT declared: the check reasons over what the
    code does, not a hand-written label (the productized footprint-synthesis join)."""
    name: str
    provides: str
    stmt: str                       # e.g. "out['scaled'] = x * 2"

    @property
    def writes(self) -> "frozenset[str]":
        """The write channels DERIVED from `stmt` (static AST + dynamic run, cross-checked)."""
        return footprint_of(self.stmt).writes

    @property
    def unknown(self) -> bool:
        """The fragment's footprint can NOT be soundly derived (its store escapes the subscript model),
        so `writes` might miss a write. Decided statically (`modelable`), without executing the fragment —
        the check REFUSES on this rather than certify a composition on an under-approximation."""
        return not modelable(self.stmt)


CATALOG: tuple[Fragment, ...] = (
    Fragment("scale",    provides="scaled",  stmt="out['scaled'] = x * 2"),
    Fragment("shift_ok", provides="shifted", stmt="out['shifted'] = x + 10"),
    # the copy-paste bug: a `shifted` provider whose CODE writes the wrong channel (out.scaled). Nobody
    # declares this — footprint_of DERIVES `writes={out.scaled}` from the stmt, so composing it with
    # `scale` is caught as a real collision (the declaration can no longer hide the clobber).
    Fragment("shift_bad", provides="shifted", stmt="out['scaled'] = x + 10"),
)

# an UN-MODELABLE provider (kept out of CATALOG so it doesn't perturb the recovery proposals): it writes
# through `out.update(...)`, which bypasses the subscript model, so its footprint can't be soundly derived.
# A composition using it must be REFUSED, never admitted on a footprint that might be missing a write.
SHIFT_OPAQUE = Fragment("shift_opaque", provides="shifted", stmt="out.update({'shifted': x + 10})")


# --- CNL: the pattern catalog + the recovery rule as rules over reified facts -----------------------

# A fragment REALIZES a feature it provides — the pattern-match half (trivial here, but authored as a
# rule so the catalog is data the reasoning reads, not a Python lookup).
_REALIZE_RULE = "?f realizes ?feat when ?f provides ?feat and ?f is_a fragment"

# THE RECOVERY RULE. Read off a REIFIED conflict: any fragment `?alt` SUPERSEDES the blamed fragment
# `?bad` if it provides the same feature. It only PROPOSES (every same-feature alternate); SUPPOSE then
# disposes each candidate by checking the swap is actually conflict-free. Oriented `?alt supersedes
# ?bad` so the alternates are the QUERY SUBJECTS (`who supersedes <bad>`) — the emit.py realize idiom.
_RECOVERY_RULE = (
    "?alt supersedes ?bad when ?bad is_a blamed and ?bad provides ?feat "
    "and ?alt provides ?feat and ?alt is_a fragment and ?alt != ?bad"
)

# grammapy's own frame rule, reused to VALIDATE a repair inside a SUPPOSE scope: a channel is a
# conflict iff two DISTINCT fragments write it (`?a != ?b`, ugm feedback #11).
_CONFLICT_RULE = "?c write_conflict yes when ?a writes ?c and ?b writes ?c and ?a != ?b"


def _fact_graph(facts: list[tuple[str, str, str]]) -> "h.Graph":
    g = h.Graph()
    ids: dict[str, str] = {}
    for s, p, o in facts:
        for nm in (s, o):
            if nm not in ids:
                ids[nm] = g.add_node(nm)
        g.add_relation(ids[s], p, ids[o])
    return g


def _catalog_facts(catalog: tuple[Fragment, ...]) -> list[tuple[str, str, str]]:
    facts: list[tuple[str, str, str]] = []
    for f in catalog:
        facts += [(f.name, "is_a", "fragment"), (f.name, "provides", f.provides)]
        facts += [(f.name, "writes", ch) for ch in f.writes]     # one fact per DERIVED write channel
    return facts


# --- COMPOSE ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Composition:
    """A candidate program: one chosen fragment per required feature, in spec order."""
    fragments: tuple[Fragment, ...]

    def by_feature(self, feat: str) -> "Fragment | None":
        return next((f for f in self.fragments if f.provides == feat), None)

    def replacing(self, old: Fragment, new: Fragment) -> "Composition":
        return Composition(tuple(new if f is old else f for f in self.fragments))


def compose(required: tuple[str, ...], catalog: tuple[Fragment, ...],
            prefer: dict[str, str] | None = None) -> Composition:
    """Pick one realizing fragment per required feature. `prefer` pins a feature to a fragment name
    (used to seed a specific — possibly buggy — draft); otherwise the FIRST realizer wins. Realization
    is a CNL query over the catalog facts (the pattern-match), not a Python filter."""
    prefer = prefer or {}
    g = _fact_graph(_catalog_facts(catalog))
    rules = load_machine_rules(_REALIZE_RULE)
    chosen: list[Fragment] = []
    for feat in required:
        realizers = {a.split(" ", 1)[0] for a in ask_goal(g, f"who realizes {feat}", rules)}
        cands = [f for f in catalog if f.name in realizers]
        pick = next((f for f in cands if f.name == prefer.get(feat)), cands[0] if cands else None)
        if pick is None:
            raise ValueError(f"no fragment realizes required feature {feat!r}")
        chosen.append(pick)
    return Composition(tuple(chosen))


# --- CHECK: grammapy's real Accumulate soundness (disjoint writes) ----------------------------------

def check(comp: Composition) -> list[CompositionError]:
    """Run grammapy's ACCUMULATE check over the composition's footprints. Returns [] if the writes are
    disjoint (composes), else the single `CompositionError` carrying the structured `WriteConflict`s.
    This is the real frame rule — the same CNL disjoint-writes module grammapy ships — not a re-derive."""
    items = [Item(f.name, Footprint.of(writes=[Channel(w) for w in f.writes])) for f in comp.fragments]
    try:
        Accumulate.check(items)
        return []
    except CompositionError as e:
        return [e]


# --- RECOVER: a recovery RULE proposes swaps off the reified conflict; SUPPOSE disposes each ---------

def _rule_graph(text: str) -> AttrGraph:
    rg = AttrGraph()
    for r in load_machine_rules(text):
        write_rule(rg, r)
    return rg


def _swap_is_clean(comp: Composition, bad: Fragment, alt: Fragment, channel: str) -> bool:
    """SUPPOSE the swap `bad -> alt`, then CHECK the formerly-blamed `channel` is no longer a conflict.
    Entertain the repaired composition's DERIVED write facts as assumptions, PREDICT that channel is a
    `write_conflict`; a REFUTED/INCONCLUSIVE verdict (the conflict can NOT be derived) means the swap
    is clean. `commit=False` — the hypothesis inks nothing (feedback #6/#12). Rule proposed, SUPPOSE
    disposes."""
    repaired = comp.replacing(bad, alt)
    facts = [(f.name, "writes", w) for f in repaired.fragments for w in f.writes]   # DERIVED footprints
    g = _fact_graph(facts)
    rg = _rule_graph(_CONFLICT_RULE)
    # predict the (previously) conflicted channel is STILL a conflict; CONFIRMED would mean the swap
    # failed to fix it. Any non-confirmed verdict = the collision is gone.
    res = suppose(g, [], [("write_conflict", channel, "yes")], rules=rg, commit=False)
    return res.status != "confirmed"


@dataclass
class Recovery:
    """The outcome of one recovery attempt: the proposed swaps considered, and the repaired
    composition (or None if no proposed swap disposed clean — a genuine gap)."""
    blamed: str
    proposals: list[str]
    accepted: "tuple[str, str] | None"       # (bad, alt) that SUPPOSE disposed clean
    repaired: "Composition | None"


def recover(comp: Composition, err: CompositionError, catalog: tuple[Fragment, ...]) -> Recovery:
    """Derive a repair from the REIFIED conflict. The right-hand writer of each `WriteConflict` is
    reified as `blamed`; the recovery RULE proposes every same-feature alternate; SUPPOSE disposes each
    until one checks conflict-free. The GAP-FILL shape (ugm procedures) at the fragment level."""
    blamed_name = err.conflicts[0].right                 # the later writer on the shared channel
    blamed_channel = str(err.conflicts[0].channel)       # the channel they collided on (the check's own)
    bad = next(f for f in comp.fragments if f.name == blamed_name)

    # reify the conflict + the catalog, and let the recovery RULE PROPOSE the substitutes (every
    # same-feature alternate — `who supersedes <bad>`). The rule proposes; SUPPOSE disposes below.
    g = _fact_graph(_catalog_facts(catalog) + [(blamed_name, "is_a", "blamed")])
    rules = load_machine_rules(_RECOVERY_RULE)
    proposals = [a.split(" ", 1)[0] for a in ask_goal(g, f"who supersedes {blamed_name}", rules)
                 if a.split(" ", 1)[0] != "(no"]
    by_name = {f.name: f for f in catalog}

    accepted: tuple[str, str] | None = None
    repaired: Composition | None = None
    for alt_name in proposals:
        if _swap_is_clean(comp, bad, by_name[alt_name], blamed_channel):   # SUPPOSE disposes each proposal
            accepted = (bad.name, alt_name)
            repaired = comp.replacing(bad, by_name[alt_name])
            break
    return Recovery(blamed_name, proposals, accepted, repaired)


# --- EMIT + VERIFY (trust by execution) -------------------------------------------------------------

def emit(comp: Composition) -> str:
    """Emit the composition as a real `report(x)` function: init the output, run each fragment's
    statement in order, return it. Straightforward — the fragments carry their own source."""
    body = ["    out = {}"] + [f"    {f.stmt}" for f in comp.fragments] + ["    return out"]
    return "def report(x):\n" + "\n".join(body)


@dataclass
class Verified:
    source: str
    result: dict
    ok: bool
    reason: str


def verify(comp: Composition, required: tuple[str, ...]) -> Verified:
    """RUN the emitted program and check every required feature actually landed a distinct key. A
    clobbering composition (two fragments writing one channel) drops a field — caught HERE, by
    execution, not by claim."""
    source = emit(comp)
    ns: dict = {}
    exec(source, ns)
    result = ns["report"](5)
    missing = [feat for feat in required if feat not in result]
    ok = not missing
    reason = ("all required features present and distinct" if ok
              else f"clobbered: required {list(required)} but ran to {result} (missing {missing})")
    return Verified(source, result, ok, reason)


# --- the loop --------------------------------------------------------------------------------------

@dataclass
class Outcome:
    label: str
    draft: Composition
    steps: list[str] = field(default_factory=list)
    final: "Composition | None" = None
    verified: "Verified | None" = None
    refusal: str = ""

    @property
    def shipped_ok(self) -> bool:
        return self.verified is not None and self.verified.ok


def run(label: str, required: tuple[str, ...], catalog: tuple[Fragment, ...],
        prefer: dict[str, str] | None = None, fuel: int = 3) -> Outcome:
    """compose -> check -> (recover -> re-check)* -> emit + verify, or a named Refusal."""
    comp = compose(required, catalog, prefer)
    out = Outcome(label, comp)
    # REFUSE on unknown: a fragment whose footprint can't be soundly derived can't be certified disjoint.
    # Never admit on a possible under-approximation — the honest-unknown membrane, decided before the check.
    unknown = [f.name for f in comp.fragments if f.unknown]
    if unknown:
        out.refusal = (f"cannot derive a sound footprint for {unknown} — the store escapes the analyzable "
                       f"model, so the disjointness check REFUSES rather than certify on a possible "
                       f"under-approximation. Provide these features on plain subscript writes.")
        out.steps.append(f"CHECK abstains: {unknown} unmodelable -> Refusal (never admit on unknown)")
        return out
    for _ in range(fuel):
        errs = check(comp)
        if not errs:
            out.final = comp
            out.verified = verify(comp, required)
            out.steps.append(f"CHECK clean -> emit + verify: {out.verified.reason}")
            return out
        err = errs[0]
        wc = err.conflicts[0]
        out.steps.append(f"CHECK conflict: {wc}")
        rec = recover(comp, err, catalog)
        if rec.repaired is None:
            out.refusal = (f"no disjoint provider of {rec.blamed!r}'s feature — proposals "
                           f"{rec.proposals or '{}'} all still collide. Add a fragment that provides "
                           f"it on a distinct channel.")
            out.steps.append(f"RECOVER failed -> Refusal: {out.refusal}")
            return out
        bad, alt = rec.accepted
        out.steps.append(f"RECOVER (rule proposed {rec.proposals}; SUPPOSE disposed) -> swap {bad} -> {alt}")
        comp = rec.repaired
    out.refusal = "recovery fuel exhausted"
    return out


def _show(out: Outcome) -> None:
    print(f"  [{out.label}]  draft = {[f.name for f in out.draft.fragments]}")
    for s in out.steps:
        print(f"     {s}")
    if out.final is not None:
        print(f"     => shipped {[f.name for f in out.final.fragments]}  ran report(5)={out.verified.result}")
    print(f"     => trustworthy program shipped: {out.shipped_ok}\n")


def main() -> None:
    print("COMPOSE -> CHECK -> RECOVER — assembling a program from fragments, gated by grammapy's")
    print("disjoint-writes rule, repaired by a recovery RULE, each repair disposed by SUPPOSE, and")
    print("the winner TRUSTED ONLY BECAUSE IT RUNS CORRECTLY.\n")
    required = ("scaled", "shifted")

    print("PART 1 — a SOUND draft (scale + shift_ok): disjoint writes, ships on the first check\n")
    _show(run("sound", required, CATALOG, prefer={"shifted": "shift_ok"}))

    print("PART 2 — a BUGGY draft (scale + shift_bad, both write out.scaled): the conflict is a real")
    print("clobber; caught by CHECK, repaired by the recovery rule, verified by re-execution\n")
    _show(run("buggy->recovered", required, CATALOG, prefer={"shifted": "shift_bad"}))

    print("PART 3 — an UNRECOVERABLE draft: strip the good provider from the catalog, so the recovery")
    print("rule can propose nothing disjoint -> a NAMED refusal, never a clobbering program\n")
    thin = tuple(f for f in CATALOG if f.name != "shift_ok")
    _show(run("unrecoverable", required, thin, prefer={"shifted": "shift_bad"}))

    print("PART 4 — an UN-MODELABLE fragment (shift_opaque writes via out.update): its footprint can't be")
    print("soundly derived, so the check REFUSES rather than admit on a possible under-approximation\n")
    _show(run("unmodelable", required, (CATALOG[0], SHIFT_OPAQUE)))

    print("The composer proposes, grammapy's frame rule + re-execution dispose. A rejected composition")
    print("is repaired by a RULE reading the reified conflict (validated hypothetically by SUPPOSE), or")
    print("refused with a named gap. Unsound assembly never ships; the shipped program is RUN correct.")


if __name__ == "__main__":
    main()
