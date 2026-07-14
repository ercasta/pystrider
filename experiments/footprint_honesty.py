"""Feasibility probe — FOOTPRINT HONESTY checked by EXECUTION (the grammapy convergence, Phase 5 step 7).

grammapy's whole non-interference guarantee is decided from **declared** footprints: `Accumulate.check`
admits a set of atoms iff their declared `writes` are pairwise disjoint (the frame rule). That guarantee
is only as true as the declarations. An atom that DECLARES it writes `confirm.button.cancel` but at
runtime ALSO writes `confirm.submit` is *dishonest* — and grammapy, reasoning over the declaration,
admits a composition that actually collides. The declaration is the trusted input; nothing checks it.

That is exactly the gap pystrider was built to close. Every other axis of this project trusts code by
**executing it**, never by its claim (analysis re-executes; app-synthesis drives the app). Here the same
move certifies a footprint: DRIVE the atom in an instrumented store that RECORDS every channel it writes,
and compare the OBSERVED write-set to the DECLARED one. This is grammapy roadmap step 7 (empirical
footprint / non-interference check), implemented by pystrider's concrete-exec oracle.

Two findings, one line each:

  1. HONESTY is an execution property, not a declaration. `footprint_honest(atom)` executes the atom and
     reports the writes it made OUTSIDE its declared footprint. An honest atom writes ⊆ what it declared;
     a dishonest one is caught the only way it can be — by running it.

  2. EXECUTION can reject a composition grammapy ADMITTED. Two atoms whose *declared* writes are disjoint
     pass `Accumulate.check` at design time. But if one is dishonest, re-running the disjointness rule
     over the *observed* writes finds the real collision grammapy could not see. Design-time composition
     trusts the declarations; execution verifies them — and the verdict can flip from admitted to rejected.

**The seam this exposes (feeds the deferred bridges-vs-channels decision).** Honesty is only checkable
when a channel NAME maps to an observable runtime effect. Here that mapping is concrete because the atom
bodies write a store keyed by channel name. Grounding the *real* withdrawal app's button atoms the same
way (mapping `confirm.submit` to an observable Textual effect) is precisely what typing pystrider's
untyped bridges as grammapy channel contracts would buy — so this probe is the concrete evidence for that
call, not a resolution of it (docs/grammapy_convergence.md, "bridges-vs-channels").

Run it: `python -m experiments.footprint_honesty`
"""
from __future__ import annotations

from dataclasses import dataclass, field

from grammapy import Accumulate, Channel, CompositionError, Footprint, Item
from grammapy.channels import disjoint_writes


# --- an executable ATOM: a footprint DECLARATION paired with the code that realizes it ----------
# grammapy's `Item` is a label + a declared footprint — the design-time view. To CHECK the
# declaration we need the atom's behaviour too, so an executable atom additionally carries a `body`:
# a fragment that writes the channels it actually touches into a `store` (keyed by channel name). The
# store is the observable boundary — the concrete stand-in for the runtime effects a real atom has.

@dataclass(frozen=True)
class Atom:
    """A grammapy atom made executable: `label` + declared `footprint` (as `Item`) + a `body` fragment.
    `body` runs with one name in scope, `store`, and writes each channel it touches as `store["<name>"]`.
    The DECLARED footprint is what grammapy trusts; the BODY is what execution reveals."""
    label: str
    footprint: Footprint
    body: str

    @property
    def item(self) -> Item:
        """The design-time view grammapy composes over (drops the body — the declaration is all it sees)."""
        return Item(label=self.label, footprint=self.footprint)


class RecordingStore:
    """An instrumented write-only store: it RECORDS the name of every channel written to it. The
    observable boundary the atom's execution is watched through (the concrete-exec instrument)."""
    def __init__(self) -> None:
        self.written: set[str] = set()

    def __setitem__(self, channel: str, value: object) -> None:
        self.written.add(channel)


