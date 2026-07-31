"""Pins for `strider/` — pystrider's bidirectional-pattern bet, running on ../ugm's microfunctions engine.

Slice 0 (`tests/test_microfunction_pattern.py`) established that the bet is expressible. These pin it as
a PRODUCT: authored `.mf` files on disk, a loader, and both halves reaching structure only through what
those files say.
"""
import pytest

from strider import Abstained, construct, load, pattern_of, recognize, recognizes
from strider.library import RULES
from strider.patterns import unreadable


def parts(lib, *kinds):
    return [lib.graph.mint(k) for k in kinds]


# --- the authored library ------------------------------------------------------------------------------

def test_the_library_loads_from_real_mf_files():
    lib = load()
    assert set(lib.patterns) == {"as_iteration", "as_application", "as_conditional"}


def test_patterns_and_bridges_are_kept_apart_by_the_FILE_they_live_in():
    """A bridge writes the edges it would then match, so it must never be offered as a description of
    something. The file draws the line — not a naming convention, and not a hand-kept list."""
    lib = load()
    assert set(lib.bridge_names) == {"as_iteration_from_for_stmt", "as_application_from_call",
                                     "as_conditional_from_if_stmt"}
    assert not set(lib.patterns) & set(lib.bridge_names)


def test_every_authored_pattern_is_readable():
    """A dark pattern is not a failure of this layer, but it IS something a consumer must be told about.
    The shipped library must have none — that is the authoring rules in `patterns.mf` doing their job."""
    assert unreadable(load()) == {}


def test_no_predicate_name_is_hardcoded_outside_the_mf_files():
    """The property that makes this ONE library. If a predicate name appeared in the Python it would be
    two descriptions that happen to agree, and the perturbation pin below could not bite.

    Checked over string LITERALS reached by `ast`, not raw text: prose about the pattern is fine and
    expected — a hardcoded value is not. (The first version of this check grepped the source and failed
    on its own docstring, which would have pushed the explanation out of the module to satisfy it.)"""
    import ast
    import strider.library as library_mod
    import strider.patterns as patterns_mod

    authored = RULES.joinpath("patterns.mf").read_text(encoding="utf-8")
    predicates = {tok.strip('"') for tok in authored.split() if tok.startswith('"')}
    assert predicates, "no predicates found in the .mf — this check would pass vacuously"

    for module in (patterns_mod, library_mod):
        tree = ast.parse(open(module.__file__, encoding="utf-8").read())
        docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef))}
        literals = {n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)} - docstrings
        assert not (predicates & literals), (module.__file__, predicates & literals)


# --- both halves, through one description --------------------------------------------------------------

@pytest.mark.parametrize("name,kinds,keys", [
    ("as_iteration", ("sequence", "variable", "block"), ("seq", "var", "body")),
    ("as_application", ("func", "value"), ("func", "arg")),
    ("as_conditional", ("test", "block", "block"), ("test", "then_body", "else_body")),
])
def test_construct_then_recognize_round_trips(name, kinds, keys):
    lib = load()
    made = parts(lib, *kinds)
    node = construct(lib, name, **dict(zip(keys, made)))
    assert recognize(lib, node, name) == dict(zip(keys, made))


def test_recognition_returns_bindings_not_a_verdict():
    lib = load()
    seq, var, body = parts(lib, "sequence", "variable", "block")
    node = construct(lib, "as_iteration", seq=seq, var=var, body=body)
    assert recognize(lib, node, "as_iteration")["seq"] == seq


def test_the_effect_tuples_carry_both_roles():
    """The shared-variable join. Without the object role, three effects about one node could not say
    WHICH part is which, and the bindings above would be unavailable."""
    _subject, required = pattern_of(load(), "as_iteration")
    assert all(subj == "it" and obj is not None for _k, _l, subj, obj in required)


def test_construct_mints_the_declared_return_type():
    lib = load()
    node = construct(lib, "as_application", **dict(zip(("func", "arg"), parts(lib, "func", "value"))))
    assert lib.graph.kind(node) == "application"


# --- bottom-up: what IS this -----------------------------------------------------------------------------

def test_recognizes_finds_the_pattern_without_being_told_which():
    lib = load()
    seq, var, body = parts(lib, "sequence", "variable", "block")
    node = construct(lib, "as_iteration", seq=seq, var=var, body=body)
    assert set(recognizes(lib, node)) == {"as_iteration"}


def test_multi_pattern_falls_out_rather_than_needing_mechanism():
    """These are independent structural predicates, so a node satisfying two descriptions is recognized
    as both — the same property ugm's `types.recognize` gets for multi-type, for the same reason."""
    lib = load()
    g = lib.graph
    seq, var, body = parts(lib, "sequence", "variable", "block")
    node = construct(lib, "as_iteration", seq=seq, var=var, body=body)
    g.link(node, "applies", g.mint("func"))
    g.link(node, "to", g.mint("value"))
    assert set(recognizes(lib, node)) == {"as_iteration", "as_application"}


