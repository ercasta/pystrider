"""Pins for the build-as-a-procedure probe (experiments/build_procedure.py).

The claim: a succinct spec becomes running code through steps SEQUENCED BY UGM'S PLANNER, where every
decision is a rule and the verdict is execution — and when the check fails, the loop course-corrects
rather than needing to have been right first time.
"""
import ugm as h

from experiments.build_procedure import (
    CURRENT, LOWERING, RECOVERY, REPAIRS, STEPS, SPEC_TWO_REPAIRS, SPEC_UNCOVERED, SPEC_UNREPAIRABLE,
    build, current_versions, emit_source, many, of_kind, one,
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
    assert b.recovered and "repair_greet" in b.order      # chosen by the planner's rules, not an `if`


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


def test_a_verified_build_ships_and_a_refused_one_does_not():
    ok = build()
    assert ok.refusal is None and ok.shipped == ok.source

    for spec in (SPEC_UNCOVERED, SPEC_UNREPAIRABLE):
        bad = build(spec)
        assert bad.refusal is not None
        assert bad.shipped is None          # the whole point: never hand back an unverified program


def test_an_uncovered_intent_refuses_by_NAME_and_says_what_to_author():
    # MISSING knowledge: no expansion rule mentions `shouts`, so nothing is lowered at all.
    b = build(SPEC_UNCOVERED)
    r = b.refusal
    assert r.kind == "uncovered"
    assert r.missing == "shouts"            # names the intent, so the fix is obvious
    assert r.unreached == "spec_expanded"
    assert b.order == ["expand"]            # the chain stopped at the first step
    assert "author an expansion rule" in str(r)


def test_an_unrepairable_mismatch_refuses_AFTER_exhausting_every_repair():
    # INSUFFICIENT knowledge: the rules build a program, execution disagrees, EVERY available recovery
    # rule fires, and it still refuses rather than shipping. Distinguishing this from `uncovered`
    # matters — the fix is another recovery rule, not a missing expansion rule.
    b = build(SPEC_UNREPAIRABLE)
    r = b.refusal
    assert r.kind == "unverified"
    assert r.wanted == ("goodbye_bob",)
    assert set(REPAIRS) <= set(b.order)     # it really tried — both repairs ran
    assert not b.ok and b.shipped is None   # but the verdict is still refusal


def test_two_repairs_COMPOSE_when_one_is_not_enough():
    # the spec that was refused as `unverified` before a second recovery rule existed. Adding ONE small
    # rule closes it — and the loop finds the answer by NAVIGATION, not by a smarter single rule:
    # greet gets from 'bob' to 'hello_bob' (closer, still wrong), then shout wraps that repair.
    b = build(SPEC_TWO_REPAIRS)
    assert b.order[-2:] == ["repair_greet", "repair_shout"]
    assert b.source.splitlines()[-1].strip() == "print(shout(greet(name)))"
    assert b.stdout == ["HELLO_BOB"] and b.ok and b.refusal is None
    # three versions are held; the newest wins, the superseded ones remain as provenance.
    pr = of_kind(b.workspace.g, "emit_print")[0]
    assert {b.workspace.g.name(v) for v in many(b.workspace.g, pr, "version")} == {
        "arg_v1", "arg_v2", "arg_v3"}
    assert current_versions(b.workspace)[pr] == "arg_v3"


def test_a_repair_does_not_run_once_the_goal_already_holds():
    # the actuator guard: after `repair_greet` satisfies the spec, `repair_shout` must NOT fire and
    # shout an already-correct greeting. Without this a later alternative producer turns a passing
    # build into a failing one.
    b = build()
    assert b.order == ["expand", "lower", "emit", "check", "repair_greet"]
    assert "repair_shout" not in b.order
    assert b.stdout == ["hello_bob"] and b.ok


def test_a_repair_declares_the_progress_it_makes_and_what_it_depends_on():
    # `repair_shout` wraps the greeted payload, so it CANNOT run first. That ordering is real knowledge
    # and is declared (`payload_greeted`), not left to the order operators happen to be staged in.
    greet_step = next(s for s in STEPS if s.name == "repair_greet")
    shout_step = next(s for s in STEPS if s.name == "repair_shout")
    assert "payload_greeted" in greet_step.adds      # progress is an observable effect...
    assert "payload_greeted" in shout_step.needs     # ...and the next repair's precondition


def test_the_current_projection_agrees_across_the_forward_and_demand_engines():
    # ugm #16 turned up a real bug here: a CONJUNCTIVE NAC was decided per-atom on the demand chain, so
    # a rule that derived correctly under `run_bank` returned nothing when ASKED. `CURRENT` is exactly
    # that shape, so pin both engines agreeing — a question and a forward pass must not disagree.
    g, ids = h.AttrGraph(), {}

    def node(n):
        if n not in ids:
            ids[n] = g.add_node(n)
        return ids[n]

    for s, p, o in [("p1", "is_a", "emit_print"), ("p1", "version", "arg_v1"),
                    ("p1", "version", "arg_v2"),
                    ("p2", "is_a", "emit_print"), ("p2", "version", "arg_v1"),
                    ("arg_v2", "supersedes", "arg_v1")]:
        g.add_relation(node(s), p, node(o))
    rules = h.load_machine_rules(CURRENT)

    forward = g.copy()
    h.run_bank(forward, rules)
    assert forward.name(one(forward, ids["p1"], "current")) == "arg_v2"
    assert forward.name(one(forward, ids["p2"], "current")) == "arg_v1"

    assert h.ask_goal(g.copy(), "is p1 current arg_v2", rules) == ["yes"]
    assert h.ask_goal(g.copy(), "is p2 current arg_v1", rules) == ["yes"]
    assert h.ask_goal(g.copy(), "is p1 current arg_v1", rules) != ["yes"]   # superseded


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
