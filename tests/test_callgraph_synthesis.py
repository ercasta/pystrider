"""Pins for the call-graph-shape synthesis probe.

These lock the claims of experiments/callgraph_synthesis.py: the program's FACTORING (how many
functions, the call edges among them) is itself synthesized, driven by DRY requirements, and verified
two ways — by re-execution (all shapes compute the same figure) and by re-deriving the structural
features from the emitted AST (never trusting the shape's claim). The headline is the progressive
STRUCTURAL flip: dry_source forces a shared helper, dry_runtime forces the shared result to be reused.
Selection runs through the productized `pystrider.emit` surface (no re-implemented realize/choose).
"""
import ast

import pytest

from pystrider import emit

from experiments.callgraph_synthesis import (
    Spec, SHAPES, _BY_NAME, required,
    call_graph, actual_features, behaves, synthesize,
)


def test_all_shapes_compute_the_same_figure():
    """The shapes are behaviourally equivalent — so the call-graph choice is purely STRUCTURAL, which
    is the whole point. Each pre-minted whole-program template re-executes to the same figure."""
    for sh in SHAPES:
        src = sh.emit(Spec("s"))
        ast.parse(src)
        assert behaves(src)


def test_lenient_prefers_the_compact_monolith():
    """With no DRY requirement, all three shapes realize and CHOOSE picks the most compact — the
    inline monolith (one function, no call edges)."""
    r = synthesize(Spec("report_spec"))
    assert sorted(r.retrieved) == ["helper_once", "helper_twice", "inline_dup"]
    assert r.winner == "inline_dup"
    assert r.graph == {"report": []}                                # 1 node, 0 edges


def test_dry_source_forces_a_shared_helper():
    """dry_source requires `factored`, excluding the monolith (which duplicates the logic) — only the
    helper shapes realize, and CHOOSE picks the more compact `helper_twice`. The call graph now has a
    `normalize` node with in-degree 2 (two call sites)."""
    spec = Spec("report_spec", dry_source=True)
    assert required(spec) == {"factored"}
    r = synthesize(spec)
    assert sorted(r.retrieved) == ["helper_once", "helper_twice"]
    assert r.winner == "helper_twice"
    assert r.graph["report"].count("normalize") == 2               # shared callee, in-degree 2


def test_dry_runtime_forces_reuse_of_the_result():
    """The second flip: dry_runtime requires `single_eval`, which only `helper_once` provides — so the
    winner FLIPS again, to the shape that binds `normalize(x)` once and reuses it (one call site)."""
    spec = Spec("report_spec", dry_source=True, dry_runtime=True)
    assert required(spec) == {"factored", "single_eval"}
    r = synthesize(spec)
    assert sorted(r.retrieved) == ["helper_once"]
    assert r.winner == "helper_once"
    assert r.graph["report"].count("normalize") == 1               # called once


def test_structure_is_rederived_from_the_ast_not_trusted():
    """The epistemic move: the structural features are DERIVED from the emitted AST, and they match
    each shape's declared `provides` — so verification checks the artifact, not the claim."""
    assert actual_features(_BY_NAME["inline_dup"].emit(Spec("s"))) == set()
    assert actual_features(_BY_NAME["helper_twice"].emit(Spec("s"))) == {"factored"}
    assert actual_features(_BY_NAME["helper_once"].emit(Spec("s"))) == {"factored", "single_eval"}
    for sh in SHAPES:
        assert set(sh.provides) == actual_features(sh.emit(Spec("s")))   # claim == reality


def test_exclusion_is_a_derived_miss_via_the_emit_surface():
    """WHY the monolith is excluded under dry_source is a rule derivation in the productized surface:
    it does not appear among the realizers (it lacks `factored`), while the helper shapes do."""
    realizers = {c.name for c in emit.realizing("report_spec", {"factored"}, SHAPES)}
    assert "inline_dup" not in realizers
    assert realizers == {"helper_twice", "helper_once"}


@pytest.mark.parametrize("spec,winner,edges_to_normalize", [
    (Spec("report_spec"), "inline_dup", 0),
    (Spec("report_spec", dry_source=True), "helper_twice", 2),
    (Spec("report_spec", dry_source=True, dry_runtime=True), "helper_once", 1),
])
def test_synthesize_end_to_end(spec, winner, edges_to_normalize):
    """The whole loop per spec: select -> emit -> verify (behaviour + structure), and the emitted call
    graph has the expected number of edges into the shared `normalize`."""
    r = synthesize(spec)
    assert r.winner == winner and r.verified
    assert r.behaves_ok and r.features_ok
    assert r.graph.get("report", []).count("normalize") == edges_to_normalize


def test_pre_minted_shapes_are_real_programs():
    """The emit tool pre-mints whole-program SHAPE templates (rules select, never mint); every one is
    parseable Python and defines `report`."""
    for sh in SHAPES:
        tree = ast.parse(sh.emit(Spec("s")))
        assert "report" in {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
