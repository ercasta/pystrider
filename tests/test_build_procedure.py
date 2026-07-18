"""Pins for the build-as-a-procedure probe (experiments/build_procedure.py).

The claim: a succinct spec becomes running code through steps SEQUENCED BY UGM'S PLANNER, where every
judgement is a rule over the substrate and the verdict is execution — and when the check fails, the
loop course-corrects rather than needing to have been right first time.
"""
import ugm as h

from experiments.build_procedure import _rank_tool as bp_rank
from experiments.build_procedure import (
    CHEAT_SOURCE, INSPECTION, ORACLES, SATISFIED, SPEC, inspection_graph, judge_source,
    CURRENT, RECOVERY, REFUSAL, REPAIRS, STEPS, VERDICT,
    SPEC_TWO_REPAIRS, SPEC_UNCOVERED, SPEC_UNREPAIRABLE,
    build, current_versions, many, of_kind, one, run_stratified, verdict,
)


def test_the_planner_runs_the_authored_steps_in_order():
    b = build()
    # `to build : expand then lower then emit then check` — the order is the procedure's, not Python's.
    assert b.order[:4] == ["expand", "lower", "emit", "check"]


def test_the_check_only_OBSERVES_and_the_verdict_is_a_rule():
    # the tool records what the world did; it forms no opinion. The graph carries one `observation`
    # per output line, and `satisfied` is DERIVED from those — nothing in Python compares them.
    b = build()
    obs = of_kind(b.workspace.g, "observation")
    assert obs, "check must mint an observation per output line"
    texts = {b.workspace.g.name(one(b.workspace.g, o, "text")) for o in obs}
    assert "bob" in texts                       # the first, WRONG run is on the record
    assert "hello_bob" in texts                 # ...and so is the repaired one
    assert verdict(b.workspace) is True         # the verdict is asked of the substrate


def test_the_first_attempt_is_wrong_and_is_caught_by_EXECUTION():
    b = build()
    assert any("MISMATCH" in line for line in b.workspace.log)
    assert b.recovered


def test_a_repair_is_ATTRIBUTED_to_the_statement_that_is_actually_wrong():
    # THE multi-statement pin. Line 1 is wrong under the naive lowering; line 2 is ALREADY CORRECT.
    # A repair that merely "fixes the output" without knowing WHICH line is unmet would rewrite both
    # and break line 2. Attribution is by index, in the rule.
    b = build()
    body = [ln.strip() for ln in b.source.splitlines()[1:]]
    assert body == ["audit()", "print(greet(name))", "print(title)"]   # line 2 untouched
    assert b.stdout == ["hello_bob", "boss"] and b.ok

    # and structurally: only the unmet statement gained a new version.
    g = b.workspace.g
    by_index = {g.name(one(g, pr, "at")): pr for pr in of_kind(g, "emit_print")}
    assert {g.name(v) for v in many(g, by_index["i0"], "version")} == {"arg_v1", "arg_v2"}
    assert {g.name(v) for v in many(g, by_index["i1"], "version")} == {"arg_v1"}   # never repaired


def test_the_repair_is_monotone_and_the_superseded_version_survives():
    b = build()
    g = b.workspace.g
    by_index = {g.name(one(g, pr, "at")): pr for pr in of_kind(g, "emit_print")}
    assert current_versions(b.workspace)[by_index["i0"]] == "arg_v2"   # newest wins
    assert current_versions(b.workspace)[by_index["i1"]] == "arg_v1"   # its own current, unaffected


def test_current_is_ASKED_not_stored():
    # the monotone lesson: a materialized `current` cannot move — an earlier value survives forever and
    # the node ends up with two. So the working graph holds NO `current` fact; it is derived read-only.
    b = build()
    for pr in of_kind(b.workspace.g, "emit_print"):
        assert many(b.workspace.g, pr, "current") == []
    assert set(current_versions(b.workspace).values()) == {"arg_v1", "arg_v2"}


def test_the_projection_is_per_node_not_global():
    # repairing one statement must not strip an unrepaired sibling of its current version.
    g, ids = h.AttrGraph(), {}

    def node(n):
        if n not in ids:
            ids[n] = g.add_node(n)
        return ids[n]

    for s, p, o in [("p1", "is_a", "emit_print"), ("p1", "version", "arg_v1"),
                    ("p1", "version", "arg_v2"),                     # repaired
                    ("p2", "is_a", "emit_print"), ("p2", "version", "arg_v1"),   # NOT repaired
                    ("arg_v2", "supersedes", "arg_v1")]:
        g.add_relation(node(s), p, node(o))
    run_stratified(g, CURRENT)
    assert g.name(one(g, ids["p1"], "current")) == "arg_v2"
    assert g.name(one(g, ids["p2"], "current")) == "arg_v1"