def observed_writes(atom: Atom) -> set[str]:
    """EXECUTE the atom against a fresh instrumented store and return the channels it actually wrote.
    Trust by execution: this is what the atom DOES, independent of what its footprint CLAIMS. Safe —
    the bodies are our own self-contained fragments (the design's concrete-exec tool, in miniature)."""
    store = RecordingStore()
    exec(compile(atom.body, f"<atom {atom.label}>", "exec"), {"store": store})
    return store.written


# --- the HONESTY check: observed writes vs declared writes --------------------------------------

@dataclass
class HonestyResult:
    """What executing an atom revealed about its footprint. `honest` iff every write it made was
    DECLARED (observed ⊆ declared); `undeclared` names the channels it wrote but did not admit to."""
    label: str
    declared: set[str]
    observed: set[str]
    undeclared: set[str]

    @property
    def honest(self) -> bool:
        return not self.undeclared


def footprint_honest(atom: Atom) -> HonestyResult:
    """Certify one atom's footprint by EXECUTION: run it, compare the writes it made to the writes it
    declared. An honest atom writes only what its footprint admits; a dishonest one is caught here and
    only here — no static reading of the declaration can reveal a write the declaration omits."""
    declared = {c.name for c in atom.footprint.writes}
    observed = observed_writes(atom)
    return HonestyResult(atom.label, declared, observed, undeclared=observed - declared)


# --- the composition gate: grammapy admits by DECLARATION, pystrider verifies by EXECUTION ------

@dataclass
class CompositionVerdict:
    """The two-stage verdict on a composition. `admitted_by_declaration` = grammapy's design-time call
    from the declared footprints; `honest` = every atom's declaration held under execution; `safe_by
    _execution` = the disjointness rule re-run over the OBSERVED writes still holds. A composition is
    trustworthy iff all three agree — and the interesting case is when the first says yes and the rest no."""
    admitted_by_declaration: bool
    dishonest: list[HonestyResult]
    observed_conflicts: list
    declaration_error: str | None = None
    execution_error: str | None = None

    @property
    def honest(self) -> bool:
        return not self.dishonest

    @property
    def safe_by_execution(self) -> bool:
        return not self.observed_conflicts

    @property
    def trustworthy(self) -> bool:
        return self.admitted_by_declaration and self.honest and self.safe_by_execution


def verify_composition(atoms: list[Atom]) -> CompositionVerdict:
    """The full step-7 gate. (1) DESIGN TIME: grammapy `Accumulate.check` over the DECLARED footprints —
    the guarantee as grammapy issues it. (2) EXECUTION: certify each atom's footprint is honest, then
    re-run the disjointness rule over the OBSERVED writes. A composition grammapy admitted on false
    declarations is rejected here, naming the real collision. pystrider is grammapy's step-7 oracle."""
    try:                                                   # (1) grammapy's design-time admission
        Accumulate.check(a.item for a in atoms)
        admitted, decl_err = True, None
    except CompositionError as e:
        admitted, decl_err = False, str(e)

    results = [footprint_honest(a) for a in atoms]         # (2) execution-certified honesty
    dishonest = [r for r in results if not r.honest]

    # re-run the frame rule over what the atoms ACTUALLY write, not what they claim.
    observed_items = [(a.label, Footprint.of(writes=[Channel(n) for n in r.observed]))
                      for a, r in zip(atoms, results)]
    conflicts = disjoint_writes(observed_items)
    exec_err = str(CompositionError("Accumulate", conflicts)) if conflicts else None
    return CompositionVerdict(admitted, dishonest, conflicts, decl_err, exec_err)


# --- the withdrawal-app button atoms, made executable (honest and dishonest variants) -----------
# The real app's confirmation buttons (experiments/app_synthesis.py `_button_atom`): each writes its
# own widget slot `confirm.button.<id>`, and an AFFIRMATIVE button also binds the shared proceed action
# `confirm.submit`. Here each is given a body that performs exactly those writes — an HONEST atom. The
# dishonest `cancel` additionally binds `confirm.submit` at runtime WITHOUT declaring it: the collision
# grammapy cannot see (it composed `{ok, cancel}` as disjoint) but execution does.

