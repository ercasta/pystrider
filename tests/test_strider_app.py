"""Slice 7 — a goal derives a real Textual app, and the app is trusted because it is driven.

The reasoning lives in `experiments/strider_app.py`'s docstring. These pin the claims it makes, and for
every green here the question was asked: WHAT WOULD MAKE THIS VACUOUS? Several of them exist only as the
answer to that question, and two are controls whose whole value is that they must go the other way.
"""
from __future__ import annotations

import ast

import pytest

import strider
from experiments import strider_app as A
from strider.lift import reachable
from strider.mf import driver, function, types

textual = pytest.importorskip("textual", reason="the drive needs the real toolkit")


# --- the authored code is inside the membrane ------------------------------------------------------------

def test_skeleton_and_every_fragment_are_fully_modelled():
    """No fragment is `partial`, so none is spliced in half-read.

    ⚠ This is not a formality: `strider.emit` refuses a partial node, so an unmodelled construct anywhere
    in the authored Python would surface as a refusal at emit time with no indication of which fragment
    caused it. Failing here names the file."""
    lib = strider.load()
    for label, source in (("skeleton", A.SKELETON), *A.FRAGMENTS.items()):
        got = strider.intake(lib, source, origin=label)
        assert got.complete, f"{label} is not fully modelled: {got.unmodelled}"


def test_compose_needs_yield_and_yield_is_what_slice_7_added():
    """The control for the reach widening: without `Yield`, the app-generation ending is blocked outright.

    A `compose` method is a generator, so one unmodelled expression made every Textual app partial. Pinned
    by removing it from the modelled set and watching the skeleton go partial."""
    lib = strider.load()
    assert strider.intake(lib, A.SKELETON, origin="skeleton").complete

    lib2 = strider.load()
    intake = strider.intake.__module__
    walker = __import__(intake, fromlist=["Intake"]).Intake(lib2, "no-yield")
    delattr_target = walker.__class__
    saved = delattr_target._Yield
    try:
        del delattr_target._Yield
        got = strider.intake(lib2, A.SKELETON, origin="skeleton")
        assert not got.complete
        assert any(name == "Yield" for name, _line in got.unmodelled)
    finally:
        delattr_target._Yield = saved


def test_yield_round_trips_through_text():
    """Read and write are separate capabilities, so the widening is checked in both directions."""
    lib = strider.load()
    source = "def compose(self):\n    yield Input(id='amount')"
    got = strider.intake(lib, source, origin="t")
    assert got.complete
    assert strider.emit(lib, got.module) == source


# --- the plan IS the derivation ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def derived():
    """Every cart, derived once — the search is the slow part and nothing here mutates the result."""
    return {label.strip(): A.derive(cart) for label, cart in A.CARTS}


def test_the_same_goal_yields_four_different_plans(derived):
    """⭐ THE CLAIM. One library, one goal, four carts, four derivations.

    ⚠ THE CONTROL IS THE POINT: if every cart produced the same plan, everything downstream would still be
    green — the app would emit, drive and pass its contracts — while the knobs did nothing at all. So what
    is pinned is that the plans DIFFER, not that they succeed."""
    plans = {label: tuple(out["plan"]) for label, out in derived.items()}
    assert all(plans.values()), f"a cart failed to find a plan: {plans}"
    assert len(set(plans.values())) == 4, f"the knobs did not change the derivation: {plans}"


def test_the_goal_never_mentions_a_feature():
    """The goal asks for a displayed result and a completed checkout — never for a discount or a gate.

    Otherwise the derivation would be a lookup: naming the wanted features in the goal makes the types
    decorative and the plan a restatement of the question."""
    lib, build, _module = A.setup()
    g = lib.graph
    goal = A.build_goal(g, build)
    described = " ".join(G_describe(g, c) for c in __import__(
        "microfunctions.goal", fromlist=["constraints"]).constraints(g, goal))
    for feature in ("discount", "gate", "confirm", "highlight"):
        assert feature not in described.lower(), f"the goal names {feature!r}: {described}"


def G_describe(g, c):
    from microfunctions import goal as GG
    return GG.describe_constraint(g, c)


def test_the_dependency_order_is_rediscovered_not_declared(derived):
    """`qualify` before `grant_discount` before `install_discount_display`, in every plan that has them.

    Nothing states that order. It falls out of `grant_discount(b: qualified_build)` being unproposable
    until `qualify` has written `qualifies`, which is what replaces forward chaining.

    ⚠ Pinned as a RELATIVE order, not an absolute one. `install_gated_finish` depends on nothing and the
    planner puts it first — a plan is *a* valid order, and demanding a specific one would pin the search's
    tie-breaking rather than the dependency it actually derived."""
    for label, out in derived.items():
        plan = list(out["plan"])
        if "grant_discount" not in plan:
            continue
        assert plan.index("qualify") < plan.index("grant_discount"), label
        assert plan.index("grant_discount") < plan.index("install_discount_display"), label


