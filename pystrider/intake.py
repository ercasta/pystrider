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
    returns: list[str] = field(default_factory=list)            # every return-statement id
    return_var: dict[str, str] = field(default_factory=dict)    # return id -> returned source var
    call_target: dict[str, str] = field(default_factory=dict)   # call id -> callee source name
    call_args: dict[str, list[str]] = field(default_factory=dict)  # call id -> positional arg exprs
    entry_state: str = "p0"          # the program point before the first statement
    states: list[str] = field(default_factory=list)   # every program point, in order
    state_of: dict[str, str] = field(default_factory=dict)   # expr/guard id -> the state it reads in
    namespace: str = ""              # per-function id prefix (Session); "" = single-function (today)
    not_modelled: list[str] = field(default_factory=list)   # ids of statements intake could NOT model

    def __post_init__(self) -> None:
        if self.attr_base_var is None:
            self.attr_base_var = {}

    def source_line(self, node_id: str) -> int | None:
        return self.line_of.get(node_id)

    def var_id(self, source_name: str) -> str:
        """The graph NODE id of a source variable — namespaced so `x` in two functions are two
        distinct nodes in a shared Session graph. Identity is by `(namespace, source_name)`."""
        return self.namespace + source_name

    def var_source(self, var_id: str) -> str:
        """The source name behind a namespaced variable node id (for rendering / source edits)."""
        ns = self.namespace
        return var_id[len(ns):] if ns and var_id.startswith(ns) else var_id

    def entry_cell(self, source_name: str) -> str:
        """The cell to seed a parameter hypothesis into (its value at function entry)."""
        return cell_name(self.entry_state, self.var_id(source_name))

    def entity_names(self) -> frozenset[str]:
        """Every node name this intake mentions — the working set to bound a hypothesis's attention
        to (feedback #7: `focus_scope` on `suppose`). For one function this is the whole graph (a
        no-op); once a `Session` accretes several functions in one graph it is the per-function
        subset that keeps per-hypothesis cost tracking the function, not the accreted graph."""
        names: set[str] = set()
        for s, _p, o in self.facts:
            names.add(s)
            names.add(o)
        return frozenset(names)


# the abstract-value lattice this intake commits to: concrete-or-None first (the design's
# minimum domain). `none` is the sole modelled value-kind; a fresh object value is minted
# per hypothesis by the analyzer. Emitted with every intake so the semantics can gate on it.
VALUE_LATTICE: list[tuple[str, str, str]] = [("none", "is_a", "none_value")]


