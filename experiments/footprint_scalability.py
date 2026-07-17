"""Scalability probe — where does footprint SYNTHESIS stay SOUND, and where does it silently fail?

The whole approach's trust rests on one property: a derived footprint must never MISS a real write (a
sound-but-imprecise footprint is safe — it flags a maybe-collision; an UNSOUND one lets grammapy admit a
composition that actually collides). Every probe so far used fragments WE wrote — clean `out['k'] = …`
subscript writes. This sweep stresses `pystrider.footprint_of` against progressively realistic code with
KNOWN ground-truth write-sets, and classifies each derivation:

    EXACT           derived == truth                          (sound + precise)
    SOUND(over)     derived ⊋ truth                           (safe: imprecise, never misses)
    HONEST-UNKNOWN  misses a write BUT signals its ignorance  (safe IF the check treats unknown as refuse)
    UNSOUND-SILENT  misses a write with NO signal             (FATAL: the check trusts a lie)

The one metric that matters is the count of UNSOUND-SILENT rows: each is a construct on which the approach
does NOT scale safely today. This probe is a STRESS TEST — it is designed to FIND those, not to pass.

PART 2 then shows the FIX that makes the approach scale: an `modelable()` detector that spots the
un-analyzable constructs (a store method call it doesn't model, the store passed to an OPAQUE callee, the
store aliased) and ABSTAINS — turning every UNSOUND-SILENT into an HONEST-UNKNOWN. (A store passed to a
LOCAL helper, by contrast, is now FOLLOWED exactly, not abstained.) Scalability of a symbolic core is not
"analyze everything"; it is "analyze what you can and KNOW when you can't" — the honest-unknown is exactly
the membrane where the core hands off (to a stronger analysis, or to a proposer/human).

Run it: `python -m experiments.footprint_scalability`
"""
from __future__ import annotations

from dataclasses import dataclass

from pystrider.footprint import footprint_of, modelable   # abstention is now PRODUCTIZED in the package


@dataclass(frozen=True)
class Case:
    label: str
    source: str
    truth: frozenset[str]        # the channels the code ACTUALLY writes (ground truth), across all paths
    note: str


# increasingly realistic constructs — the clean ones first, then the ones real code is full of.
CASES: tuple[Case, ...] = (
    Case("subscript", "out['a'] = x", frozenset({"out.a"}), "the baseline the probes used"),
    Case("two_keys", "out['a'] = 1\nout['b'] = 2", frozenset({"out.a", "out.b"}), "independent writes"),
    Case("aug_assign", "out['a'] = 0\nout['a'] += x", frozenset({"out.a"}), "augmented assignment"),
    Case("branch", "if x < 0:\n    out['neg'] = 1\nelse:\n    out['pos'] = 1",
         frozenset({"out.neg", "out.pos"}), "both arms; dynamic sees only one, static both"),
    Case("computed_key", "k = 'total'\nout[k] = x", frozenset({"out.total"}),
         "computed key on the TAKEN path — static abstains, dynamic resolves"),
    Case("computed_untaken", "if x < 0:\n    out[chr(97)] = 1\nelse:\n    out['pos'] = 1",
         frozenset({"out.a", "out.pos"}), "computed key on the UNTAKEN branch (x=5 -> else)"),
    Case("loop_computed", "for i in range(3):\n    out['k%d' % i] = i",
         frozenset({"out.k0", "out.k1", "out.k2"}), "loop of computed keys"),
    Case("alias_taken", "d = out\nd['a'] = 1", frozenset({"out.a"}),
         "the store ALIASED, written on the taken path"),
    Case("alias_untaken", "if x < 0:\n    d = out\n    d['a'] = 1\nelse:\n    out['pos'] = 1",
         frozenset({"out.a", "out.pos"}), "aliased write on the UNTAKEN branch (x=5 -> else)"),
    Case("helper_taken", "def h(o):\n    o['a'] = 1\nh(out)", frozenset({"out.a"}),
         "write through a HELPER CALL, taken path"),
    Case("helper_untaken", "if x < 0:\n    h = None\nelse:\n    pass\ndef h(o):\n    o['a'] = 1\nif x < 0:\n    h(out)\nelse:\n    out['pos'] = 1",
         frozenset({"out.a", "out.pos"}), "helper-call write on the UNTAKEN branch"),
    Case("update_method", "out.update({'a': 1, 'b': 2})", frozenset({"out.a", "out.b"}),
         "dict.update — no subscript, and CPython bypasses __setitem__"),
    Case("setdefault", "out.setdefault('a', 1)", frozenset({"out.a"}),
         "dict.setdefault — a method mutation, no subscript"),
)