def test_an_unrelated_node_is_recognized_as_nothing():
    lib = load()
    assert recognizes(lib, lib.graph.mint("whatever")) == {}


# --- ONE library: the perturbation pin, against the SHIPPED file ----------------------------------------

def test_perturbing_one_label_in_the_mf_darkens_both_halves():
    """Rename a single label in the authored text; the writer emits the new edge and the reader looks for
    it, so code written by the old spelling becomes invisible. Two descriptions that merely agreed would
    not both move."""
    authored = RULES.joinpath("patterns.mf").read_text(encoding="utf-8")
    perturbed = load(authored.replace('"each_does"', '"each_doez"'))
    g = perturbed.graph
    seq, var, body = parts(perturbed, "sequence", "variable", "block")

    old_spelling = g.mint("iteration")
    g.link(old_spelling, "repeats_over", seq)
    g.link(old_spelling, "element", var)
    g.link(old_spelling, "each_does", body)          # written the ORIGINAL way

    new_write = construct(perturbed, "as_iteration", seq=seq, var=var, body=body)

    assert g.targets(new_write, "each_doez") != ()   # the WRITE half moved
    assert recognize(perturbed, new_write, "as_iteration") is not None    # still self-consistent
    assert recognize(perturbed, old_spelling, "as_iteration") is None     # the READ half moved with it


def test_control_the_perturbation_pin_is_not_vacuous():
    """⚠ Vacuity control. The SAME hand-built shape must be read by the UNPERTURBED library, or
    "invisible" above would be satisfied by a node that nothing could ever read."""
    lib = load()
    g = lib.graph
    seq, var, body = parts(lib, "sequence", "variable", "block")
    control = g.mint("iteration")
    g.link(control, "repeats_over", seq)
    g.link(control, "element", var)
    g.link(control, "each_does", body)
    assert recognize(lib, control, "as_iteration") is not None


# --- refusal, the standing floor -------------------------------------------------------------------------

def test_a_partial_shape_is_refused_not_guessed():
    lib = load()
    g = lib.graph
    seq, var, _body = parts(lib, "sequence", "variable", "block")
    partial = g.mint("iteration")
    g.link(partial, "repeats_over", seq)
    g.link(partial, "element", var)                  # no body — out of repertoire
    assert recognize(lib, partial, "as_iteration") is None
    assert recognizes(lib, partial) == {}


def test_an_unknown_pattern_is_refused_BY_NAME_with_the_repertoire():
    lib = load()
    with pytest.raises(Abstained) as exc:
        pattern_of(lib, "as_comprehension")
    assert "as_comprehension" in str(exc.value)
    assert "as_iteration" in str(exc.value)          # says what IS in repertoire


def test_a_minting_pattern_is_refused_with_the_authoring_rule():
    """Finding #1 as a guardrail: if somebody authors a pattern the obvious way, they are told why it
    cannot be read and what to write instead — not left with a description that silently matches nothing."""
    lib = load("\n".join([
        'fn make_iteration(seq, var, body) -> iteration:',
        '    NEW R(it) "iteration"',
        '    LINK R(it) "repeats_over" F(seq)',
    ]))
    with pytest.raises(Abstained) as exc:
        pattern_of(lib, "make_iteration")
    assert "CAST" in str(exc.value)


def test_recognition_abstains_when_the_description_is_incomplete():
    """Finding #3 — the contract inversion. A register-sourced key cannot be read, so the description is
    incomplete, so matching it would admit nodes failing a requirement nobody could read."""
    lib = load("\n".join([
        'fn as_tagged(it, thing) -> tagged:',
        '    LINK F(it) "holds" F(thing)',
        '    ATTR R(k) F(thing) "name"',
        '    SET F(it) R(k) true',
    ]))
    with pytest.raises(Abstained):
        pattern_of(lib, "as_tagged")


def test_control_a_literal_key_in_the_same_body_is_readable():
    """⚠ Vacuity control: pin the CAUSE. It is the register key, not the presence of SET."""
    lib = load("\n".join([
        'fn as_tagged(it, thing) -> tagged:',
        '    LINK F(it) "holds" F(thing)',
        '    SET F(it) "tag" true',
    ]))
    assert pattern_of(lib, "as_tagged")[1] != ()


def test_construct_refuses_the_wrong_parts():
    lib = load()
    with pytest.raises(TypeError):
        construct(lib, "as_iteration", seq=lib.graph.mint("sequence"))
