"""Code intake — the §8 CALL tool of the design (docs/code_reasoning_design.md).

Deterministic, external, **materializes structure** from Python source via the stdlib
`ast`. Per the design this boundary is explicitly *not* CNL and *not* rule-rewriting: it
is the one place we author graph structure directly (the sanctioned tool contract from
ugm's engine_developer_guide — "a tool reads opaque input, emits nodes"). Everything
downstream (semantics, hypotheses, outcomes) then reasons over these facts through the
public ugm firmware, never by touching the graph again.

Scope of this spike: a single function of straight-line, single-assignment name / attribute
code — enough to drive the vertical spike (assign, attribute access, return). Branch and
loop intake, and the state-succession axis they need, are the next slice (see the design's
"Honest scope" and "Open questions").

The output is a flat list of `(subject, predicate, object)` triples over named nodes — the
AST+CFG base facts. No DFG overlay: value flow is *computed by the semantics*, not
precomputed here (the design's central simplification).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass
class Intake:
    """The materialized facts plus the side tables a human-readable trace needs."""
    func: str
    params: list[str]
    facts: list[tuple[str, str, str]]
    line_of: dict[str, int]          # node id -> source line
    label_of: dict[str, str]         # node id -> short source-like label (for the trace)
    attributes: list[str]            # every attribute-access expr id (candidate None-deref sites)
    source: str = ""                 # the source this was intaken from (for the transformer)
    attr_base_var: dict[str, str] = None   # attribute site -> the Name variable it dereferences

    def __post_init__(self) -> None:
        if self.attr_base_var is None:
            self.attr_base_var = {}

    def source_line(self, node_id: str) -> int | None:
        return self.line_of.get(node_id)


# the abstract-value lattice this intake commits to: concrete-or-None first (the design's
# minimum domain). `none` is the sole modelled value-kind; a fresh object value is minted
# per hypothesis by the analyzer. Emitted with every intake so the semantics can gate on it.
VALUE_LATTICE: list[tuple[str, str, str]] = [("none", "is_a", "none_value")]


class _Walker:
    def __init__(self, src: str) -> None:
        self.src = src.splitlines()
        self.facts: list[tuple[str, str, str]] = list(VALUE_LATTICE)
        self.line_of: dict[str, int] = {}
        self.label_of: dict[str, str] = {}
        self.attributes: list[str] = []
        self.attr_base_var: dict[str, str] = {}
        self._n = 0

    def _fresh(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def _emit(self, s: str, p: str, o: str) -> None:
        self.facts.append((s, p, o))

    def _snippet(self, node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:                       # pragma: no cover - defensive
            return type(node).__name__

    # --- expressions: return the node-id standing for the expression's value ---
    def expr(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            eid = self._fresh("e")
            self._emit(eid, "is_a", "name")
            self._emit(eid, "reads", node.id)
            self.label_of[eid] = node.id
            self.line_of[eid] = node.lineno
            return eid
        if isinstance(node, ast.Attribute):
            base = self.expr(node.value)
            eid = self._fresh("attr")
            self._emit(eid, "is_a", "attribute")
            self._emit(eid, "attr_of", base)
            self._emit(eid, "attr_name", node.attr)
            self.attributes.append(eid)
            if isinstance(node.value, ast.Name):
                self.attr_base_var[eid] = node.value.id
            self.label_of[eid] = self._snippet(node)
            self.line_of[eid] = node.lineno
            return eid
        if isinstance(node, ast.Call):
            fn = self.expr(node.func)
            eid = self._fresh("call")
            self._emit(eid, "is_a", "call")
            self._emit(eid, "calls", fn)
            self.label_of[eid] = self._snippet(node)
            self.line_of[eid] = node.lineno
            return eid
        # unsupported expression: an opaque value node, typed `unknown_value` (honest UNKNOWN)
        eid = self._fresh("u")
        self._emit(eid, "is_a", "unknown_expr")
        self.label_of[eid] = self._snippet(node)
        self.line_of[eid] = getattr(node, "lineno", 0)
        return eid

    # --- statements ---
    def stmt(self, node: ast.AST) -> None:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            sid = self._fresh("s")
            self._emit(sid, "is_a", "assign")
            self._emit(sid, "assigns", node.targets[0].id)
            self._emit(sid, "from_expr", self.expr(node.value))
            self.line_of[sid] = node.lineno
            self.label_of[sid] = self._snippet(node)
        elif isinstance(node, ast.Return) and node.value is not None:
            sid = self._fresh("s")
            self._emit(sid, "is_a", "return")
            self._emit(sid, "returns", self.expr(node.value))
            self.line_of[sid] = node.lineno
            self.label_of[sid] = self._snippet(node)
        elif isinstance(node, ast.If):
            # a `if VAR is not None:` guard is intaken as guard structure so the semantics can
            # gate reachability on it — this is what makes the modification round-trip REAL: the
            # transformer emits this exact source, and re-intake derives the guard facts (they
            # are no longer hand-authored). Non-`is not None` conditions are treated as plain
            # (body still recursed, no guard) — honest partiality.
            guard_var = self._guard_var(node.test)
            if guard_var is not None:
                gid = self._fresh("g")
                self._emit(gid, "is_a", "guard")
                self._emit(gid, "tests", guard_var)
                self.line_of[gid] = node.lineno
                before = set(self.attributes)
                for s in node.body:
                    self.stmt(s)
                for site in self.attributes:                 # attrs created inside this body ...
                    if site not in before:
                        self._emit(site, "within_guard", gid)   # ... are guarded by it
            else:
                for s in node.body:
                    self.stmt(s)
        # other statement kinds: skipped (honest partiality, not silent misreading)

    @staticmethod
    def _guard_var(test: ast.AST) -> str | None:
        """The variable of a `VAR is not None` (or `None is not VAR`) test, else None."""
        if isinstance(test, ast.Compare) and len(test.ops) == 1 \
                and isinstance(test.ops[0], ast.IsNot):
            l, r = test.left, test.comparators[0]
            if isinstance(l, ast.Name) and isinstance(r, ast.Constant) and r.value is None:
                return l.id
            if isinstance(r, ast.Name) and isinstance(l, ast.Constant) and l.value is None:
                return r.id
        return None


def intake_function(src: str) -> Intake:
    """Parse one top-level function from `src` and materialize its AST+CFG base facts."""
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    w = _Walker(src)
    params = [a.arg for a in fn.args.args]
    w.facts.append((fn.name, "is_a", "function"))
    for p in params:
        w.facts.append((fn.name, "has_param", p))
    for s in fn.body:
        w.stmt(s)
    return Intake(func=fn.name, params=params, facts=w.facts,
                  line_of=w.line_of, label_of=w.label_of, attributes=w.attributes,
                  source=src, attr_base_var=w.attr_base_var)