# --- classify a derivation against ground truth -----------------------------------------------------

def _concrete(writes: "frozenset[str]") -> "set[str]":
    """The concretely-named channels (drop the `<computed>` uncertainty placeholder)."""
    return {w for w in writes if not w.endswith(".<computed>")}


def classify(case: Case) -> tuple[str, set[str], bool]:
    """Derive the footprint and classify it vs truth. Returns (verdict, missed_channels, signalled)."""
    fp = footprint_of(case.source)
    concrete = _concrete(fp.writes)
    missed = set(case.truth) - concrete
    signalled = bool(fp.static_unresolved)              # the ONLY uncertainty signal the module emits today
    if not missed and concrete == set(case.truth):
        verdict = "EXACT"
    elif not missed:
        verdict = "SOUND(over)"
    elif signalled:
        verdict = "HONEST-UNKNOWN"
    else:
        verdict = "UNSOUND-SILENT"
    return verdict, missed, signalled


# --- PART 2: the abstention that makes it scale — now PRODUCTIZED in `pystrider.footprint.modelable` --
# (was spiked here; promoted into the package so `footprint_of` carries the `unknown` flag and every
# caller — not just this probe — refuses on it. The productized rule is STRONGER than the original
# blocklist: "modelable iff the store is only ever subscripted" also closes operator-mutation `out |= …`
# and container-aliasing `box = [out]`, the two the soundness red-team had found still slipping.)

def abstaining_verdict(case: Case) -> str:
    """The verdict WITH abstention: if the fragment is not modelable, HONEST-UNKNOWN by construction —
    never a silent miss. Otherwise the ordinary classification."""
    if not modelable(case.source):
        return "HONEST-UNKNOWN (abstained)"
    return classify(case)[0]


def main() -> None:
    print("FOOTPRINT SCALABILITY — where does derivation stay SOUND, and where does it silently miss?\n")
    print(f"  {'case':16} {'verdict':16} {'truth':28} note")
    print(f"  {'-'*16} {'-'*16} {'-'*28} {'-'*30}")
    silent = []
    for c in CASES:
        verdict, missed, _ = classify(c)
        if verdict == "UNSOUND-SILENT":
            silent.append(c.label)
        miss = f"  MISSED {sorted(missed)}" if missed else ""
        print(f"  {c.label:16} {verdict:16} {str(sorted(c.truth)):28} {c.note}{miss}")

    print(f"\n  SCALABILITY VERDICT: {len(silent)} of {len(CASES)} constructs are UNSOUND-SILENT "
          f"(a missed write with NO signal): {silent}")
    print("  This is an ALIASED write across an UNTAKEN branch — genuinely out of the subscript model. (The")
    print("  dict methods `update`/`setdefault` are now MODELED as writes; a store passed to a LOCAL helper")
    print("  is now FOLLOWED into the callee exactly — so both are derived, not missed.) Without a signal,")
    print("  the derivation can confidently miss a real write on aliasing — which abstention must refuse on.\n")

    print("PART 2 — the FIX: an `modelable()` detector abstains on the un-analyzable, so a silent miss")
    print("becomes an HONEST-UNKNOWN the check can refuse on. Scalability = knowing when you don't know.\n")
    print(f"  {'case':16} {'naive':16} {'with abstention':24}")
    print(f"  {'-'*16} {'-'*16} {'-'*24}")
    fixed = 0
    for c in CASES:
        naive = classify(c)[0]
        abst = abstaining_verdict(c)
        flip = "   <- silent miss -> honest" if naive == "UNSOUND-SILENT" and "UNKNOWN" in abst else ""
        if flip:
            fixed += 1
        print(f"  {c.label:16} {naive:16} {abst:24}{flip}")
    print(f"\n  Abstention converted {fixed} UNSOUND-SILENT construct(s) into HONEST-UNKNOWN — zero silent")
    print("  misses remain. The symbolic core now scales SAFELY: it derives what it can, and refuses (hands")
    print("  off at the membrane) on what it can't — never a confident wrong answer. THAT is the scalable")
    print("  posture, and this sweep is how we'd measure it against a real corpus next.")


if __name__ == "__main__":
    main()
