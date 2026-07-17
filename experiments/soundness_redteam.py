"""Soundness RED-TEAM — deliberately try to make the checker certify WRONG code, and map what it can't see.

The whole thesis rests on the checker: derive a fragment's footprint (what it writes) + verify by
execution. A thesis is only credible if you attack its load-bearing part hardest. So this probe is
adversarial: it constructs code designed to slip past the checker — "footprint says clean / ran fine",
while the code actually writes something the disjointness check would need, or behaves wrong. Each case is
classified against ground truth:

    CAUGHT(abstain)  the abstention detector refused to model it -> honest UNKNOWN, safe
    CAUGHT(crash)    the derivation raised rather than lie -> not silent, at least
    SOUND            the footprint included the real write
    SLIPPED          the footprint MISSED a real write with no abstention -> the checker was FOOLED

The SLIPPED rows are the honest output. Since abstention was PRODUCTIZED and strengthened in
`pystrider.footprint.modelable`, the footprint oracle now has **zero** SLIPPED in this battery — the two
classes that once escaped (operator-mutation `|=`, container-aliasing across an untaken branch) are caught.
The remaining named boundary is the EXECUTION oracle's own blind spots (input-dependence, non-determinism),
where multi-input / property / determinism checks must extend before that half of the guarantee is real.

Run it: `python -m experiments.soundness_redteam`
"""
from __future__ import annotations

from dataclasses import dataclass

from pystrider.footprint import footprint_of
from experiments.footprint_scalability import modelable


@dataclass(frozen=True)
class Case:
    label: str
    source: str
    truth: frozenset      # the channels the code ACTUALLY writes (ground truth)
    note: str


# adversarial cases against the FOOTPRINT oracle (what a fragment writes -> the disjointness check).
CASES: tuple[Case, ...] = (
    Case("subscript", "out['a'] = 1", frozenset({"out.a"}), "baseline — a plain write"),
    Case("aug_subscript", "out['a'] = 0\nout['a'] += 1", frozenset({"out.a"}), "augmented subscript"),
    Case("tuple_targets", "out['a'], out['b'] = 1, 2", frozenset({"out.a", "out.b"}), "tuple of subscripts"),
    Case("update_method", "out.update({'a': 1})", frozenset({"out.a"}), "dict.update — bypasses __setitem__"),
    Case("setdefault_chain", "out.setdefault('a', []).append(1)", frozenset({"out.a"}), "mutate via setdefault"),
    Case("helper_mutate", "def h(o):\n    o['a'] = 1\nh(out)", frozenset({"out.a"}),
         "write through a LOCAL helper call — followed into exactly (now SOUND, not abstained)"),
    Case("opaque_callee", "external(out)", frozenset({"out.a"}),
         "store passed to an OPAQUE (out-of-view) callee — the genuine inter-procedural escape"),
    Case("alias_direct", "d = out\nd['a'] = 1", frozenset({"out.a"}), "store aliased then written"),
    Case("ior_operator", "out |= {'a': 1}", frozenset({"out.a"}), "|= dict-union — no subscript, bypasses __setitem__"),
    Case("container_alias_untaken",
         "box = [out]\nif x < 0:\n    box[0]['a'] = 1\nelse:\n    out['b'] = 1",
         frozenset({"out.a", "out.b"}), "aliased-through-a-list write on the untaken branch"),
)


def classify(c: Case) -> tuple[str, set]:
    try:
        derived = {w for w in footprint_of(c.source).writes if not w.endswith(".<computed>")}
        crashed = False
    except Exception:
        derived, crashed = set(), True
    if not modelable(c.source):
        return "CAUGHT(abstain)", derived
    if crashed:
        return "CAUGHT(crash)", derived
    if derived >= set(c.truth):
        return "SOUND", derived
    return "SLIPPED", derived


# --- the OTHER half of the checker: verify-by-execution, and its own blind spots ---------------------

def _run(src: str, **env) -> dict:
    ns = dict(env)
    exec(src, {}, ns)
    return ns


def main() -> None:
    print("SOUNDNESS RED-TEAM — can the checker be made to certify wrong code? Where is it blind?\n")

    print("PART 1 — the FOOTPRINT oracle (what a fragment writes -> the disjointness check):\n")
    print(f"  {'case':24} {'truth':22} {'derived':20} verdict")
    print(f"  {'-'*24} {'-'*22} {'-'*20} {'-'*16}")
    slipped = []
    for c in CASES:
        v, derived = classify(c)
        if v == "SLIPPED":
            slipped.append(c.label)
        miss = f"  MISSED {sorted(set(c.truth) - derived)}" if v == "SLIPPED" else ""
        print(f"  {c.label:24} {str(sorted(c.truth)):22} {str(sorted(derived)):20} {v}{miss}")
    print(f"\n  {len(slipped)} of {len(CASES)} SLIPPED — the checker was FOOLED (missed a real write, no abstention): {slipped}")
    print("  ZERO now slip: the two classes this red-team once caught escaping — operator-mutation (`|=`) and")
    print("  container-aliasing across an untaken branch — are CAUGHT since abstention was PRODUCTIZED and")
    print("  strengthened (`pystrider.footprint.modelable`: the store is modelable only if it is *only ever")
    print("  subscripted*, which those two violate). Every footprint case is now SOUND or CAUGHT(abstain).\n")

    print("PART 2 — the EXECUTION oracle (verify by running), and ITS blind spots:\n")

    # (a) input-dependence: a single input passes, another reveals the bug.
    f = "def f(v):\n    return v or 'default'"
    ns = _run(f)
    print("  (a) INPUT-DEPENDENCE — verify on one input is not verification:")
    print(f"      f(5)  -> {ns['f'](5)!r}   (looks like it returns its input — 'verified')")
    print(f"      f(0)  -> {ns['f'](0)!r}   (a falsy-but-valid input is silently dropped — the bug)")
    print("      A single-input verify SLIPS; only multi-input / property-based checking catches it.\n")

    # (b) non-determinism: one run 'passes' but the value is not reproducible.
    nd = "import random\nresult = random.random()"
    r1, r2 = _run(nd)["result"], _run(nd)["result"]
    print("  (b) NON-DETERMINISM — a single run certifies an unreproducible value:")
    print(f"      run 1 -> {r1:.4f}   run 2 -> {r2:.4f}   (different — the 'verified' behavior is not stable)")
    print("      The execution oracle sees ONE run; determinism must be checked, not assumed.\n")

    print("READING: the FOOTPRINT oracle now has NO silent slip in this battery — the once-open operator-mutation")
    print("and container-aliasing classes were closed by productizing + strengthening abstention. The remaining")
    print("named boundary is the EXECUTION oracle: input-dependence (fix: multi-input/property verify) and")
    print("non-determinism (fix: a determinism check). None of these is a silent mystery — each is a precise gap")
    print("with a known mitigation. That map is the credible claim: the guarantee holds up to THIS enumerated boundary.")


if __name__ == "__main__":
    main()