def test_an_unqualified_cart_can_never_reach_the_discount(derived):
    """The negative half: no plan grants a discount to a cart that did not earn it."""
    for label, out in derived.items():
        cart = out["cart"]
        entitled = cart.tier == "premium" and cart.spend >= cart.threshold
        granted = "grant_discount" in out["plan"]
        assert granted == entitled, f"{label}: granted={granted} entitled={entitled}"


def test_the_decision_rewrites_the_code_not_a_flag(derived):
    """`grant_discount` edits the skeleton's own `APPLIES = False` constant.

    So there is no separate apply-the-decisions pass that could disagree with the decisions. Read off the
    EMITTED TEXT rather than the graph, because the graph is where we wrote it and the text is what runs."""
    for label, out in derived.items():
        cart = out["cart"]
        entitled = cart.tier == "premium" and cart.spend >= cart.threshold
        assert f"APPLIES = {entitled}" in out["source"], label


# --- the emitted artifact ---------------------------------------------------------------------------------

def test_the_emitted_source_is_valid_python_and_defines_the_app(derived):
    for label, out in derived.items():
        tree = ast.parse(out["source"])            # by construction, via ast.unparse — never by inspection
        names = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        assert "CheckoutApp" in names, label


def test_the_confirm_screen_appears_exactly_when_the_checkout_is_irreversible(derived):
    """⭐ The README's flip: change one knob and the screen shape changes, forced rather than chosen."""
    for label, out in derived.items():
        tree = ast.parse(out["source"])
        classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        assert ("ConfirmScreen" in classes) == out["cart"].irreversible, label


def test_every_seam_is_filled_exactly_once(derived):
    """Two fragments for one seam would both be spliced and the second would silently win."""
    for label, out in derived.items():
        body = next(n for n in ast.parse(out["source"]).body
                    if isinstance(n, ast.ClassDef) and n.name == "CheckoutApp").body
        methods = [n.name for n in body if isinstance(n, ast.FunctionDef)]
        assert methods.count("_present") == 1, f"{label}: {methods}"
        assert methods.count("_finish") == 1, f"{label}: {methods}"


def test_the_emitted_code_carries_the_decorator_and_the_class_base(derived):
    """`@on(Button.Pressed, '#checkout')` and `class CheckoutApp(App)` — the constructs slice 5 unblocked,
    checked on a real artifact rather than on a synthetic example."""
    source = derived["premium, 150, IRREVERSIBLE"]["source"]
    assert "@on(Button.Pressed, '#checkout')" in source
    assert "class CheckoutApp(App):" in source
    assert "class ConfirmScreen(ModalScreen):" in source


def test_the_fragments_arrive_as_parsed_artifacts_not_as_text():
    """`from_code` on a spliced method — the property that makes this composition rather than concatenation.

    A consumer asking "does this app show a discount" must be answered about the ARTIFACT. If the splice
    had been a string append there would be nothing to ask."""
    out = A.derive(A.Cart("premium", 150, 100, False))
    g = out["lib"].graph
    block = g.target(next(n for n in reachable(out["lib"], out["module"])
                          if g.kind(n) == "class_def"), "does")
    spliced = [s for s in g.targets(block, "stmt")
               if g.kind(s) == "function_def" and g.attr(s, "name") == "_present"]
    assert len(spliced) == 1
    assert g.attr(spliced[0], "from_code") is True
    assert g.attr(spliced[0], "origin") == "fragment discount_display"


# --- reality: the drive -----------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def driven(derived):
    return {label: A.drive(out) for label, out in derived.items()}


def test_every_derived_app_actually_works_when_driven(driven):
    """⭐ The independent gate. Not "it emitted" — it ran, under the real toolkit, and did what it should."""
    for label, d in driven.items():
        assert d.works, f"{label}: safe={d.safe} live={d.live} shown={d.shown} events={d.events}"


def test_the_gate_is_observed_before_completion_not_merely_present(driven):
    """SAFETY as an ORDER over observed events. A `ConfirmScreen` in the source proves nothing about when
    it ran — an app could show the gate after completing and still contain the class."""
    for label, d in driven.items():
        if not d.events or "gate_shown" not in d.events:
            continue
        assert d.events.index("gate_shown") < d.events.index(
            next(e for e in d.events if e.startswith("completed"))), label


def test_the_discount_is_observed_as_behaviour_not_as_a_claim(driven, derived):
    """HONESTY: when the business granted a discount, the running app showed it AND highlighted it."""
    for label, d in driven.items():
        cart = derived[label]["cart"]
        if not (cart.tier == "premium" and cart.spend >= cart.threshold):
            continue
        assert any(e.startswith("discount_shown") for e in d.events), label
        assert "highlighted" in d.events, label


