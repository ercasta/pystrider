"""Feature-interaction SCALING — the §8 "the LOC model understates the win" bullet, made concrete.

The economic limit-test (`economic_test.py`) closed on a claim it only ARGUED: hand-code must manage a
combinatorial feature-interaction surface while a CNL spec grows linearly and grammapy *checks* the
interactions. That argument is the whole case that the approach pays at SCALE (and only at scale — a one-off
app reads as a loss). An argued claim is a debt; this probe pays it, on grammapy's REAL `Accumulate` frame
rule (the same disjoint-writes check `compose_recover.py` uses) and by actually RUNNING the emitted programs.

The measured ledger, as a feature library grows to F features:

    author effort         O(F)     one bundle per feature — you write the feature, not its interactions
    interaction surface   O(F^2)   every pair that could touch a shared slot must be audited for a clobber
    who pays the O(F^2)   the CHECK, automatically, in one pass over the chosen composition — NOT the author

That is the win the LOC count misses: the author's ledger stays linear because grammapy bears the quadratic
interaction-audit for free. The probe makes it non-hand-wavy three ways: (1) it prints the diverging ledger;
(2) at scale it injects a genuine collision and shows `Accumulate` CATCHES it structurally, no matter how big
F is, while the author wrote zero interaction code; (3) it RUNS the naive additive program (just concatenate
the features) and shows it silently CLOBBERS a slot — the exact bug hand-additive code ships.

The honest boundary (red-team discipline): the disjoint-writes check catches RESOURCE collisions (two
features writing one slot). A SEMANTIC interaction — two features on disjoint slots that are jointly
incoherent — is invisible to it, and is caught by the OTHER automatic layer, driven execution (the playground
already drives every emitted app through Pilot). Two automatic layers, a named boundary between them; neither
is an author-enumerated combination table.

Run it: `python -m experiments.interaction_scaling`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import comb

from grammapy.channels import Footprint, Channel
from grammapy.combinators import Accumulate, Item, CompositionError


@dataclass(frozen=True)
class Feature:
    """One composable feature bundle. `writes` are the screen slots it fills (its footprint); `stmt` is
    the real statement that fills them, so a collision is an EXECUTABLE clobber, not just a label clash.
    `incompatible_with` is an optional SEMANTIC constraint (disjoint slots, still jointly incoherent)."""
    name: str
    writes: "tuple[str, ...]"
    stmt: str
    incompatible_with: "frozenset[str]" = frozenset()


def feature(i: int) -> Feature:
    """The i-th independent feature in a growing library: it fills its own private slot. A well-designed
    bundle library is mostly like this — each feature disjoint — which is exactly why the interactions
    that DO exist are the needles a linear-effort author cannot afford to hunt by hand."""
    slot = f"slot_{i}"
    return Feature(f"feat_{i}", (slot,), f"screen['{slot}'] = 'feat_{i}'")


def library(f: int) -> "tuple[Feature, ...]":
    return tuple(feature(i) for i in range(f))


# --- CHECK: grammapy's real Accumulate (disjoint writes) over the composition ----------------------

def collisions(features: "tuple[Feature, ...]") -> "list":
    """Run grammapy's ACCUMULATE check over the features' footprints. Returns the structured
    `WriteConflict`s (empty if the writes are disjoint). One pass over the WHOLE composition — the author
    never enumerates the pairs; the frame rule finds any shared-slot clobber itself."""
    items = [Item(x.name, Footprint.of(writes=[Channel(w) for w in x.writes])) for x in features]
    try:
        Accumulate.check(items)
        return []
    except CompositionError as e:
        return list(e.conflicts)


# --- EMIT + RUN: the naive additive program, to catch the real clobber by execution ----------------

def additive_run(features: "tuple[Feature, ...]") -> dict:
    """Emit the hand-additive program — init a screen, run each feature's statement in order — and RUN it.
    Two features writing one slot means the second assignment silently overwrites the first: a dropped
    feature, observable only by running. This is what additive hand-code ships when the audit is skipped."""
    body = ["    screen = {}"] + [f"    {x.stmt}" for x in features] + ["    return screen"]
    ns: dict = {}
    exec("def build():\n" + "\n".join(body), ns)
    return ns["build"]()


def additive_dropped(features: "tuple[Feature, ...]") -> "set[str]":
    """Which slots the additive program DROPPED — a feature wrote it but it did not survive to the output
    (clobbered by a later writer). The runtime symptom of an unaudited interaction."""
    ran = additive_run(features)
    wrote = {w for x in features for w in x.writes}
    return {slot for slot in wrote if slot not in ran} | {
        slot for slot in wrote if sum(slot in x.writes for x in features) > 1 and slot in ran
        and ran[slot] != next(x.name for x in features if slot in x.writes)
    }


# --- the honest boundary: a SEMANTIC interaction the disjoint-writes check cannot see --------------

def semantic_conflicts(features: "tuple[Feature, ...]") -> "list[tuple[str, str]]":
    """Pairs that are jointly incoherent despite writing DISJOINT slots — invisible to Accumulate, which
    only sees resource collisions. Caught by the other automatic layer (driven execution). Named here so
    the structural check's boundary is explicit, not implied."""
    names = {x.name for x in features}
    out: "list[tuple[str, str]]" = []
    for x in features:
        for other in sorted(x.incompatible_with & names):
            if (other, x.name) not in out:
                out.append((x.name, other))
    return out


