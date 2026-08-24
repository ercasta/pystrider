"""Slice 2b's pins — the repair the corpus MEANT, not the one rank gave it.

The narrative version with its printed evidence is
`experiments/restrider_attention.py`.

⚠ Read `conftest.py` first: this suite runs in its own pytest invocation.

⚠⚠ **THE CONTROLS ARE THE POINT OF THIS FILE, NOT THE POSITIVE ARM.** Attending the
right node and attending nothing at all produce the same green result whenever the
table's rank already agrees — which is the state slice 2 shipped in, and is why
this defect survived a green suite. So every positive pin below is paired with a
declaration-order swap, and the swap is asserted to move something on its own.
"""
from __future__ import annotations

import pytest

from restrider import corpus
from restrider.emit import emit
from restrider.evaluator import register
from restrider.facts import Facts
from restrider.intake import intake
from restrider.mf import PLUS

BUG = "def classify(age):\n    if age > 18:\n        return 'adult'\n    return 'minor'\n"

AUTHORED = "after <boundary> => attend(?o, 1)"
RIVAL = "after <boundary> => attend(?r, 1)"

RELAXED = "if age >= 18:"
LOWERED = "if age > 17:"


def _drop(text: str, name: str) -> str:
    """Remove one rule by name, paren-counted. ⚠ Never cut on the first `)`."""
    start = text.index(f"rule <{name}>")
    i, depth = text.index("(", start), 0
    while True:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return text[:start] + text[i + 1:]


def live() -> str:
    return corpus("patterns", "repair")


def unpoliced(text: str) -> str:
    """The corpus as slice 2 shipped it — no `<boundary>`, no postcondition."""
    text = _drop(text, "boundary")
    return "\n".join(l for l in text.splitlines() if not l.startswith("after <boundary>"))


def swapped(text: str) -> str:
    """Declare `<lower>` before `<relax>`. The instrument, and nothing else moves."""
    i, j = text.index("rule <relax>"), text.index("rule <lower>")
    return text[:i] + text[j:] + "\n" + text[i:j]


def repair(rules: str, scope: str, given=18, wants="adult") -> dict:
    f = Facts(rules, scope=scope)
    taken = intake(BUG, f, "<test2b>")
    function = f.subjects("function")[0]
    case = f.node("case")
    f.fact("case", case)
    f.fact("given", case, f.value(given))
    f.fact("wants", function, case, f.value(wants))
    register(f)
    f.run()
    goal = f.g.rel(f.rel("agrees"), function, case)
    f.m.gate.write(f.m.focus, f.g.rel(f.m.GOAL, goal), PLUS, mention=True)
    f.run(limit=8000)
    return {
        "family": "lower" if f.subjects("lowered")
                  else ("relax" if f.subjects("relaxed") else "none"),
        "guard": emit(f, taken.module).strip().splitlines()[1].strip(),
        "holds": f.m.holds(goal),
        "policy_fired": bool(f.subjects("boundary")),
    }


# -- the defect the policy exists for -------------------------------------------


def test_WITHOUT_a_policy_the_artefact_is_a_function_of_DECLARATION_ORDER():
    """⚠ The pin that could not have existed before: both columns are correct
    repairs, and nothing in the corpus chose between them."""
    bare = unpoliced(live())
    assert repair(bare, "d1")["guard"] == RELAXED
    assert repair(swapped(bare), "d2")["guard"] == LOWERED


def test_CONTROL_both_declaration_orders_genuinely_repair_the_bug():
    """Neither column is a failure — that is what makes the choice a choice."""
    bare = unpoliced(live())
    assert repair(bare, "d3")["holds"] == PLUS
    assert repair(swapped(bare), "d4")["holds"] == PLUS


# -- the policy -----------------------------------------------------------------


@pytest.mark.parametrize("order", ["as written", "swapped"])
def test_WITH_the_policy_the_same_artefact_under_EITHER_order(order):
    text = live() if order == "as written" else swapped(live())
    assert repair(text, f"p{order[:3]}")["guard"] == RELAXED


def test_the_policy_FIRED_and_it_is_the_case_naming_the_boundary_that_fires_it():
    assert repair(live(), "p2")["policy_fired"]


def test_the_policy_is_SILENT_when_the_case_does_not_name_the_boundary():
    """⚠ What this cannot show, said rather than implied: for this bug 18 is the
    only disagreeing case, so a repair WITHOUT the coincidence is not reachable
    from this fixture. Silence is pinned; silence-with-a-repair is not."""
    out = repair(live(), "p3", given=25)
    assert not out["policy_fired"]
    assert out["family"] == "none"


# -- another author disagrees, in one line --------------------------------------


@pytest.mark.parametrize("order", ["as written", "swapped"])
def test_THE_RIVAL_POLICY_takes_the_other_family_and_is_stable_too(order):
    """⭐ One authored line, the other artefact — and stable under the swap, which
    is what distinguishes a policy from agreeing with rank by luck."""
    text = live() if order == "as written" else swapped(live())
    assert repair(text.replace(AUTHORED, RIVAL), f"r{order[:3]}")["guard"] == LOWERED


def test_CONTROL_the_two_policies_differ_by_exactly_one_word():
    a, b = live().split(), live().replace(AUTHORED, RIVAL).split()
    assert sum(1 for x, y in zip(a, b) if x != y) == 1


# -- ⚠⚠ the two ways to attend nothing, both silent -----------------------------


@pytest.mark.parametrize("var", ["?f", "?g", "?c"])
def test_a_node_BOTH_families_bind_discriminates_NOTHING(var):
    """Upstream's *attention that names everything discriminates nothing*, in the
    smallest form there is: everything is two. Rank decides again, silently."""
    text = swapped(live()).replace(AUTHORED, f"after <boundary> => attend({var}, 1)")
    assert repair(text, f"s{var[1]}")["guard"] == LOWERED


def test_attending_a_CONTAINER_is_attending_nothing_and_it_does_not_ANNOUNCE_it():
    """⚠⚠ The survey's own probe attended the function's body block and read the
    null result as *attention buys us nothing on the recognition half* — for a full
    cycle. The lift reads the nodes an APPLICATION binds, and no repair family
    binds the block its guard sits in."""
    text = swapped(live()).replace(
        "{ +wants(?f, ?c, ?v),", "{ +wants(?f, ?c, ?v), +body(?f, ?bl),"
    ).replace(AUTHORED, "after <boundary> => attend(?bl, 1)")
    assert "+body(?f, ?bl)" in text and "attend(?bl, 1)" in text   # the edit is real
    out = repair(text, "sbl")
    assert out["guard"] == LOWERED
    assert out["policy_fired"], "and the trail looks exactly like the working one"


def test_CONTROL_the_node_exactly_ONE_family_binds_is_the_one_that_moves_it():
    """The positive arm of all four above — without it they pin only inertia."""
    assert repair(swapped(live()), "sok")["guard"] == RELAXED
