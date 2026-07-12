"""Code intake — the §8 CALL tool of the design (docs/code_reasoning_design.md).

Deterministic, external, **materializes structure** from Python source via the stdlib
`ast`. Per the design this boundary is explicitly *not* CNL and *not* rule-rewriting: it
is the one place we author graph structure directly (the sanctioned tool contract from
ugm's engine_developer_guide — "a tool reads opaque input, emits nodes"). Everything
downstream (semantics, hypotheses, outcomes) then reasons over these facts through the
public ugm firmware, never by touching the graph again.

Scope: a single function of straight-line name / attribute code with **reassignment** — assign,
attribute access, return, and a tail `if VAR is not None:` guard. Intake emits a CFG: one
program-point (state) per statement, `from_state`/`to_state` on each assignment, `in_state` on
every expression + guard, and a pre-materialized `(state x variable)` cell lattice. The semantics
then thread value through the cells, so `y = a; y = b` is correct (not SSA-wrong). Branch-merge
(a join over two predecessor states) and loop unrolling are the next slice (design "Open
questions").

The output is a flat list of `(subject, predicate, object)` triples over named nodes — the
AST+CFG base facts. No DFG overlay: value flow is *computed by the semantics*, not
precomputed here (the design's central simplification). The one "mint" intake owns beyond AST
structure is the state/cell lattice — states cannot be minted by rules (existential heads
aren't Skolem-minted), so the tool that knows the CFG pre-materializes them.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field


def cell_name(state: str, var: str) -> str:
    """The node id of the `(program-point, variable)` cell — one value slot per state x var. Pre-
    materialized by intake (which knows the CFG statically); the semantics only *bind* these, never
    mint them (state-succession without existential heads — see docs/spike_findings.md)."""
    return f"c_{state}_{var}"


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
    entry_state: str = "p0"          # the program point before the first statement
    states: list[str] = field(default_factory=list)   # every program point, in order
    state_of: dict[str, str] = field(default_factory=dict)   # expr/guard id -> the state it reads in

    def __post_init__(self) -> None:
        if self.attr_base_var is None:
            self.attr_base_var = {}

    def source_line(self, node_id: str) -> int | None:
        return self.line_of.get(node_id)

    def entry_cell(self, var: str) -> str:
        """The cell to seed a parameter hypothesis into (its value at function entry)."""
        return cell_name(self.entry_state, var)


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
        self.func: str = ""              # the enclosing function node (set by intake_function)
        self._vars_seen: set[str] = set()
        self._n = 0
        # --- CFG / state threading: values live in per-state cells, not in bare variables, so
        # reassignment is correct (see docs/spike_findings.md "State-succession"). `state` is the
        # program point the statement currently being walked reads/writes at; assigns advance it.
        self.entry_state = "p0"
        self.state = self.entry_state
        self.states: list[str] = [self.entry_state]
        self.state_of: dict[str, str] = {}
        self._sn = 0

    def _fresh(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def _fresh_state(self) -> str:
        self._sn += 1
        st = f"p{self._sn}"
        self.states.append(st)
        return st

    def _in_state(self, node_id: str) -> str:
        """Stamp `node_id` (an expression or guard) with the program point it reads in."""
        self._emit(node_id, "in_state", self.state)
        self.state_of[node_id] = self.state
        return node_id

    def _emit(self, s: str, p: str, o: str) -> None:
        self.facts.append((s, p, o))

    def _scope(self, entity: str) -> str:
        """Record `entity`'s membership in the enclosing function STRUCTURALLY — an
        `in_function` edge to the function node, not a name prefix. Scope is thus queryable
        graph structure (and the anchor a focus frame / inter-procedural link would use)."""
        if self.func:
            self._emit(entity, "in_function", self.func)
        return entity

    def _var(self, name: str) -> str:
        """A variable mention: type it `variable` and scope it to the function on first sight.
        (Identity is still by bare name within this one function — distinct-node identity across
        functions in a shared graph is the inter-procedural follow-on; see the design doc.)"""
        if name not in self._vars_seen:
            self._vars_seen.add(name)
            self._emit(name, "is_a", "variable")
            self._scope(name)
        return name

    def _snippet(self, node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:                       # pragma: no cover - defensive
            return type(node).__name__

    # --- expressions: return the node-id standing for the expression's value ---
    # every expression is stamped `in_state <point>` so the semantics reads its variables from the
    # cells live at that point (value flow is state-threaded, not SSA-per-variable).
    def expr(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            eid = self._in_state(self._scope(self._fresh("e")))
            self._emit(eid, "is_a", "name")
            self._emit(eid, "reads", self._var(node.id))
            self.label_of[eid] = node.id
            self.line_of[eid] = node.lineno
            return eid
        if isinstance(node, ast.Attribute):
            base = self.expr(node.value)
            eid = self._in_state(self._scope(self._fresh("attr")))
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
            eid = self._in_state(self._scope(self._fresh("call")))
            self._emit(eid, "is_a", "call")
            self._emit(eid, "calls", fn)
            self.label_of[eid] = self._snippet(node)
            self.line_of[eid] = node.lineno
            return eid
        # unsupported expression: an opaque value node, typed `unknown_value` (honest UNKNOWN)
        eid = self._in_state(self._scope(self._fresh("u")))
        self._emit(eid, "is_a", "unknown_expr")
        self.label_of[eid] = self._snippet(node)
        self.line_of[eid] = getattr(node, "lineno", 0)
        return eid

    # --- statements ---
    def stmt(self, node: ast.AST) -> None:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            # an assignment is a CFG transition frm -> to: the RHS reads the cells live at `frm`,
            # the target's cell at `to` takes that value, every other var is framed forward.
            frm, to = self.state, self._fresh_state()
            sid = self._scope(self._fresh("s"))
            self._emit(sid, "is_a", "assign")
            self._emit(sid, "assigns", self._var(node.targets[0].id))
            self._emit(sid, "from_expr", self.expr(node.value))   # read at `frm` (state not yet advanced)
            self._emit(sid, "from_state", frm)
            self._emit(sid, "to_state", to)
            self.line_of[sid] = node.lineno
            self.label_of[sid] = self._snippet(node)
            self.state = to                                       # advance the program point
        elif isinstance(node, ast.Return) and node.value is not None:
            sid = self._scope(self._fresh("s"))
            self._emit(sid, "is_a", "return")
            self._emit(sid, "returns", self.expr(node.value))     # reads at the current point (terminal)
            self.line_of[sid] = node.lineno
            self.label_of[sid] = self._snippet(node)
        elif isinstance(node, ast.If):
            # a `if VAR is not None:` guard is intaken as guard structure so the semantics can
            # gate reachability on it — this is what makes the modification round-trip REAL: the
            # transformer emits this exact source, and re-intake derives the guard facts (they
            # are no longer hand-authored). Non-`is not None` conditions are treated as plain
            # (body still recursed, no guard) — honest partiality. The body reads at the guard's
            # own program point (single tail-guard shape — branch-refinement is a later slice).
            guard_var = self._guard_var(node.test)
            if guard_var is not None:
                gid = self._in_state(self._scope(self._fresh("g")))
                self._emit(gid, "is_a", "guard")
                self._emit(gid, "tests", self._var(guard_var))
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
    w.func = fn.name                                      # the scope node every entity links to
    params = [a.arg for a in fn.args.args]
    w.facts.append((fn.name, "is_a", "function"))
    for p in params:
        w.facts.append((fn.name, "has_param", w._var(p)))   # a param is a variable, scoped
    for s in fn.body:
        w.stmt(s)
    # pre-materialize the state x var cell lattice now that every state and variable is known —
    # the intake "mint" that lets the semantics thread state without existential rule heads.
    for st in w.states:
        for v in sorted(w._vars_seen):
            cid = cell_name(st, v)
            w._emit(cid, "in_state", st)
            w._emit(cid, "for_var", v)
    return Intake(func=fn.name, params=params, facts=w.facts,
                  line_of=w.line_of, label_of=w.label_of, attributes=w.attributes,
                  source=src, attr_base_var=w.attr_base_var,
                  entry_state=w.entry_state, states=w.states, state_of=w.state_of)