# --- the ledger --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Ledger:
    f: int
    author_lines: int          # O(F): one bundle per feature
    audit_pairs: int           # O(F^2): pairs a hand-coder must check for a shared-slot clobber


def ledger(f: int) -> Ledger:
    return Ledger(f, author_lines=f, audit_pairs=comb(f, 2))


def main() -> None:
    print("FEATURE-INTERACTION SCALING — author effort is linear; the interaction-audit is quadratic and")
    print("borne by grammapy's frame rule, not the author. The §8 'understates the win' bullet, demonstrated.\n")

    # -----------------------------------------------------------------------------------------------
    print("PART 1 — the diverging ledger as the feature library grows:\n")
    print(f"      {'features F':>10} {'author lines':>13} {'interaction pairs':>18} {'ratio pairs/lines':>18}")
    print(f"      {'-'*10} {'-'*13} {'-'*18} {'-'*18}")
    for f in (2, 4, 8, 16, 32, 64):
        L = ledger(f)
        print(f"      {L.f:>10} {L.author_lines:>13} {L.audit_pairs:>18} {L.audit_pairs / L.author_lines:>17.1f}x")
    print("\n  The author writes O(F) bundles. The interactions that could clobber grow as O(F^2). If the author")
    print("  had to audit them by hand, effort would go quadratic; the whole point is they do NOT — see PART 2.\n")

    # -----------------------------------------------------------------------------------------------
    print("PART 2 — at SCALE, a real collision: the check catches it in one pass; additive code ships it.\n")
    for f in (8, 32):
        base = library(f)
        # inject the F-th feature as an adversarial collider: it fills slot_0, already owned by feat_0.
        collider = Feature(f"feat_{f}_collides", ("slot_0",), "screen['slot_0'] = 'INTRUDER'")
        composed = base + (collider,)

        cs = collisions(composed)                       # grammapy Accumulate — one pass over all F+1
        dropped = additive_dropped(composed)            # RUN the naive additive program
        print(f"  F={f}: library of {f} disjoint features + 1 collider on slot_0")
        print(f"     grammapy Accumulate  -> {len(cs)} conflict(s) CAUGHT structurally: "
              f"{[f'{c.left} vs {c.right} on {c.channel}' for c in cs]}")
        print(f"     naive additive RUN   -> slot(s) silently CLOBBERED at runtime: {sorted(dropped)}")
        print(f"     (author wrote 0 interaction code; the check audited all {comb(f + 1, 2)} pairs itself)\n")

    # -----------------------------------------------------------------------------------------------
    print("PART 3 — the honest BOUNDARY: a SEMANTIC interaction on DISJOINT slots (invisible to the check).\n")
    guest = Feature("guest_checkout", ("slot_guest",), "screen['slot_guest'] = 'guest'",
                    incompatible_with=frozenset({"loyalty_account"}))
    loyalty = Feature("loyalty_account", ("slot_loyalty",), "screen['slot_loyalty'] = 'account'")
    pair = (guest, loyalty)
    print(f"      features: {[x.name for x in pair]}  (slots {[x.writes[0] for x in pair]} — DISJOINT)")
    print(f"      grammapy Accumulate  -> {len(collisions(pair))} resource conflict(s) (clean: disjoint writes)")
    print(f"      semantic layer       -> jointly-incoherent pair(s): {semantic_conflicts(pair)}")
    print("      The disjoint-writes check is blind here BY DESIGN — it audits RESOURCE collisions, not")
    print("      behavior. Behavioral interactions are caught by the OTHER automatic layer, driven execution")
    print("      (the playground drives every emitted app through Pilot). Two automatic layers; named seam.\n")

    print("READING: as features scale, the author's ledger stays LINEAR (one bundle each) while the")
    print("interaction-audit surface grows QUADRATICALLY — and grammapy's frame rule pays that quadratic")
    print("automatically, catching a real clobber that additive hand-code ships. That is precisely the win a")
    print("LOC count misses. The structural check's boundary (resource-collision, not semantics) is named, and")
    print("the semantic residual falls to the second automatic layer — driven execution — not to the author.")


if __name__ == "__main__":
    main()
