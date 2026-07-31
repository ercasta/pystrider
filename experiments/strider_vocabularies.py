"""SLICE 4 — three independently-authored vocabularies compose, WITHOUT forward chaining.

This is the README's headline claim carried onto the new engine: business rules, UX rules and a widget
toolkit each stay in their own file and their own vocabulary, one bridge crosses between them, and
changing any block re-derives the rest. The old version rested on **forward chaining** — CNL rules that
fired wherever the world matched, saturating the graph, after which you asked an open question:

    ?cart grants_discount yes when ?cart customer_tier premium and ?cart order_qualifies yes
    who admitted_for cart

**Microfunctions are POINTED. Nothing fires.** So the question this slice answers is what replaces that,
now that the project has adopted the goal-driven approach.

**⭐ THE ANSWER: a rule's CONDITION becomes its PARAMETER TYPE, and saturation becomes PLANNING.**
`grant_discount(c: qualified_cart)` is proposable only against a cart that already qualifies — so the
dependency the old engine discovered by firing to fixpoint is the same dependency the planner discovers
by chaining return types into parameter types. Nothing orders the blocks; the types do.

**⭐⭐ AND THE PLAN *IS* THE DERIVATION — which is strictly better than what it replaces.** Forward
chaining leaves you a saturated graph and the job of reconstructing *why* a fact is there. Here the chain
that established the goal is the returned plan: an ordered, inspectable list of which rule from which
vocabulary fired, in what order, to make this true. The README's "with the reasoning auditable" stops
being a feature somebody had to build and becomes the shape of the answer.

**⚠ THE HONEST COST, stated because it is real.** Forward chaining derives EVERY consequence, so an open
question (`who admitted_for cart`) is a lookup. Goal-directed planning derives only what a goal needs, and
`goal.py` constrains *named individuals* — there is no quantifier. So an open question becomes **one goal
per candidate**, which is N searches rather than one saturation. `open_question` below does exactly that
and reports the cost, rather than hiding it behind an API that looks like a lookup.

Run it: `python -m experiments.strider_vocabularies`
"""
from __future__ import annotations

from pathlib import Path

from strider.library import Library
from strider.mf import asm, driver, goal as G, new_graph, types

VOCABULARIES = Path(__file__).resolve().parent / "vocabularies"

#: What the toolkit can do. Swap this and the same business and UX blocks retarget — or honestly fail to.
TEXTUAL = {"styled_label": True, "modal_confirm": True, "input_value": True, "button_widget": True}

#: A toolkit that cannot gate an irreversible action. Used to show the failure is honest, not silent.
BARE = {"styled_label": True, "input_value": True}


def declare(g) -> None:
    """The types that make the vocabularies chain. **This is where a rule's CONDITION now lives.**

    Each type is the precondition of the rule that consumes it, so a rule becomes applicable exactly when
    the old CNL body would have matched — except that the planner can now *search* over it instead of the
    engine having to saturate."""
    types.declare_type(g, "cart", {"policy": ("policy", 1), "library": ("library", 1)})
    types.declare_type(g, "priced_cart", base="cart")
    types.declare_type(g, "checked_cart", base="cart", attrs={"order_checked": True})
    types.declare_type(g, "qualified_cart", base="cart", attrs={"order_qualifies": True})
    types.declare_type(g, "discounting_cart", base="cart", attrs={"grants_discount": True})
    types.declare_type(g, "ux_specified_cart", base="cart")
    types.declare_type(g, "wants_highlight", base="cart", attrs={"requires_highlighted_discount": True})
    types.declare_type(g, "wants_confirmation", base="cart", attrs={"requires_confirmation_step": True})
    types.declare_type(g, "admitted_cart", base="cart")
    types.declare_type(g, "irreversible_cart", base="cart", attrs={"action_irreversible": True})


def world(*, amount=150, tier="premium", irreversible=True, toolkit=TEXTUAL, threshold=100):
    """One cart, one policy, one library — each block's facts, in each block's own terms."""
    g = new_graph()
    names = asm.load_dir(g, VOCABULARIES)
    lib = Library(g, (), (), tuple(sorted(names)))
    declare(g)

    policy = g.mint("policy", threshold=threshold, rate=10)
    toolkit_node = g.mint("library", **toolkit)
    cart = g.mint("cart", amount=amount, customer_tier=tier, action_irreversible=irreversible)
    g.link(cart, "policy", policy)
    g.link(cart, "library", toolkit_node)
    g.link("root", "has", cart)
    return lib, cart


