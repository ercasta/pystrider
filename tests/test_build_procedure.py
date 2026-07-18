"""Pins for the build-as-a-procedure probe (experiments/build_procedure.py).

The claim: a succinct spec becomes running code through steps SEQUENCED BY UGM'S PLANNER, where every
decision is a rule and the verdict is execution — and when the check fails, the loop course-corrects
rather than needing to have been right first time.
"""
import ugm as h

from experiments.build_procedure import (
    CURRENT, LOWERING, RECOVERY, build, current_versions, emit_source, many, of_kind, one,
)


def test_the_planner_runs_the_authored_steps_in_order():
    b = build()
    # `to build : expand then lower then emit then check` — the order is the procedure's, not Python's.
    assert b.order[:4] == ["expand", "lower", "emit", "check"]


def test_the_first_attempt_is_wrong_and_the_check_catches_it_by_EXECUTION():
    # the naive lowering prints the raw value; the spec expects a greeting. Nothing declares the
    # failure — it is observed by running the generated code and looking at stdout.
    b = build()
    assert b.workspace.expected() == ["hello_bob"]
    assert any("MISMATCH" in line for line in b.workspace.log)
    # the mismatch is recorded on the graph as a FACT, which is what the recovery rule fires on.
    g = b.workspace.g
    report = g.nodes_named("report")[0]
    assert [g.name(t) for t in many(g, report, "unmet")] == ["yes"]


def test_the_planner_replans_onto_the_alternative_producer():
    b = build()
    assert b.recovered and "repair" in b.order            # chosen by the planner's rules, not an `if`


def test_the_recovery_rule_produces_a_real_verified_code_change():
    b = build()
    assert b.source.splitlines()[-1].strip() == "print(greet(name))"
    assert b.stdout == ["hello_bob"]                      # verified by RUNNING it
    assert b.ok


def test_the_repair_is_monotone_and_the_superseded_version_survives():
    b = build()
    pr = of_kind(b.workspace.g, "emit_print")[0]
    versions = {b.workspace.g.name(v) for v in many(b.workspace.g, pr, "version")}
    assert versions == {"arg_v1", "arg_v2"}               # nothing was deleted
    assert current_versions(b.workspace)[pr] == "arg_v2"  # the projection picks the latest


def test_current_is_ASKED_not_stored():
    # the monotone lesson: a materialized `current` cannot move — an earlier value survives forever and
    # the node ends up with two. So the working graph must hold NO `current` fact at all; it is derived
    # read-only, on demand, from `version` + `supersedes`.
    b = build()
    pr = of_kind(b.workspace.g, "emit_print")[0]
    assert many(b.workspace.g, pr, "current") == []       # never materialized
    assert current_versions(b.workspace)[pr] == "arg_v2"  # yet answerable


def test_the_projection_is_per_node_not_global():
    # repairing one statement must not strip an unrepaired sibling of its current version. Two nodes,
    # only one carrying a v2: the conjunctive NAC scopes supersession to the node that holds both.
    g, ids = h.AttrGraph(), {}

    def node(n):
        if n not in ids:
            ids[n] = g.add_node(n)
        return ids[n]

    for s, p, o in [("a", "is_a", "emit_print"), ("a", "version", "arg_v1"),
                    ("a", "version", "arg_v2"),                     # repaired
                    ("b", "is_a", "emit_print"), ("b", "version", "arg_v1"),   # NOT repaired
                    ("arg_v2", "supersedes", "arg_v1")]:
        g.add_relation(node(s), p, node(o))
    h.run_bank(g, h.load_machine_rules(CURRENT))
    assert g.name(one(g, ids["a"], "current")) == "arg_v2"
    assert g.name(one(g, ids["b"], "current")) == "arg_v1"   # keeps its own current


def test_the_generated_line_is_explainable_back_to_the_observed_failure():
    # provenance over GENERATED code (ugm #15), addressed by definite description because the
    # substrate is nameless. The trace cites the failed run as the cause of the change.
    from ugm import ByDesc
    b = build()
    trace = h.ask_goal(b.workspace.g,
                       ("why", ByDesc("pr", (("arg_v1", "name"),)), "version", "arg_v2"),
                       h.load_machine_rules(RECOVERY), provenance=True)
    assert any("<- rule" in line for line in trace)        # threaded a rule, not "(given)"
    assert any("unmet" in line for line in trace)          # ...back to the OBSERVED failure