def test_negation_over_a_DERIVED_fact_is_scheduled_correctly():
    # `satisfied` negates over the DERIVED `unmet_at`. Decided in the wrong order it is not merely
    # wrong but PERMANENTLY wrong, because the graph is monotone — this once reported a demonstrably
    # broken program as OK (ugm feedback #18).
    #
    # `run_bank` now stratifies by DEFAULT, so the hazard is gone at the source. The pin holds both
    # halves: the default is correct, and `stratified=False` (the raw one-stratum primitive) still
    # exhibits the old behaviour — which is what makes it clear the scheduling is doing the work.
    g, ids = h.AttrGraph(), {}

    def node(n):
        if n not in ids:
            ids[n] = g.add_node(n)
        return ids[n]

    for s, p, o in [("report", "is_a", "procedure"),
                    ("st0", "is_a", "step"), ("st0", "of_procedure", "report"),
                    ("st0", "at", "i0"), ("st0", "wants", "hello_bob"),
                    ("o0", "is_a", "observation"), ("o0", "at", "i0"), ("o0", "text", "bob")]:
        g.add_relation(node(s), p, node(o))

    raw = g.copy()
    h.run_bank(raw, h.load_machine_rules(VERDICT), stratified=False)  # the raw one-stratum primitive
    scheduled = g.copy()
    run_stratified(scheduled, VERDICT)                                # the default: stratified

    rep = lambda gr: [gr.name(t) for t in many(gr, gr.nodes_named("report")[0], "prints_ok")]
    assert rep(scheduled) == []              # correct: the expectation is unmet
    assert rep(raw) == ["yes"]               # unscheduled, the old hazard — what stratification buys


def test_a_structural_oracle_catches_a_program_that_FAKES_the_output():
    # The black-box oracle can be satisfied by a program that is right for the wrong reason: printing
    # the literal the spec expects for THIS input. The structural oracle READS the generated code
    # (intake -> BRIDGE -> the neutral `invokes`) and sees no call to `greet`.
    cheat = judge_source(SPEC, CHEAT_SOURCE)
    assert cheat["prints_ok"] is True            # the output oracle is fooled...
    assert cheat["structure_ok"] is False        # ...and the structural one is not
    assert cheat["satisfied"] is False           # the AND is a rule, not a Python `and`

    honest = judge_source(SPEC, build().source)
    assert honest == {"prints_ok": True, "structure_ok": True, "satisfied": True}


def test_the_structural_oracle_reads_the_code_through_the_BRIDGE():
    # the read half meeting the write half: intake parses the GENERATED source into its own
    # vocabulary, and the bridge lifts it into the vocabulary the requirement is authored in. Neither
    # side shares a predicate with the other.
    b = build()
    g = inspection_graph(b.workspace)
    run_stratified(g, ORACLES)
    assert of_kind(g, "call")                                    # intake's vocabulary is present
    invokers = [n for n in g.nodes() if many(g, n, "invokes")]    # ...lifted by the bridge
    assert any(g.name(one(g, n, "invokes")) == "greet" for n in invokers)
    assert "invokes" in INSPECTION and "calls_func" in INSPECTION
    assert "calls_func" not in SATISFIED          # the requirement never mentions intake's names


def test_a_structural_repair_fires_on_something_the_output_oracle_CANNOT_SEE():
    # The third repair shape: driven by READING the code, not by watching it run. `audit()` prints
    # nothing, so stdout is byte-identical before and after — no output-based loop could ever find it.
    b = build()
    log = "\n".join(b.workspace.log)

    # the telling moment: after the payload repair the output is ALREADY final, and the build is
    # still not satisfied, because the policy call is missing.
    assert "re-ran it -> ['hello_bob', 'boss'] => STILL WRONG" in log
    assert "repair_audit" in b.order

    body = [ln.strip() for ln in b.source.splitlines()[1:]]
    assert body == ["audit()", "print(greet(name))", "print(title)"]
    assert b.stdout == ["hello_bob", "boss"]      # ...the same output the previous step produced
    assert b.ok


def test_the_structural_repair_MINTS_A_STATEMENT_rather_than_revising_one():
    # the other repairs add a VERSION to an existing statement; this one adds a statement, and places
    # it by linking before whichever statement had no predecessor.
    b = build()
    g = b.workspace.g
    calls = of_kind(g, "emit_call")
    assert len(calls) == 1
    assert g.name(one(g, calls[0], "callee")) == "audit"
    heads = [s for s in calls if not any(calls[0] in many(g, o, "stmt_before")
                                         for o in of_kind(g, "emit_print"))]
    assert heads                                   # nothing precedes the policy call
    # and it is scoped: `greet` is required too, but is NOT a policy_call, so no bare `greet()` appears.
    assert "greet()" not in b.source