def honest_button(b: str, *, affirmative: bool) -> Atom:
    """An honest confirmation-button atom: it declares AND writes its own slot, plus `confirm.submit`
    iff it is the affirmative (proceed) button. Declaration and behaviour agree — grammapy's guarantee
    is real for this atom."""
    writes = [Channel(f"confirm.button.{b}")] + ([Channel("confirm.submit")] if affirmative else [])
    body = f'store["confirm.button.{b}"] = 1\n' + ('store["confirm.submit"] = 1\n' if affirmative else '')
    return Atom(label=f"button {b}", footprint=Footprint.of(writes=writes), body=body)


def dishonest_cancel() -> Atom:
    """A `cancel` atom that DECLARES only its own slot but SECRETLY binds `confirm.submit` at runtime —
    the kind of quiet feature-interaction a hand-written or generated atom introduces. Its declared
    footprint is disjoint from `ok`'s, so grammapy admits `{ok, cancel}`; its behaviour is not."""
    return Atom(label="button cancel",
                footprint=Footprint.of(writes=[Channel("confirm.button.cancel")]),  # DECLARES no submit
                body='store["confirm.button.cancel"] = 1\nstore["confirm.submit"] = 1\n')  # but WRITES it


# --- live walkthrough -------------------------------------------------------------------------

def _fmt(s: set[str]) -> str:
    return "{" + ", ".join(sorted(s)) + "}" if s else "{}"


def main() -> None:
    print("FOOTPRINT HONESTY - grammapy admits by DECLARATION; pystrider verifies by EXECUTION\n")
    print("(grammapy roadmap step 7: the non-interference guarantee is only as true as the footprints\n"
          " it trusts - so drive the atom and check the writes it CLAIMED against the writes it MADE.)\n")

    ok = honest_button("ok", affirmative=True)
    cancel_honest = honest_button("cancel", affirmative=False)
    cancel_bad = dishonest_cancel()

    print("PART 1 - an honest atom writes only what it declared\n")
    for atom in (ok, cancel_honest):
        r = footprint_honest(atom)
        print(f"  {atom.label:<14} declared {_fmt(r.declared):<45} observed {_fmt(r.observed):<45} "
              f"-> honest={r.honest}")

    print("\nPART 2 - a DISHONEST atom is caught only by running it\n")
    r = footprint_honest(cancel_bad)
    print(f"  {cancel_bad.label:<14} declared {_fmt(r.declared):<45} observed {_fmt(r.observed):<45}")
    print(f"      -> honest={r.honest}   undeclared writes: {_fmt(r.undeclared)}")
    print("      (no static reading of the declaration could reveal `confirm.submit` - it is not there.)")

    print("\nPART 3 - execution REJECTS a composition grammapy ADMITTED\n")
    good = verify_composition([ok, cancel_honest])
    print(f"  {{ok, cancel}} (both honest):")
    print(f"      grammapy admits by declaration: {good.admitted_by_declaration}   "
          f"honest under execution: {good.honest}   safe by execution: {good.safe_by_execution}")
    print(f"      => trustworthy: {good.trustworthy}\n")

    bad = verify_composition([ok, cancel_bad])
    print(f"  {{ok, cancel}} (cancel is dishonest):")
    print(f"      grammapy admits by declaration: {bad.admitted_by_declaration}   "
          f"(disjoint DECLARED footprints -> grammapy sees no conflict)")
    print(f"      honest under execution: {bad.honest}   dishonest: {[r.label for r in bad.dishonest]}")
    print(f"      safe by execution: {bad.safe_by_execution}   => trustworthy: {bad.trustworthy}")
    print("      the real collision, from OBSERVED writes:")
    for line in (bad.execution_error or "").splitlines():
        print(f"        {line}")

    print("\n  So the guarantee has two halves: grammapy proves the DECLARED footprints compose; pystrider")
    print("  proves the declarations are HONEST. Only together do they certify the composition - which is")
    print("  grammapy's own roadmap step 7, and the concrete evidence for typing bridges as channels.")


if __name__ == "__main__":
    main()
