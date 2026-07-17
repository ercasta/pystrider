"""The base tier — the UNNAMED residual is still operable and reusable, no concept required.

`understand_curve` / `understand_partial` found that ~half of real loops carry no known value-concept.
The pessimistic reading is "the membrane must handle them." This probe shows that reading is wrong: a
loop with NO named concept is still fully handled at the BASE TIER — the same base tier the footprint work
already lives at. Two demonstrations over real code:

  1. FOOTPRINT the residual. For every stdlib loop that has NO recognized value-aspect (the "unnamed"
     residual), derive a base-tier effect summary — what it iterates, binds, reads (its free inputs),
     writes, and calls — straight from the AST. Naming is 0%; footprinting is ~100%. The residual is not
     a black hole; it is base-tier code whose effect is derivable without a concept.

  2. REUSE the residual as a BLACK-BOX FRAGMENT. Take a genuinely bespoke loop (a line-continuation
     joiner — no `sum`/`map`/`filter` name fits it), derive its interface (inputs = free reads, produces
     = writes) WITHOUT naming what it means, and invoke it on real input as an opaque parameterized block.
     Reuse needs an interface, not a name.

The point: understanding is not naming. Named concepts are a compression layer (shortcut + property
certificate) over a base tier that is complete on its own — execute it, footprint it, reuse it by its
derived interface. So the "membrane" is not the unnamed residual; it is intent→spec ambiguity, plus
optionally proposing a name when compression/reuse is worth it. See `docs/understanding_findings.md`.

Run it: `python -m experiments.base_tier`
"""
from __future__ import annotations

import ast
import glob
import os

from experiments.understand_curve import scan_corpus
from experiments.understand_partial import leaf_aspects, VALUE_ASPECTS

# collection-mutating methods: the receiver is WRITTEN; any other call is an external effect.
_MUTATORS = {"append", "add", "extend", "update", "insert", "appendleft", "discard", "pop",
             "popleft", "setdefault", "clear", "sort", "remove", "__setitem__"}


def _target_names(t: ast.AST) -> "set[str]":
    """The written names of one assignment target, decorated (`d[]`, `o.attr`) for display."""
    if isinstance(t, ast.Name):
        return {t.id}
    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
        return {t.value.id + "[]"}
    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
        return {t.value.id + "." + t.attr}
    if isinstance(t, (ast.Tuple, ast.List)):
        return set().union(*(_target_names(e) for e in t.elts)) if t.elts else set()
    return set()


def footprint(fs: ast.For) -> dict:
    """A base-tier effect summary of ANY loop — no concept name needed. Derived purely from the AST:
    what it iterates over, binds, reads (its free inputs), writes, and calls (external effects)."""
    binds = {n.id for n in ast.walk(fs.target) if isinstance(n, ast.Name)}
    iters = {n.id for n in ast.walk(fs.iter) if isinstance(n, ast.Name)}
    writes, write_bases, reads, effects = set(), set(), set(), set()
    for stmt in fs.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                reads.add(node.id)
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    writes |= _target_names(tgt)
                    write_bases |= {w.split("[")[0].split(".")[0] for w in _target_names(tgt)}
            elif isinstance(node, ast.AugAssign):
                writes |= _target_names(node.target)
                write_bases |= {w.split("[")[0].split(".")[0] for w in _target_names(node.target)}
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name):
                recv = node.func.value.id
                if node.func.attr in _MUTATORS:
                    writes.add(recv + "." + node.func.attr + "()")
                    write_bases.add(recv)
                else:
                    effects.add(recv + "." + node.func.attr)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                effects.add(node.func.id)
    return dict(iterates=iters, binds=binds, writes=writes,
                reads=(reads - write_bases - binds - iters), effects=effects)


# --- PART 2: reuse a bespoke, unnamed loop as a black-box fragment -----------------------------------

