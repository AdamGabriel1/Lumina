"""Testes unitários de `lumina/common/attrs.py`.

Cobre a normalização de `attrs` para `List[Tuple[str, List[str]]]`
a partir dos múltiplos formatos legados:
  - None
  - List[str]
  - List[Tuple[str, List]]
  - List[Tuple[str]]  (sem args)
  - List[List[str]]
"""
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lumina.common.attrs import (   # noqa: E402
    normalize_attrs, attr_names, has_attr, get_attr_args,
)


# ============================================================
# normalize_attrs
# ============================================================
def test_normalize_none():
    assert normalize_attrs(None) == []
    assert normalize_attrs([]) == []


def test_normalize_list_of_str():
    result = normalize_attrs(["inline", "cold"])
    assert result == [("inline", []), ("cold", [])]


def test_normalize_list_of_tuples_with_args():
    result = normalize_attrs([("derive", ["Eq", "Debug"]), ("inline", [])])
    assert result == [("derive", ["Eq", "Debug"]), ("inline", [])]


def test_normalize_tuple_without_args():
    result = normalize_attrs([("inline",)])
    assert result == [("inline", [])]


def test_normalize_mixed_formats():
    """Mistura List[str] + Tuple é aceito."""
    result = normalize_attrs(["macro", ("derive", ["Eq"])])
    assert result == [("macro", []), ("derive", ["Eq"])]


def test_normalize_list_of_lists():
    result = normalize_attrs([["derive", "Eq", "Debug"]])
    assert result == [("derive", ["Eq", "Debug"])]


def test_normalize_ignores_malformed():
    """Entradas não reconhecidas são silenciosamente descartadas."""
    result = normalize_attrs([None, 42, ("inline",), "cold"])
    # None e 42 são descartados; ("inline",) e "cold" aceitos
    assert ("inline", []) in result
    assert ("cold", []) in result


# ============================================================
# attr_names
# ============================================================
def test_attr_names():
    assert attr_names([("derive", ["Eq"]), ("inline", [])]) == [
        "derive", "inline"
    ]


def test_attr_names_empty():
    assert attr_names(None) == []
    assert attr_names([]) == []


# ============================================================
# has_attr
# ============================================================
def test_has_attr_true():
    assert has_attr([("derive", ["Eq"])], "derive") is True
    assert has_attr(["inline"], "inline") is True


def test_has_attr_false():
    assert has_attr([("derive", ["Eq"])], "inline") is False
    assert has_attr(None, "inline") is False


# ============================================================
# get_attr_args
# ============================================================
def test_get_attr_args():
    attrs = [("derive", ["Eq", "Debug"]), ("inline", [])]
    assert get_attr_args(attrs, "derive") == ["Eq", "Debug"]
    assert get_attr_args(attrs, "inline") == []


def test_get_attr_args_missing():
    assert get_attr_args([("inline", [])], "derive") is None
    assert get_attr_args(None, "inline") is None


# ============================================================
# Integração: `@derive` no parser
# ============================================================
def test_parser_emits_normalizable_attrs():
    """O parser emite `List[Tuple[str, List]]` — normalização é no-op."""
    from lumina.lexer import Lexer
    from lumina.parser import Parser

    src = (
        '@derive(Eq, Debug)\n'
        'struct P:\n'
        '    x: int\n'
    )
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens, "<test>", src).parse()
    assert len(ast) == 1
    decl = ast[0]
    raw_attrs = getattr(decl, 'attrs', None)
    normalized = normalize_attrs(raw_attrs)
    # Deve ter pelo menos um attr "derive" com args ["Eq", "Debug"]
    assert ("derive", ["Eq", "Debug"]) in normalized, (
        f"attrs do parser não normalizam:\nraw={raw_attrs}\n"
        f"normalized={normalized}"
    )