def test_the_discounted_price_is_what_the_running_app_charged(driven, derived):
    """The arithmetic is the emitted code's, never the derivation's — the ISA has no multiplication and
    was never asked to price anything. Read the number the app actually completed at."""
    d = driven["premium, 150, reversible"]
    assert "completed 120.0" in d.events        # 150 less 20%
    assert "completed 150.0" in driven["basic,   150, reversible"].events


# --- the controls: what would make the greens above vacuous ------------------------------------------------

def test_relaxing_the_safety_type_produces_an_unsafe_app_that_the_drive_catches():
    """⭐⭐ THE CONTROL FOR SAFETY, and without it `test_every_derived_app_actually_works` measures nothing.

    Safety here is carried entirely by `install_direct_finish(b: reversible_build)`: an irreversible build
    does not fit, so the ungated app is UNBUILDABLE rather than detected. That guarantee is exactly as good
    as the type. Break the type, force the direct finish, and the drive reports an irreversible checkout
    that completed with no gate — proving the drive would have caught it, and therefore that the passing
    case was a test and not a tautology."""
    broken = A.unsafe_without_the_type()
    d = broken["driven"]
    assert d.completed, "the control did not even complete, so it tests nothing"
    assert "gate_shown" not in d.events
    assert not d.safe, f"the unsafe app was reported safe: {d.events}"


def test_the_unsafe_app_is_unreachable_while_the_type_holds():
    """The other side of the control, in the two parts it actually has.

    ⚠ THIS PIN CORRECTED THE CLAIM IT WAS WRITTEN TO CONFIRM. It first asserted that invoking the direct
    finish on an irreversible build would raise, and it did not: `function.invoke` does not check parameter
    types. A parameter type binds `driver.proposals` — it is a PLANNING constraint, and calling the
    operation directly walked straight past it. So what is pinned now is both halves separately, and
    `app.mf` grew the explicit `CHECK` that makes the second one true."""
    lib, build, _module = A.setup(A.Cart("premium", 150, 100, True))
    g = lib.graph
    assert not types.is_a(g, build, "reversible_build")

    # 1. NO PLAN reaches it: the operation is not among the proposals for this build.
    from microfunctions import workbench as W
    frame = W.root_frame(g, W.open_workbench(g, build, label="proposal probe"))
    offered = {name for name, _bindings in driver.proposals(g, frame)}
    assert "install_gated_finish" in offered, "the safe route must still be available"
    assert "install_direct_finish" not in offered

    # 2. NO CALL reaches it either — but only because `CHECK` is in the body, not because of the signature.
    with pytest.raises(types.TypeViolation):
        function.invoke(g, "install_direct_finish", {"b": build})


def test_a_missing_operation_refuses_rather_than_emitting_a_half_app():
    """The membrane, pointing at the planner. Withhold the only op that can fill a seam and the search must
    come back empty — never with an app missing a method it will call at run time.

    ⚠ Checked as `found is falsy AND no source`, because a search that reports failure while having already
    mutated the graph would be the worse outcome and would pass a check on `found` alone."""
    lib, build, module = A.setup(A.Cart("premium", 150, 100, True))
    g = lib.graph
    goal = A.build_goal(g, build)
    from microfunctions import thread as T

    report = driver.pursue(g, goal, T.open_thread(g, "crippled"), build,
                           allow=lambda name: name != "install_gated_finish")
    assert not report.get("found")
    assert g.attr(build, "finishes") is None

    # ⚠ `def _finish`, not `_finish`. The skeleton CALLS `self._finish(total)` unconditionally — that call
    # is the seam and it is always there. Asserting on the bare name passed for the wrong reason and would
    # have gone on passing if the fragment had been spliced. What must be absent is the DEFINITION.
    assert "def _finish" not in strider.emit(lib, module)


def test_the_seam_collision_that_the_drive_found_would_still_be_invisible_structurally():
    """⭐ The finding, pinned as a fact about the METHOD rather than as a regression test for the name.

    `_display` is one of Textual's own private `App` methods. An emitted app overriding it parses, round
    trips byte-exactly, satisfies every contract we can express about our own graph — and crashes on the
    first repaint. What this pins is that structure genuinely cannot see it: the collision is a property of
    code we do not own, so the seam name must be checked against the real base class, by execution.

    If Textual ever grows an `App._present`, this goes red and the seam must be renamed — which is the
    correct behaviour, and the reason the check reads the live class instead of a remembered list."""
    from textual.app import App
    assert hasattr(App, "_display"), "the collision this records is gone; the lesson is not"
    for seam in ("_present", "_finish"):
        assert not hasattr(App, seam), f"{seam} now collides with Textual's own API"
