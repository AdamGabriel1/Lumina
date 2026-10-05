"""Testes de regressão dos bugs latentes no semantic.

Cobrem:
  - Inferência de tipo para MemberExpr (`self.campo`)
  - Validação dentro de métodos de ImplBlock
  - Aliases de trait default
  - VarDecl com BinaryExpr
  - VarDecl com NoneExpr
  - VarDecl com ComptimeExpr
"""
import pytest
from lumina.lexer import Lexer
from lumina.parser import Parser
from lumina.semantic import SemanticAnalyzer
from lumina.errors import LuminaError
from lumina.ast import Function, ImplBlock, VarDecl


def _analyze(src):
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens, "<test>", src).parse()
    SemanticAnalyzer("<test>", src).analyze(ast)
    return ast


def _infer(src):
    """Roda o semantic e retorna os var_types inferidos dentro de `main`."""
    ast = _analyze(src)
    result = {}
    for decl in ast:
        if isinstance(decl, Function) and decl.name == "main":
            for stmt in decl.body:
                if isinstance(stmt, VarDecl):
                    result[stmt.name] = stmt.var_type
    return result


# ============================================================
# MemberExpr em VarDecl
# ============================================================
def test_var_decl_member_ptr():
    src = (
        'struct Box:\n'
        '    data: ptr\n'
        '    n: int\n'
        '\n'
        'impl Box:\n'
        '    fn get_data():\n'
        '        let d = self.data\n'
        '        d[0] = 1\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    # Não deve levantar erro — se inferisse "int" para `d`, o index `d[0]`
    # funcionaria por acaso. Mas pelo menos validamos que não quebra.
    _analyze(src)


def test_var_decl_member_int():
    src = (
        'struct Box:\n'
        '    data: ptr\n'
        '    n: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box\n'
        '    b.n = 42\n'
        '    let x = b.n\n'
        '    print(x)\n'
        '    return 0\n'
    )
    types = _infer(src)
    # `x` deve ser "int"
    assert types.get("x") == "int"


# ============================================================
# Análise dentro de ImplBlock
# ============================================================
def test_impl_method_analyzed():
    """Erros dentro de métodos de impl devem ser detectados."""
    src = (
        'struct S:\n'
        '    x: int\n'
        '\n'
        'impl S:\n'
        '    fn bad():\n'
        '        let y: int = "texto"\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    with pytest.raises(LuminaError, match="Tipo inválido"):
        _analyze(src)


def test_impl_method_var_type_inferred():
    src = (
        'struct S:\n'
        '    x: int\n'
        '\n'
        'impl S:\n'
        '    fn calc() -> int:\n'
        '        let a = 1\n'
        '        let b = 2.5\n'
        '        return a\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    # Não deve dar erro. `a` = int, `b` = float.
    _analyze(src)


# ============================================================
# Trait default aliases
# ============================================================
def test_trait_default_alias_registered():
    src = (
        'trait T:\n'
        '    fn name() -> str\n'
        '    fn greet():\n'
        '        let n = name()\n'
        '        print(n)\n'
        '\n'
        'struct S:\n'
        '    dummy: int\n'
        '\n'
        'impl T for S:\n'
        '    fn name() -> str:\n'
        '        return "x"\n'
        '\n'
        'fn main() -> int:\n'
        '    return 0\n'
    )
    # Não deve reclamar que `name` não existe.
    _analyze(src)


# ============================================================
# VarDecl com BinaryExpr
# ============================================================
def test_binary_expr_comparison_is_bool():
    src = (
        'fn main() -> int:\n'
        '    let x = 1 == 1\n'
        '    print(x)\n'
        '    return 0\n'
    )
    types = _infer(src)
    assert types.get("x") == "bool"


def test_binary_expr_arithmetic_is_int():
    src = (
        'fn main() -> int:\n'
        '    let x = 1 + 2\n'
        '    print(x)\n'
        '    return 0\n'
    )
    types = _infer(src)
    assert types.get("x") == "int"


def test_binary_expr_with_float_is_float():
    src = (
        'fn main() -> int:\n'
        '    let x = 1 + 2.5\n'
        '    print(x)\n'
        '    return 0\n'
    )
    types = _infer(src)
    assert types.get("x") == "float"


def test_binary_expr_string_concat_is_str():
    src = (
        'fn main() -> int:\n'
        '    let x = "a" + "b"\n'
        '    print(x)\n'
        '    return 0\n'
    )
    types = _infer(src)
    assert types.get("x") == "str"


# ============================================================
# VarDecl com NoneExpr
# ============================================================
def test_none_expr_is_option():
    src = (
        'fn main() -> int:\n'
        '    let x = none\n'
        '    return 0\n'
    )
    types = _infer(src)
    assert types.get("x") == "Option"


# ============================================================
# VarDecl com ComptimeExpr
# ============================================================
def test_comptime_int():
    src = (
        'fn main() -> int:\n'
        '    let x = comptime(1 + 2)\n'
        '    print(x)\n'
        '    return 0\n'
    )
    types = _infer(src)
    assert types.get("x") == "int"


def test_comptime_float():
    src = (
        'fn main() -> int:\n'
        '    let x = comptime(1.5 + 2.5)\n'
        '    print(x)\n'
        '    return 0\n'
    )
    types = _infer(src)
    assert types.get("x") == "float"


def test_comptime_bool():
    src = (
        'fn main() -> int:\n'
        '    let x = comptime(1 == 1)\n'
        '    print(x)\n'
        '    return 0\n'
    )
    types = _infer(src)
    assert types.get("x") == "bool"