def test_declared_COSTS_order_the_recovery():
    """"Try the smallest edit first", authored purely as staged `cost` knowledge (ugm #20).

    This pin previously asserted the OPPOSITE — that ranking did not reach replan-selected
    alternatives. It was true when written and is now fixed upstream: `corpus/procedure.cnl` emits the
    rank call for the untried producers of an unmet effect and blocks each one that has a cheaper
    untried rival, so the cheapest is committed. (The symptom was also worse than we had measured:
    with no `cheaper_than` facts, `dominated`/`best` — the banks' ONLY narrowing criterion — had
    nothing to work with, so replan was not picking in staging order, it was picking EVERY untried
    producer at once.)

    Tested by INVERTING the declared costs and watching the CHOICE invert. That is the only honest way
    to test this: the default costs agree with staging order, so a passing default run is no evidence
    at all — which is exactly how the dead version of this tool looked alive.
    """
    import experiments.build_procedure as bp

    def repairs_under(costs):
        original = bp.STEPS
        try:
            bp.STEPS = tuple(bp.Step(s.name, s.adds, s.needs, cost=costs.get(s.name, s.cost))
                             for s in original)
            b = bp.build()
            return [o for o in b.order if o.startswith("repair")], b.ok
        finally:
            bp.STEPS = original

    cheap_greet, ok1 = repairs_under({"repair_greet": 1, "repair_audit": 2, "repair_shout": 3})
    cheap_audit, ok2 = repairs_under({"repair_audit": 1, "repair_greet": 2, "repair_shout": 3})
    assert cheap_greet[0] == "repair_greet"      # the declared-cheapest is committed first...
    assert cheap_audit[0] == "repair_audit"      # ...and inverting the costs inverts the choice
    assert ok1 and ok2                           # both orders still reach a verified program

    # the shipped costs encode "how much of the existing program does this edit disturb".
    assert {s.name: s.cost for s in STEPS if s.name in REPAIRS} == {
        "repair_greet": 1, "repair_audit": 2, "repair_shout": 3}


def test_the_rank_calculator_imposes_a_TOTAL_order():
    # ugm #20: a forward round collects all its matches before any fires, so two ops the calculator
    # leaves incomparable BOTH commit. Breaking ties is the calculator's job, not the bank's — so
    # equal-cost operators must still compare.
    #
    # What matters is that a tie yields EXACTLY ONE direction: zero directions and both rivals commit
    # (the #20 bug), both directions and the order is contradictory. WHICH one wins is arbitrary — the
    # costs say they are equally good, so there is nothing to be right about — and is deliberately NOT
    # pinned, so the tiebreak can change without a test failing for no reason.
    g, ids = h.AttrGraph(), {}

    def node(n):
        if n not in ids:
            ids[n] = g.add_node(n)
        return ids[n]

    for s, p, o in [("alpha", "cost", "c2"), ("beta", "cost", "c2")]:   # a TIE
        g.add_relation(node(s), p, node(o))

    from ugm.dispatch import call_arg as _ca
    handler = bp_rank()
    call = g.add_node("<call>")
    g.add_relation(call, "arg", ids["alpha"])
    handler(g, call)
    pairs = {(g.name(n), g.name(t))
             for n in g.nodes() for r, t in g.relations_from(n) if g.has_key(r, "cheaper_than")}
    assert (("alpha", "beta") in pairs) != (("beta", "alpha") in pairs)


def test_a_verified_build_ships_and_a_refused_one_does_not():
    ok = build()
    assert ok.refusal is None and ok.shipped == ok.source
    for spec in (SPEC_UNCOVERED, SPEC_UNREPAIRABLE):
        bad = build(spec)
        assert bad.refusal is not None
        assert bad.shipped is None          # never hand back an unverified program


def test_the_refusal_KIND_is_derived_by_rules_not_decided_in_python():
    # both flags come from the REFUSAL bank; Python only reads which one holds.
    uncovered = build(SPEC_UNCOVERED)
    d = uncovered.workspace.derived(REFUSAL)
    assert [d.name(t) for t in many(d, d.nodes_named("report")[0], "refused_uncovered")] == ["yes"]
    assert uncovered.refusal.kind == "uncovered"
    assert uncovered.refusal.missing == ("sort_line",)     # names the intent nothing expanded
    assert uncovered.order == ["expand"]                   # the chain stopped at the first step

    unverified = build(SPEC_UNREPAIRABLE)
    d2 = unverified.workspace.derived(REFUSAL)
    assert [d2.name(t) for t in many(d2, d2.nodes_named("report")[0], "refused_unverified")] == ["yes"]
    assert unverified.refusal.kind == "unverified"