class _Walker:
    def __init__(self, src: str, loop_unroll: int = 2, namespace: str = "") -> None:
        self.src = src.splitlines()
        self.ns = namespace              # per-function id prefix; "" = single-function (today)
        self.facts: list[tuple[str, str, str]] = list(VALUE_LATTICE)
        self.line_of: dict[str, int] = {}
        self.label_of: dict[str, str] = {}
        self.attributes: list[str] = []
        self.attr_base_var: dict[str, str] = {}
        self.returns: list[str] = []              # every return-statement id (candidate returns-None sites)
        self.not_modelled: list[str] = []         # ids of statements intake could not model (visible gaps)
        self.statements: list[str] = []           # every statement id, in creation order — what lets a
                                                  # compound statement link its DIRECT children
        self._structured: set[str] = set()        # compound statements whose STRUCTURE is already
                                                  # emitted (see `_for`: structure is per-source,
                                                  # state is per-unrolling)
        self.return_var: dict[str, str] = {}      # return id -> the source Name it returns (if a bare var)
        self.call_target: dict[str, str] = {}     # call id -> callee SOURCE name (free-function calls)
        self.call_args: dict[str, list[str]] = {}  # call id -> positional argument expr ids
        self.func: str = ""              # the enclosing function NODE (namespaced; set by intake_function)
        self._vars_seen: set[str] = set()
        self._n = 0
        # --- CFG / state threading: values live in per-state cells, not in bare variables, so
        # reassignment is correct (see docs/spike_findings.md "State-succession"). The program point
        # is threaded explicitly through `block`/`stmt` (a fork-join tree, not a single cursor).
        self.entry_state = f"{namespace}p0"
        self.states: list[str] = [self.entry_state]
        self.state_of: dict[str, str] = {}
        self._sn = 0
        # loop bodies are UNROLLED to this depth: the pre-materialized state-pool size IS the
        # fuel/world budget (design "fuel / world budget"). Beyond it, later iterations are not
        # modelled — an honest bound, not a fixpoint (the "agent, not theorem prover" stance).
        self.loop_unroll = loop_unroll

    def _fresh(self, kind: str) -> str:
        self._n += 1
        return f"{self.ns}{kind}{self._n}"

    def _fresh_state(self) -> str:
        self._sn += 1
        st = f"{self.ns}p{self._sn}"
        self.states.append(st)
        return st

    def _in_state(self, node_id: str, state: str) -> str:
        """Stamp `node_id` (an expression or guard) with the program point it reads in."""
        self._emit(node_id, "in_state", state)
        self.state_of[node_id] = state
        return node_id

    def _edge(self, frm: str, to: str) -> str:
        """A plain CFG control-flow edge (branch fork / merge join) — assigns nothing, so the frame
        rule carries EVERY variable across it. A merge point simply has two incoming edges, and the
        value union at the merge falls out of the frame rule firing once per edge (Horn disjunction)
        — the join is a ugm derivation, never a Python-computed lattice meet."""
        tid = self._fresh("t")
        self._emit(tid, "is_a", "transition")
        self._emit(tid, "from_state", frm)
        self._emit(tid, "to_state", to)
        return tid

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
        """A variable mention -> its graph NODE id (namespaced). Identity is by `(namespace,
        source_name)`: within one function all mentions of `x` share a node; across functions in a
        shared Session graph two `x`s are distinct nodes (the `ns` prefix), so the shared graph
        holds legitimately different same-named variables. The source name is kept as the label."""
        vid = self.ns + name
        if name not in self._vars_seen:
            self._vars_seen.add(name)
            self._emit(vid, "is_a", "variable")
            self._scope(vid)
            self.label_of[vid] = name
        return vid

    def _snippet(self, node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:                       # pragma: no cover - defensive
            return type(node).__name__

    # --- expressions: return the node-id standing for the expression's value ---
    # every expression is stamped `in_state <point>` so the semantics reads its variables from the
    # cells live at that point (value flow is state-threaded, not SSA-per-variable).
    def expr(self, node: ast.AST, state: str) -> str:
        if isinstance(node, ast.Name):
            eid = self._in_state(self._scope(self._fresh("e")), state)
            self._emit(eid, "is_a", "name")
            self._emit(eid, "reads", self._var(node.id))
            self.label_of[eid] = node.id
            self.line_of[eid] = node.lineno
            return eid
        if isinstance(node, ast.Attribute):
            base = self.expr(node.value, state)
            eid = self._in_state(self._scope(self._fresh("attr")), state)
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
            fn = self.expr(node.func, state)
            eid = self._in_state(self._scope(self._fresh("call")), state)
            self._emit(eid, "is_a", "call")
            self._emit(eid, "calls", fn)
            # a FREE-function call `g(a, ...)` is an inter-procedural link candidate: record the
            # callee's SOURCE name and each positional argument expression (each read in this state),
            # so a Session can wire arg -> callee param cell. A method call (`x.bar()`) is not a link.
            if isinstance(node.func, ast.Name):
                self.call_target[eid] = node.func.id
                self._emit(eid, "calls_func", node.func.id)
                arg_exprs = [self.expr(a, state) for a in node.args]
                self.call_args[eid] = arg_exprs
                for i, aexpr in enumerate(arg_exprs):
                    self._emit(eid, "passes", aexpr)
                    self._emit(aexpr, "at_index", str(i))
            self.label_of[eid] = self._snippet(node)
            self.line_of[eid] = node.lineno
            return eid
        # unsupported expression: an opaque value node, typed `unknown_value` (honest UNKNOWN)
        eid = self._in_state(self._scope(self._fresh("u")), state)
        self._emit(eid, "is_a", "unknown_expr")
        self.label_of[eid] = self._snippet(node)
        self.line_of[eid] = getattr(node, "lineno", 0)
        return eid

    # --- statements: process one statement entering at `state`; return the EXIT state ---
    def block(self, stmts: list[ast.stmt], state: str) -> str:
        """Walk a straight-line block from `state`, threading the program point statement to
        statement; return the block's exit state."""
        for s in stmts:
            state = self.stmt(s, state)
        return state

    def stmt(self, node: ast.AST, state: str) -> str:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            # an assignment is a CFG transition state -> to: the RHS reads the cells live at `state`,
            # the target's cell at `to` takes that value, every other var is framed forward.
            to = self._fresh_state()
            sid = self._scope(self._fresh("s"))
            self.statements.append(sid)
            self._emit(sid, "is_a", "assign")
            self._emit(sid, "assigns", self._var(node.targets[0].id))
            self._emit(sid, "from_expr", self.expr(node.value, state))
            self._emit(sid, "from_state", state)
            self._emit(sid, "to_state", to)
            self.line_of[sid] = node.lineno
            self.label_of[sid] = self._snippet(node)
            return to                                             # advance the program point
        if isinstance(node, ast.Return) and node.value is not None:
            sid = self._scope(self._fresh("s"))
            self.statements.append(sid)
            self._emit(sid, "is_a", "return")
            self._emit(sid, "returns", self.expr(node.value, state))   # reads at `state` (terminal)
            self.returns.append(sid)                                   # a candidate returns-None site
            if isinstance(node.value, ast.Name):
                self.return_var[sid] = node.value.id                   # the var a coalesce would default
            self.line_of[sid] = node.lineno
            self.label_of[sid] = self._snippet(node)
            return state
        if isinstance(node, ast.If):
            return self._if(node, state)
        if isinstance(node, ast.While):
            return self._while(node, state)
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            return self._for(node, state)
        if isinstance(node, ast.Expr):
            # An expression STATEMENT (`print(x)`, `log(x)`): it binds no name, so the program point
            # does not advance and no cell is written — but the EXPRESSION is modelled, so its calls,
            # attribute accesses and reads become ordinary nodes. Previously this fell through to
            # `not_modelled`, which made a whole class of real program (anything built out of bare
            # calls) invisible to every downstream question: a generated `print(greet(name))` produced
            # zero `call` nodes, so no structural rule could see it at all. Modelling the expression is
            # the vocabulary author's half of a COVERAGE gap that no bridge can close
            # (`docs/vocabulary_bridge.md`).
            eid = self.expr(node.value, state)
            sid = self._scope(self._fresh("s"))
            self.statements.append(sid)
            self._emit(sid, "is_a", "expr_stmt")
            self._emit(sid, "evaluates", eid)
            self.line_of[sid] = node.lineno
            self.label_of[sid] = self._snippet(node)
            return state                                          # binds nothing -> same program point
        # an unmodelled statement kind (aug-assign, attribute/subscript store, tuple unpack, `with`,
        # a `for` over a non-Name target, ...): we cannot thread its effect on state. Emit a VISIBLE `not_modelled`
        # marker so a downstream `clean`/`verified` verdict can say "clear MODULO this", instead of
        # silently framing a stale value forward and reporting confidently-clean (critique #5). The
        # state is returned unchanged (we still don't model the effect) — but the gap is now audited.
        sid = self._scope(self._fresh("s"))
        self.statements.append(sid)
        self._emit(sid, "is_a", "not_modelled")
        self.line_of[sid] = getattr(node, "lineno", 0)
        self.label_of[sid] = self._snippet(node)
        self.not_modelled.append(sid)
        return state

    def _if(self, node: ast.If, state: str) -> str:
        """Two intake shapes for a conditional:

        - a **tail** `if VAR is not None:` (no else) is kept as `guard` structure gated by the
          reachability rules — this is what makes the repair round-trip real (the transformer emits
          exactly this source and re-intake derives the guard). Body reads at the guard's own point.
        - **any other** `if`/`if-else` is a control-flow **fork**: two edges out of `state` into a
          then- and else-entry point, each body threaded independently, then two edges into a fresh
          **merge** point. Value at the merge is the *union* of the branches — derived by the frame
          rule firing once per merge edge (Horn disjunction), never a Python join.
        """
        guard_var = self._guard_var(node.test)
        if guard_var is not None and not node.orelse:
            gid = self._in_state(self._scope(self._fresh("g")), state)
            self._emit(gid, "is_a", "guard")
            self._emit(gid, "tests", self._var(guard_var))
            self.line_of[gid] = node.lineno
            before = set(self.attributes)
            before_calls = set(self.call_target)
            exit_state = self.block(node.body, state)
            for site in self.attributes:                          # attrs created inside this body ...
                if site not in before:
                    self._emit(site, "within_guard", gid)         # ... are guarded by it
            for cid in self.call_target:                          # calls created inside this body too:
                if cid not in before_calls:
                    self._emit(cid, "within_guard", gid)          # lets a Session refine a guarded call's
            return exit_state                                     # argument value across the call boundary

        then_entry, else_entry = self._fresh_state(), self._fresh_state()
        then_edge = self._edge(state, then_entry)                 # fork: assume-cond / assume-not-cond
        else_edge = self._edge(state, else_entry)
        # PATH REFINEMENT: when the condition is a `VAR is [not] None` test we understand, tag each
        # fork edge with what it ASSUMES about VAR. The refined-frame rules then carry only values
        # consistent with the assumption (none filtered out on the non-null branch, and vice versa),
        # so a deref of VAR on its safe branch no longer reports a spurious None outcome. A condition
        # we don't understand gets no tag → the sound may-union (both branches keep every value).
        ref = self._none_compare(node.test)
        if ref is not None:
            rvar, kind = ref
            vid = self._var(rvar)
            then_kind, else_kind = ("nonnull", "null") if kind == "nonnull" else ("null", "nonnull")
            self._emit(then_edge, f"assume_{then_kind}", vid)     # true-branch of the test
            self._emit(else_edge, f"assume_{else_kind}", vid)     # false-branch of the test
        then_exit = self.block(node.body, then_entry)
        else_exit = self.block(node.orelse, else_entry) if node.orelse else else_entry
        merge = self._fresh_state()
        self._edge(then_exit, merge)                              # join: both paths flow to the merge
        self._edge(else_exit, merge)
        return merge

    def _block_ids(self, stmts: list[ast.stmt], state: str) -> tuple[str, list[str]]:
        """`block`, but also reporting the DIRECT child statement of each entry — the first id the
        statement created, since a compound statement emits its own id before descending. Nested
        statements are therefore attributed to their own parent, not to this one."""
        ids: list[str] = []
        for s in stmts:
            mark = len(self.statements)
            state = self.stmt(s, state)
            if len(self.statements) > mark:
                ids.append(self.statements[mark])
        return state, ids

    def _for(self, node: ast.For, state: str) -> str:
        """A `for` loop — modelled in BOTH registers, because two different questions are asked of it.

        STRUCTURE (what it is): `is_a for_loop`, the sequence it `iterates`, the variable it `binds`,
        and a `loop_body` link per direct child. This is what a pattern needs in order to recognize an
        iteration in hand-written code — and it is deliberately the same shape the generation half
        MINTS (`emit_for` / `iter_over` / `binds` / `body_has`), so a bridge can reconcile the two
        namings without either side inventing structure the other lacks.

        STATE (what it does): unrolled to `loop_unroll` iterations exactly as `_while` is, with the
        loop variable bound at each body entry from an element we do not model — an `unknown_expr`,
        because knowing a sequence says nothing about its elements. Honest bound, not a fixpoint.

        **Structure is per-SOURCE, state is per-UNROLLING** — the distinction the two registers force.
        A loop nested inside another is walked once per outer iteration, so a naive walker mints a
        second `for_loop` node for the same source statement and "how many loops does this function
        have?" answers wrongly. The structural node is therefore identified by source position and
        emitted once; only the CFG (states, the element binding, the body's threading) repeats. For the
        same reason `loop_body` links the FIRST walk's statement ids: the later ones are CFG copies of
        the same source statement, not distinct code."""
        fid = self._scope(f"{self.ns}for@{node.lineno}")
        first = fid not in self._structured
        if first:
            self._structured.add(fid)
            self.statements.append(fid)
            self._emit(fid, "is_a", "for_loop")
            self._emit(fid, "binds", self._var(node.target.id))
            self.line_of[fid] = node.lineno
            self.label_of[fid] = f"for {node.target.id} in {self._snippet(node.iter)}"
        iterated = self.expr(node.iter, state)         # a real read at this program point, every pass
        if first:
            self._emit(fid, "iterates", iterated)

        post = self._fresh_state()
        head, linked = state, False
        for _ in range(max(0, self.loop_unroll)):
            body_entry = self._fresh_state()
            self._edge(head, body_entry)                         # take the body once more ...
            self._edge(head, post)                               # ... or exit here (0..k iterations)
            bound = self._fresh_state()                          # the loop variable takes an element
            element = self._in_state(self._scope(self._fresh("u")), body_entry)
            self._emit(element, "is_a", "unknown_expr")           # an element we cannot know
            self.label_of[element] = f"<element of {self._snippet(node.iter)}>"
            bid = self._scope(self._fresh("s"))
            self.statements.append(bid)
            self._emit(bid, "is_a", "assign")
            self._emit(bid, "assigns", self._var(node.target.id))
            self._emit(bid, "from_expr", element)
            self._emit(bid, "from_state", body_entry)
            self._emit(bid, "to_state", bound)
            self.line_of[bid] = node.lineno
            self.label_of[bid] = f"{node.target.id} = <element>"
            body_exit, ids = self._block_ids(node.body, bound)
            if first and not linked:                             # structure from the first pass only
                for child in ids:
                    self._emit(fid, "loop_body", child)
                linked = True
            nxt = self._fresh_state()
            self._edge(body_exit, nxt)                           # back-edge to the next unrolled head
            head = nxt
        self._edge(head, post)                                   # fuel exhausted at depth k: exit
        return post

    def _while(self, node: ast.While, state: str) -> str:
        """A `while` loop, **unrolled** to `self.loop_unroll` iterations — the pre-materialized
        state pool IS the fuel budget. Each unrolled head forks into *exit the loop* (an edge
        straight to the post-loop merge) and *run the body once more* (thread the body, then a
        back-edge to the next head). Every exit — after 0, 1, … k iterations — flows into the same
        merge, so the post-loop value is the *union* over all iteration counts (frame-rule
        disjunction; no Python join, no fixpoint). The condition itself is not evaluated: exit is
        always possible (sound may-analysis). Iterations beyond k are not modelled (honest bound)."""
        post = self._fresh_state()
        head = state
        for _ in range(max(0, self.loop_unroll)):
            body_entry = self._fresh_state()
            self._edge(head, body_entry)                         # take the body once more ...
            self._edge(head, post)                               # ... or exit here (0..k iterations)
            body_exit = self.block(node.body, body_entry)
            nxt = self._fresh_state()
            self._edge(body_exit, nxt)                           # back-edge to the next unrolled head
            head = nxt
        self._edge(head, post)                                   # fuel exhausted at depth k: exit
        return post

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

    @staticmethod
    def _none_compare(test: ast.AST) -> tuple[str, str] | None:
        """`(var, 'nonnull')` for a `VAR is not None` test, `(var, 'null')` for `VAR is None`
        (either operand order), else None. Drives fork PATH REFINEMENT: 'nonnull' = the true-branch
        assumes VAR is non-None, 'null' = it assumes VAR is None."""
        if not (isinstance(test, ast.Compare) and len(test.ops) == 1):
            return None
        op, l, r = test.ops[0], test.left, test.comparators[0]
        name = None
        if isinstance(l, ast.Name) and isinstance(r, ast.Constant) and r.value is None:
            name = l.id
        elif isinstance(r, ast.Name) and isinstance(l, ast.Constant) and l.value is None:
            name = r.id
        if name is None:
            return None
        if isinstance(op, ast.IsNot):
            return (name, "nonnull")
        if isinstance(op, ast.Is):
            return (name, "null")
        return None


def intake_function(src: str, *, loop_unroll: int = 2, namespace: str = "") -> Intake:
    """Parse one top-level function from `src` and materialize its AST+CFG base facts.

    `loop_unroll` is the fuel budget: `while` bodies are pre-materialized (unrolled) to this many
    iterations. Behaviour beyond it is not modelled — a bug that only manifests on iteration k+1 is
    missed (honest, bounded partiality). Raising it costs more states, not new machinery.

    `namespace` prefixes every structural node id (states, exprs, statements, transitions, cells,
    variables, the function node) so several functions coexist in one shared Session graph without
    colliding — the type/value vocabulary the rules match on (`assign`, `none`, `none_value`,
    `attribute_error`, …) stays SHARED (unprefixed). Default `""` is single-function (today)."""
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    w = _Walker(src, loop_unroll=loop_unroll, namespace=namespace)
    func_node = namespace + fn.name                      # the scope node every entity links to
    w.func = func_node
    w.label_of[func_node] = fn.name
    params = [a.arg for a in fn.args.args]
    w.facts.append((func_node, "is_a", "function"))
    for p in params:
        w.facts.append((func_node, "has_param", w._var(p)))   # a param is a variable, scoped
    w.block(fn.body, w.entry_state)
    # pre-materialize the state x var cell lattice now that every state and variable is known —
    # the intake "mint" that lets the semantics thread state without existential rule heads.
    for st in w.states:
        for v in sorted(w._vars_seen):
            vid = w.ns + v
            cid = cell_name(st, vid)
            w._emit(cid, "in_state", st)
            w._emit(cid, "for_var", vid)
    return Intake(func=fn.name, params=params, facts=w.facts,
                  line_of=w.line_of, label_of=w.label_of, attributes=w.attributes,
                  source=src, attr_base_var=w.attr_base_var,
                  returns=w.returns, return_var=w.return_var,
                  call_target=w.call_target, call_args=w.call_args,
                  entry_state=w.entry_state, states=w.states, state_of=w.state_of,
                  namespace=namespace, not_modelled=w.not_modelled)
