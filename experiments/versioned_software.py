"""Feasibility probe — the SOFTWARE ITSELF is versioned: a build DAG with a movable `current` pointer.

`versioned_recovery.py` versioned the STATE a program computes. This probe versions the PROGRAM — the
code artifact under revision — which is pystrider's actual domain. A **build** is a reified version
node wired (hyperedges) to the fragment nodes that constitute the program at that version; a `current`
pointer selects the live build; the emitted source is derived from `current`. Editing/repairing is
minting the NEXT build and MOVING the pointer — never mutating or deleting the old one (monotone). This
is git's object store + moving HEAD, made of graph nodes.

What that buys, none of which the template/in-place model can give:

  * REPAIR AS A VERSION TRANSITION — a rejected build is not patched in place; recovery mints `build v2`
    (current build with the offending fragment REPLACED by its alternative, derived by compose_recover's
    recovery rule) and moves `current` to it. The transition carries PROVENANCE (`revised_from`,
    `replaced`, `reason`), so `why does the shipped program contain shift_ok?` is answerable.
  * TIME TRAVEL — every past build is RETAINED and still emittable; `current` can be moved BACK (undo)
    and forward (redo) with nothing deleted — the pointer move is the only operation.
  * THE VERIFIED CODE CHANGE (roadmap Phase 3, `rederivation.py`) becomes a WALK over the build DAG:
    the diff a policy change produces is `emit(v_before)` vs `emit(v_after)`, two nodes in the DAG.

The trust move is unchanged: a build SHIPS only if it passes the design-time check (grammapy disjoint
writes) AND drives correct (re-execution). The generator proposes builds; the checker + the Pilot
dispose. No language model anywhere — the whole loop is rules + execution.

Run it: `python -m experiments.versioned_software`
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from ugm import AttrGraph

from experiments.compose_recover import (
    CATALOG, Fragment, Composition, compose, check, recover, emit, verify,
)

REQUIRED = ("scaled", "shifted")


# --- the build DAG: reified version nodes + a movable current pointer, all monotone -----------------

@dataclass
class Build:
    """One version of the software: a reified node wired to its member fragments, its parent, and the
    provenance of the edit that produced it. The `comp` (the actual code artifact) is the opaque blob a
    tool opens; the graph holds the STRUCTURE."""
    id: int
    node: str
    comp: Composition
    revised_from: "int | None" = None
    replaced: str = ""
    added: str = ""
    reason: str = ""


class SoftwareRepo:
    """A monotone, versioned store of the software. Builds are graph nodes wired to their fragments and
    parents; the `current` pointer is an APPEND-ONLY reflog of build ids (a pointer move adds an entry,
    never rewrites). Nothing is ever deleted — revision and undo are both just moving `current`."""

    def __init__(self) -> None:
        self.g = AttrGraph()
        self._by_id: dict[int, Build] = {}
        self._reflog: list[int] = []                      # append-only history of what `current` pointed at
        self._sw = self.g.add_node("<software>")

    def _ensure(self, name: str) -> str:
        found = self.g.nodes_named(name)
        return found[0] if found else self.g.add_node(name)

    def mint(self, comp: Composition, *, revised_from: "int | None" = None,
             replaced: str = "", added: str = "", reason: str = "") -> Build:
        """Mint a new build node from `comp`, wire it into the DAG (members, parent, provenance), point
        `current` at it, and return it. Additive only — a prior build is never touched."""
        bid = len(self._by_id) + 1
        node = self.g.add_node(f"<build:{bid}>")
        for frag in comp.fragments:
            self.g.add_relation(node, "member", self._ensure(frag.name))
        if revised_from is not None:
            self.g.add_relation(node, "revised_from", self._by_id[revised_from].node)
            self.g.add_relation(node, "supersedes", self._by_id[revised_from].node)
        if replaced:
            self.g.add_relation(node, "replaced", self._ensure(replaced))
        if added:
            self.g.add_relation(node, "added", self._ensure(added))
        build = Build(bid, node, comp, revised_from, replaced, added, reason)
        self._by_id[bid] = build
        self._reflog.append(bid)                          # MOVE current (append; never rewrite)
        return build

    def move_current(self, bid: int) -> None:
        """Move the `current` pointer to an EXISTING build (undo/redo). Append-only: the reflog records
        the move; every build the pointer ever left remains in the graph, re-emittable."""
        self._reflog.append(bid)

    def current(self) -> Build:
        return self._by_id[self._reflog[-1]]

    def builds(self) -> list[Build]:
        return [self._by_id[i] for i in sorted(self._by_id)]

    def why(self, bid: int) -> str:
        """Render the provenance of a build — the recorded reason it exists (the RECORD trace)."""
        b = self._by_id[bid]
        if b.revised_from is None:
            return f"build {b.id}: the initial draft"
        return (f"build {b.id}: revised from build {b.revised_from} — replaced `{b.replaced}` with "
                f"`{b.added}` because {b.reason}")

    def emit(self, bid: int) -> str:
        return emit(self._by_id[bid].comp)


# --- the development loop: propose a build, gate it, and on rejection mint the next version ----------

@dataclass
class Development:
    repo: SoftwareRepo
    shipped: "Build | None" = None
    steps: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.shipped is not None


def develop(prefer: dict, catalog: tuple[Fragment, ...] = CATALOG, fuel: int = 3) -> Development:
    """Author an initial build and drive it through the gate; on rejection, mint the repaired build as
    the next version and move `current`. Returns when a build ships (checks clean AND drives correct)."""
    repo = SoftwareRepo()
    dev = Development(repo)
    build = repo.mint(compose(REQUIRED, catalog, prefer))
    dev.steps.append(f"minted build {build.id} (initial): {[f.name for f in build.comp.fragments]}")

    for _ in range(fuel):
        errs = check(build.comp)
        v = verify(build.comp, REQUIRED)
        if not errs and v.ok:
            dev.shipped = build
            dev.steps.append(f"build {build.id} PASSES (check clean, drives {v.result}) -> SHIP")
            return dev
        why = errs[0].conflicts[0] if errs else v.reason
        dev.steps.append(f"build {build.id} REJECTED: {why}")
        rec = recover(build.comp, errs[0], catalog) if errs else None
        if rec is None or rec.repaired is None:
            dev.steps.append("no repair available -> refuse")
            return dev
        bad, alt = rec.accepted
        build = repo.mint(rec.repaired, revised_from=build.id, replaced=bad, added=alt,
                          reason=f"{why}")
        dev.steps.append(f"minted build {build.id}: {bad} -> {alt}; current now build {build.id}")
    return dev


def _diff(repo: SoftwareRepo, a: int, b: int) -> str:
    left, right = repo.emit(a).splitlines(), repo.emit(b).splitlines()
    return "\n".join(difflib.unified_diff(left, right, fromfile=f"build{a}", tofile=f"build{b}", lineterm=""))


def main() -> None:
    print("VERSIONED SOFTWARE — the program is a build DAG; repair mints the next version, undo moves back.\n")

    print("Develop a buggy draft (scale + shift_bad) — the clobber is caught, and the REPAIR is a new")
    print("BUILD, not an in-place patch:\n")
    dev = develop(prefer={"shifted": "shift_bad"})
    for s in dev.steps:
        print(f"   {s}")
    repo = dev.repo

    print("\nThe build DAG (every version RETAINED — nothing deleted):")
    for b in repo.builds():
        mark = "  <- current (shipped)" if b is repo.current() else ""
        print(f"   build {b.id}: {[f.name for f in b.comp.fragments]}{mark}")
        print(f"      {repo.why(b.id)}")

    print("\nTIME TRAVEL — every past build is still emittable. Source diff build1 -> build2 (the verified")
    print("code change, as a walk over the DAG):")
    print("\n".join("      " + ln for ln in _diff(repo, 1, 2).splitlines()))

    print("\nUNDO — move `current` back to build 1 (nothing deleted; the pointer just moves):")
    repo.move_current(1)
    print(f"   current is now build {repo.current().id}: {[f.name for f in repo.current().comp.fragments]}")
    print(f"   emit(current) drives to: {verify(repo.current().comp, REQUIRED).result}  (the old, buggy program)")
    repo.move_current(2)                                   # redo
    print(f"   REDO -> current build {repo.current().id}; drives to: {verify(repo.current().comp, REQUIRED).result}")

    print("\nThe program is versioned: repair is a version transition with provenance, undo/redo is a")
    print("pointer move, and every build ever made is retained and re-emittable. Monotone substrate +")
    print("first-class software versions => edit history, time travel, and the verified code change for free.")


if __name__ == "__main__":
    main()