def ask(lib, cart, key, *, max_depth=6, **kw) -> dict:
    """Ask ONE question, goal-directed: can `key` be made true for this cart?

    Returns the verdict, the derivation chain that established it, and what it cost."""
    from microfunctions import thread as T
    g = lib.graph
    goal = G.open_goal(g, about=cart, label=f"{key} for this cart")
    G.require_attr(g, goal, cart, key, True)
    report = driver.pursue(g, goal, T.open_thread(g, f"ask:{key}"), cart, max_depth=max_depth, **kw)
    return {"answered": bool(report.get("found")),
            "derivation": driver.plan_steps(g, report) if report.get("found") else (),
            "imagined": report.get("steps"),
            "report": report}


def why_not(lib, cart, report, markers=("unsupported_confirmation_step",
                                        "unsupported_highlighted_discount",
                                        "order_qualifies")) -> dict:
    """⚠ **A REGRESSION OF THE GOAL-DRIVEN APPROACH, and how to get back what it costs.**

    Forward chaining saturated the REAL graph, so after a failure the diagnosis was simply lying there:
    the cart said `requires_feature confirmation_step` and nothing said `realized_by`, and you could read
    why. Goal-directed planning does all its reasoning on workbench copies, and a failed search discards
    them — so `pursue` answers "no plan found", which is true and useless. `blocked_by` and `refused` are
    both empty here, because nothing was *forbidden*; the goal was simply never established.

    But the frames are ordinary graph nodes and they still exist. The bridge DID run, and DID record that
    the toolkit lacks the capability — on a frame nobody looks at. So the reasoning is recoverable by
    reading the imagined worlds rather than the real one, which is what this does.

    **The lesson worth carrying: on this substrate a refusal has to be RETRIEVED from imagination, never
    read off the world.** Any operation that wants to explain itself must record the reason where the
    frames are, and something must go and look."""
    from microfunctions import workbench as W
    g = lib.graph
    findings: dict = {}
    for frame in W.frames(g, report["workbench"]):
        for m in W.mappings(g, frame):
            if W.resolve(g, m) != cart:
                continue
            image = W.image_of(g, m)
            for marker in markers:
                value = g.attr(image, marker)
                if value is not None:
                    findings.setdefault(marker, set()).add(value)
    return {k: sorted(v) for k, v in findings.items()}


def open_question(lib, cart, candidates, **kw) -> dict:
    """⚠ The open question, and its honest price.

    Forward chaining answered `who admitted_for cart` by looking at a saturated graph. Goal-directed
    planning has no quantifier, so this is one search per candidate. The cost is REPORTED — a wrapper that
    looked like a lookup would hide that N searches happened."""
    answers, cost = {}, 0
    for key in candidates:
        got = ask(lib, cart, key, **kw)
        answers[key] = got["derivation"] if got["answered"] else None
        cost += got["imagined"] or 0
    return {"admitted": {k: v for k, v in answers.items() if v is not None},
            "refused": [k for k, v in answers.items() if v is None],
            "searches": len(candidates), "imagined_total": cost}


ADMISSIONS = ("admitted_highlighted_discount", "admitted_confirmation_step")


def main() -> None:
    print("=== a premium cart over the threshold, on a toolkit that can do everything ===")
    lib, cart = world()
    for key in ADMISSIONS:
        got = ask(lib, cart, key)
        print(f"  {key}")
        print(f"     answered  : {got['answered']}   (imagined {got['imagined']} states)")
        print(f"     derivation: {' -> '.join(got['derivation']) or '—'}")

    print("\n=== the same blocks, a toolkit that CANNOT gate an irreversible action ===")
    lib2, cart2 = world(toolkit=BARE)
    got = ask(lib2, cart2, "admitted_confirmation_step")
    print(f"  answered: {got['answered']}  <- honest refusal, not a wrong answer")
    print(f"  why not : {why_not(lib2, cart2, got['report'])}")
    print(f"  the REAL graph knows: {cart2 and lib2.graph.attr(cart2, 'unsupported_confirmation_step')}"
          "  <- nothing; the reasoning happened in imagination and had to be retrieved")

    print("\n=== the same blocks, a cart that does not qualify (below threshold) ===")
    lib3, cart3 = world(amount=50)
    got = ask(lib3, cart3, "admitted_highlighted_discount")
    print(f"  answered: {got['answered']}  <- the business block alone changed the UI")
    print(f"  why not : {why_not(lib3, cart3, got['report'])}")

    print("\n=== the open question, and what it costs ===")
    lib4, cart4 = world()
    out = open_question(lib4, cart4, ADMISSIONS)
    print(f"  admitted: {sorted(out['admitted'])}")
    print(f"  refused : {out['refused']}")
    print(f"  cost    : {out['searches']} searches, {out['imagined_total']} imagined states "
          "(forward chaining would have been one saturation)")


if __name__ == "__main__":
    main()
