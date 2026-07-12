"""Demo 3 - a Session: several functions in ONE graph, value flow across a call boundary.

A Session holds several functions in one shared UGM graph. Identity is by `(function,
source_name)`, so two functions that both use a variable `p` are DISTINCT nodes - no name
mangling. Each function is analyzed under its own focus (cost tracks the function, not the whole
graph) and detection is read-only, so functions and hypotheses never contaminate one another.

The payoff: a `call` in one function is wired to the callee's parameter, so a value HYPOTHESIZED
about the caller's input flows across the boundary and surfaces as an outcome INSIDE the callee -
with a single trace threading the whole path.

    python demos/03_session_interprocedural.py
"""
from _util import banner, show_source, show_trace, try_changing

from pystrider import Session


CALLER = """
def handle(request):
    return render(request)
"""

CALLEE = """
def render(page):
    return page.title()
"""


def main() -> None:
    banner("1. TWO FUNCTIONS IN ONE SHARED GRAPH")
    show_source(CALLER)
    print()
    show_source(CALLEE)

    sess = Session()
    sess.add_function(CALLER)
    sess.add_function(CALLEE)
    print(f"\n  shared graph now holds both functions; `render`'s param `page` and any other "
          f"function's `page` are DISTINCT nodes (identity is (function, source_name)).")

    banner("2. WIRE THE CALL  ->  caller's argument flows into the callee's parameter")
    for caller, callee, param in sess.link_calls():
        print(f"    linked: {caller}(...) -> {callee},  argument wired to param `{param}`")

    banner("3. SUPPOSE the CALLER's input is None  ->  outcome surfaces INSIDE the callee")
    outs = sess.analyze_across_call("handle", {"request": "none"}, "render")
    for o in outs:
        print(f"    OUTCOME: {o.label} (line {o.line}) -> AttributeError, inside `render`")
        print("    trace (value threads caller-cell -> call link -> callee-cell -> deref):")
        show_trace(o.trace, indent="      ")

    banner("4. SOUNDNESS & ISOLATION")
    clean = sess.analyze_across_call("handle", {"request": "object"}, "render")
    print("  caller input = <object> ->", clean or "no outcome  (value flow is sound)")
    print("  the shared graph was never inked (read-only detection), so re-analysis under a new")
    print("  hypothesis is uncontaminated - analyze `render` alone under page = object:",
          sess.analyze("render", {"page": "object"}) or "clean")

    try_changing(
        "* Add a THIRD function `page_of(x): return x` and have `render` call it - chain the flow.",
        "* Before `link_calls()`, run step 3: with no link there is NO phantom flow (returns []).",
        "* Give the callee a guard `if page is not None:` - the cross-call outcome disappears.",
    )


if __name__ == "__main__":
    main()