def test_an_unrepairable_mismatch_refuses_AFTER_exhausting_every_repair():
    b = build(SPEC_UNREPAIRABLE)
    assert b.refusal.wanted == ("goodbye_bob",)
    assert set(REPAIRS) <= set(b.order)     # it really tried — every repair ran
    assert not b.ok and b.shipped is None


def test_two_repairs_COMPOSE_when_one_is_not_enough():
    # `HELLO_BOB` is unreachable by either recovery rule alone; the LOOP composes them, checked by
    # execution at each hop. This is the spec that was REFUSED before the second rule existed.
    b = build(SPEC_TWO_REPAIRS)
    # cost order is greet(1) -> audit(2) -> shout(3). `audit` is tried in between and does not apply
    # (this spec declares no policy call), which is what a cascade through cheaper alternatives looks
    # like: the loop spends a turn finding out, then moves on.
    tried = [o for o in b.order if o.startswith("repair")]
    assert tried == ["repair_greet", "repair_audit", "repair_shout"]
    assert tried.index("repair_greet") < tried.index("repair_shout")   # greet's repair is wrapped
    assert b.source.splitlines()[-1].strip() == "print(shout(greet(name)))"
    assert b.stdout == ["HELLO_BOB"] and b.ok and b.refusal is None
    pr = of_kind(b.workspace.g, "emit_print")[0]
    assert {b.workspace.g.name(v) for v in many(b.workspace.g, pr, "version")} == {
        "arg_v1", "arg_v2", "arg_v3"}
    assert current_versions(b.workspace)[pr] == "arg_v3"


def test_a_repair_does_not_run_once_the_goal_already_holds():
    # the actuator guard: once the goal is met, a later alternative producer must NOT fire and shout an
    # already-correct greeting, turning a passing build into a failing one.
    #
    # Uses a spec WITHOUT the policy requirement, so `repair_greet` alone satisfies everything — which
    # is exactly the situation the guard exists for. (Under the full SPEC the goal is still unmet after
    # `repair_greet`, because `audit` is missing, so the later repairs legitimately do get a turn.)
    spec = [f for f in SPEC if f[2] not in ("audit", "policy_call")]
    b = build(spec)
    assert b.order == ["expand", "lower", "emit", "check", "repair_greet"]
    assert "repair_shout" not in b.order and "repair_audit" not in b.order
    assert b.stdout == ["hello_bob", "boss"] and b.ok


def test_a_repair_declares_the_progress_it_makes_and_what_it_depends_on():
    greet_step = next(s for s in STEPS if s.name == "repair_greet")
    shout_step = next(s for s in STEPS if s.name == "repair_shout")
    assert "payload_greeted" in greet_step.adds      # progress is an observable effect...
    assert "payload_greeted" in shout_step.needs     # ...and the next repair's precondition


def test_the_current_projection_agrees_across_the_forward_and_demand_engines():
    # ugm #16 turned up a real bug here: a CONJUNCTIVE NAC was decided per-atom on the demand chain, so
    # a rule that derived correctly under `run_bank` returned nothing when ASKED. `CURRENT` is exactly
    # that shape, so pin both engines agreeing.
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
    run_stratified(forward, CURRENT)
    assert forward.name(one(forward, ids["p1"], "current")) == "arg_v2"
    assert forward.name(one(forward, ids["p2"], "current")) == "arg_v1"

    assert h.ask_goal(g.copy(), "is p1 current arg_v2", rules) == ["yes"]
    assert h.ask_goal(g.copy(), "is p2 current arg_v1", rules) == ["yes"]
    assert h.ask_goal(g.copy(), "is p1 current arg_v1", rules) != ["yes"]   # superseded


def test_the_generated_line_is_explainable_back_to_the_observed_run():
    # provenance over GENERATED code (ugm #15), addressed by definite description because the substrate
    # is nameless: the repair on line 1 threads back through the rule that minted it.
    from ugm import ByDesc
    b = build()
    trace = h.ask_goal(b.workspace.g,
                       ("why", ByDesc("pr", (("at", "i0"),)), "version", "arg_v2"),
                       h.load_machine_rules(RECOVERY), provenance=True)
    assert any("<- rule" in line for line in trace)        # threaded a rule, not "(given)"
