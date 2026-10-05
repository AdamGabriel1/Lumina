"""Testes do semantic (além dos de test_types.py).

Cobrem:
  - Escopo de bloco
  - Exaustividade de match
  - Traits com método default
  - Métodos e associação struct+impl
  - Nested functions
  - Redeclaração
"""
import pytest
from lumina.errors import LuminaError


def _check_ok(analyze, src):
    analyze(src)


def _check_fails(analyze, src, match=None):
    with pytest.raises(LuminaError, match=match):
        analyze(src)


# ============================================================
# Escopo
# ============================================================
def test_block_scope(analyze):
    src = (
        "fn main() -> int:\n"
        "    if true:\n"
        "        let temp = 100\n"
        "        print(temp)\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


def test_block_scope_var_not_visible_outside(analyze):
    src = (
        "fn main() -> int:\n"
        "    if true:\n"
        "        let temp = 100\n"
        "    print(temp)\n"
        "    return 0\n"
    )
    _check_fails(analyze, src, match="não declarada")


def test_while_body_variables(analyze):
    src = (
        "fn main() -> int:\n"
        "    mut i = 0\n"
        "    while i < 5:\n"
        "        let x = i * 2\n"
        "        i = i + 1\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


def test_for_loop_variable_in_scope(analyze):
    src = (
        "fn main() -> int:\n"
        "    for i in 0..10:\n"
        "        print(i)\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


# ============================================================
# Funções
# ============================================================
def test_forward_reference(analyze):
    # Função pode chamar outra definida depois
    src = (
        "fn main() -> int:\n"
        "    return soma(1, 2)\n"
        "\n"
        "fn soma(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )
    _check_ok(analyze, src)


def test_recursion(analyze):
    src = (
        "fn fact(n: int) -> int:\n"
        "    if n <= 1:\n"
        "        return 1\n"
        "    return n * fact(n - 1)\n"
        "\n"
        "fn main() -> int:\n"
        "    return fact(5)\n"
    )
    _check_ok(analyze, src)


def test_duplicate_function_definition(analyze):
    # Hoje o semantic não reclama — testa que não crasha
    src = (
        "fn f() -> int:\n"
        "    return 1\n"
        "\n"
        "fn f() -> int:\n"
        "    return 2\n"
        "\n"
        "fn main() -> int:\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


# ============================================================
# Structs
# ============================================================
def test_struct_field_access(analyze):
    src = (
        "struct P:\n"
        "    x: int\n"
        "    y: int\n"
        "\n"
        "fn main() -> int:\n"
        "    let p = P { x: 1, y: 2 }\n"
        "    return p.x\n"
    )
    _check_ok(analyze, src)


def test_struct_field_wrong_type(analyze):
    src = (
        'struct P:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = P { x: "texto", y: 2 }\n'
        '    return 0\n'
    )
    _check_fails(analyze, src, match="Tipo inválido para campo 'x'")


# ============================================================
# Enums e match
# ============================================================
def test_match_exhaustive(analyze):
    src = (
        "enum Par:\n"
        "    Dois(int, int)\n"
        "    Zero\n"
        "\n"
        "fn main() -> int:\n"
        "    let p = Dois(1, 2)\n"
        "    match p:\n"
        "        case Dois(a, b): return a\n"
        "        case Zero: return 0\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


def test_match_non_exhaustive(analyze):
    src = (
        "enum Par:\n"
        "    Dois(int, int)\n"
        "    Zero\n"
        "\n"
        "fn main() -> int:\n"
        "    let p = Dois(1, 2)\n"
        "    match p:\n"
        "        case Dois(a, b): return a\n"
        "    return 0\n"
    )
    _check_fails(analyze, src, match="não exaustivo|Faltam variantes")


# ============================================================
# Traits
# ============================================================
def test_trait_default_method(analyze):
    src = (
        "trait Greeter:\n"
        "    fn greet() -> int:\n"
        "        print(1)\n"
        "        return 0\n"
        "\n"
        "struct English:\n"
        "    dummy: int\n"
        "\n"
        "impl Greeter for English:\n"
        "    fn greet() -> int:\n"
        "        return 0\n"
        "\n"
        "fn main() -> int:\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


# ============================================================
# Retorno de função
# ============================================================
def test_return_type_from_call(analyze):
    src = (
        "fn dobro(x: int) -> int:\n"
        "    return x * 2\n"
        "\n"
        "fn main() -> int:\n"
        "    let y = dobro(10)\n"
        "    return y\n"
    )
    _check_ok(analyze, src)


# ============================================================
# Variáveis
# ============================================================
def test_redeclaration_in_same_scope(analyze):
    # Redeclarar no mesmo escopo: hoje passa (shadowing silencioso)
    src = (
        "fn main() -> int:\n"
        "    let x = 1\n"
        "    let x = 2\n"
        "    return x\n"
    )
    _check_ok(analyze, src)


def test_variable_from_outer_scope(analyze):
    src = (
        "fn main() -> int:\n"
        "    let x = 10\n"
        "    if true:\n"
        "        return x\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


# ============================================================
# Loops
# ============================================================
def test_break_inside_loop(analyze):
    src = (
        "fn main() -> int:\n"
        "    for i in 0..10:\n"
        "        if i == 5:\n"
        "            break\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


def test_continue_inside_loop(analyze):
    src = (
        "fn main() -> int:\n"
        "    for i in 0..10:\n"
        "        if i == 5:\n"
        "            continue\n"
        "        print(i)\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


# ============================================================
# Defer / assert
# ============================================================
def test_defer(analyze):
    src = (
        "fn main() -> int:\n"
        "    defer print(1)\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)


def test_assert(analyze):
    src = (
        "fn main() -> int:\n"
        "    assert(1 == 1)\n"
        "    return 0\n"
    )
    _check_ok(analyze, src)