# A line-continuation joiner: fold a `\`-terminated run of lines into one. No sum/map/filter name fits;
# it is a genuinely bespoke stateful loop — the kind that IS the residual.
RESIDUAL_SRC = '''
out = []
buf = []
for line in lines:
    line = line.rstrip("\\n")
    if line.endswith("\\\\"):
        buf.append(line[:-1])
    else:
        buf.append(line)
        out.append("".join(buf))
        buf.clear()
'''


def interface(loop_src: str) -> dict:
    """Derive a fragment's interface from an unnamed loop: inputs (free reads) and produced state
    (writes) — no concept name. This is all reuse needs."""
    mod = ast.parse(loop_src)
    fs = next(n for n in ast.walk(mod) if isinstance(n, ast.For))
    fp = footprint(fs)
    # a var assigned before the loop and read after is part of the interface; the free reads are inputs.
    pre_assigned = {t.id for s in mod.body if isinstance(s, ast.Assign) for t in s.targets if isinstance(t, ast.Name)}
    inputs = sorted(fp["reads"])
    produces = sorted(pre_assigned)                      # the state the loop builds (the outputs)
    return {"inputs": inputs, "produces": produces}


def invoke(loop_src: str, inputs: dict, want: str):
    """Run the residual as an OPAQUE parameterized block: seed the free inputs, execute, read a produced
    value out. Reuse by derived interface + execution — the concept name never appears."""
    ns = dict(inputs)
    exec(compile(loop_src, "<residual-fragment>", "exec"), {}, ns)
    return ns[want]


def main() -> None:
    files = sorted(glob.glob(os.path.join(os.path.dirname(os.__file__), "*.py")))
    hits = scan_corpus(files)
    residual = [h.node for h in hits if not any(a in VALUE_ASPECTS for a in leaf_aspects(h.node.body))]

    print("BASE TIER — the unnamed residual is operable and reusable without a concept\n")

    fps = [footprint(fs) for fs in residual]
    summarized = sum(1 for fp in fps if fp["reads"] or fp["writes"] or fp["effects"] or fp["iterates"])
    acting = sum(1 for fp in fps if fp["writes"] or fp["effects"])
    print(f"PART 1 — FOOTPRINT the residual ({len(residual)} loops with NO named value-concept):")
    print(f"  named:           0%    (that's the point — no concept fits them)")
    print(f"  base-summary:  {100 * summarized / len(residual):3.0f}%    ({summarized}/{len(residual)} have a derivable iterate/read/write/effect summary)")
    print(f"  of those, {100 * acting / len(residual):3.0f}% write or call (the rest are pure search/scan — read + control)\n")
    print("  a few residual loops + their derived footprints (understanding without a name):")
    shown = 0
    for fs in residual:
        fp = footprint(fs)
        if len(fp["writes"]) + len(fp["effects"]) >= 2 and shown < 4:   # pick a few with real content
            head = ast.unparse(fs).splitlines()[0][:70]
            print(f"    {head}")
            print(f"        reads={sorted(fp['reads'])[:4]}  writes={sorted(fp['writes'])[:4]}  effects={sorted(fp['effects'])[:3]}")
            shown += 1
    print()

    print("PART 2 — REUSE a bespoke unnamed loop as a BLACK-BOX FRAGMENT (a line-continuation joiner):")
    iface = interface(RESIDUAL_SRC)
    print(f"  derived interface (no name): inputs={iface['inputs']}  produces={iface['produces']}")
    lines = ["foo=1 \\", "bar", "baz=2"]                  # 'foo=1 ' continues onto 'bar'
    result = invoke(RESIDUAL_SRC, {"lines": lines}, want="out")
    print(f"  invoked on lines={lines!r}  ->  out = {result}")
    print(f"  reused by its DERIVED INTERFACE + execution — the concept name never appeared.\n")

    print("READING: naming is 0% and footprinting is ~100%. The unnamed residual is not a hole the model")
    print("must fill — it is base-tier code, fully operable (footprint + execution) and reusable (derived")
    print("interface), by the SAME base-tier substrate the footprint work already uses. Named concepts are")
    print("an optional compression layer on top. The membrane is intent-ambiguity, not the unnamed residual.")


if __name__ == "__main__":
    main()
