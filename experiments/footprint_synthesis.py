"""Feasibility probe → PRODUCTIZED: footprint synthesis is now `pystrider.footprint`.

The synthesis itself (derive a fragment's write footprint from its CODE, static AST + dynamic run,
cross-checked) has been promoted into the package — `pystrider.footprint_of` / `CodeFootprint`. This
file keeps only what is genuinely probe/seam material: the grammapy ADAPTER (`derived_item`) and the
two demonstrations that motivate the module. It imports the product rather than re-deriving it (paying
down the probe-divergence tax, docs/critique.md #8).

The point it demonstrates is unchanged, and it is a COMPLEMENT to grammapy, not a replacement: grammapy
is the checker (does a set of footprints compose?); footprint synthesis is the INPUT to that checker,
derived from code instead of hand-declared. Type-checker : type-inference. The liar below is rejected by
grammapy's OWN `Accumulate.check` — synthesis just hands it the real footprint to reject on.

Run it: `python -m experiments.footprint_synthesis`
"""
from __future__ import annotations

from dataclasses import dataclass

from grammapy import Accumulate, Item, Footprint, Channel, CompositionError

# the productized synthesis (re-exported so this module's readers/tests see one surface).
from pystrider.footprint import CodeFootprint, footprint_of, static_writes, dynamic_writes

__all__ = ["CodeFootprint", "footprint_of", "static_writes", "dynamic_writes", "derived_item"]


# --- the SEAM: adapt a derived CodeFootprint into a grammapy Item (the two decoupled halves join here) --

def derived_item(label: str, source: str) -> Item:
    """A grammapy `Item` whose footprint is DERIVED from the code — the drop-in for a hand-declared one.
    This is the join between the analysis half (pystrider derives) and the composition half (grammapy
    checks); it lives at the seam because neither package imports the other."""
    fp = footprint_of(source)
    return Item(label=label, footprint=Footprint.of(writes=[Channel(w) for w in fp.writes]))


# --- the demonstrations ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Frag:
    label: str
    declares: str            # the HAND-DECLARED write channel (what a human wrote)
    source: str              # the actual code


def _accumulate(items: list[Item]) -> "str | None":
    try:
        Accumulate.check(items)
        return None
    except CompositionError as e:
        return str(e).splitlines()[0]


def demo_liar() -> None:
    scale = Frag("scale", declares="out.scaled", source="out['scaled'] = x * 2")
    # the LIAR: declares it writes `out.shifted`, but the code writes `out.scaled`.
    liar = Frag("shift_liar", declares="out.shifted", source="out['shifted'] = x + 10\nout['scaled'] = x + 10")

    print("  fragments:")
    for f in (scale, liar):
        fp = footprint_of(f.source)
        print(f"    {f.label}: declares {{{f.declares}}}   code actually writes {set(fp.writes)}"
              f"   (static={set(fp.static)}, dynamic={set(fp.dynamic)}, agree={fp.agree})")

    declared_items = [Item(f.label, Footprint.of(writes=[Channel(f.declares)])) for f in (scale, liar)]
    derived_items = [derived_item(f.label, f.source) for f in (scale, liar)]

    print(f"\n  Accumulate over DECLARED footprints: {_accumulate(declared_items) or 'ADMITTED (disjoint) — WRONG, they collide'}")
    print(f"  Accumulate over DERIVED  footprints: {_accumulate(derived_items) or 'admitted'}")
    print("  => grammapy's OWN check rejects the collision once fed the DERIVED footprint; the trusted "
          "input moved from the declaration to the CODE.\n")


def demo_two_oracles() -> None:
    print("  each oracle covers the other's blind spot:")
    branch = "if x < 0:\n    out['neg'] = 1\nelse:\n    out['pos'] = 1"
    fp = footprint_of(branch, x=5)                       # x=5 takes the else branch
    print(f"    branchy code  (x=5): static={set(fp.static)}  dynamic={set(fp.dynamic)}"
          f"  -> dynamic MISSED {set(fp.dynamic_missed)} (untaken branch); sound footprint (union)={set(fp.writes)}")
    computed = "k = 'total'\nout[k] = x"
    fpc = footprint_of(computed)
    print(f"    computed key       : static={set(fpc.static)}  dynamic={set(fpc.dynamic)}"
          f"  -> static could not resolve the key; dynamic did; sound footprint={set(fpc.writes)}\n")


def main() -> None:
    print("FOOTPRINT SYNTHESIS (now pystrider.footprint) — derive the footprint from the code, so the")
    print("check inspects the code, not a label. A COMPLEMENT to grammapy: it feeds grammapy's checker.\n")
    print("PART 1 — a FOOTPRINT LIAR: hand-declared Accumulate admits it; derived-footprint Accumulate rejects it\n")
    demo_liar()
    print("PART 2 — why TWO oracles: static sees all branches, dynamic resolves computed keys; union is sound\n")
    demo_two_oracles()
    print("The footprint is the load-bearing input to every grammapy check. Deriving it from the code")
    print("removes the last hand-declared link from the trust chain — the composition guarantee reasons")
    print("over what the code DOES, not what a human CLAIMED. grammapy still checks; it just checks the truth.")


if __name__ == "__main__":
    main()
