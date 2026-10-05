import pytest
from lumina.lexer import Lexer
from lumina.parser import Parser
from lumina.semantic import SemanticAnalyzer
from lumina.errors import LuminaError


def _analyze(src):
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens, "<test>", src).parse()
    SemanticAnalyzer("<test>", src).analyze(ast)


# ============================================================
# VarDecl
# ============================================================
def test_var_decl_type_mismatch():
    src = 'fn main() -> int:\n    let x: int = "texto"\n    return 0\n'
    with pytest.raises(LuminaError, match="Tipo inválido em declaração de 'x'"):
        _analyze(src)


def test_var_decl_ok():
    src = 'fn main() -> int:\n    let x: int = 10\n    return 0\n'
    _analyze(src)


def test_int_to_float_promotion():
    src = 'fn main() -> int:\n    let x: float = 10\n    return 0\n'
    _analyze(src)


def test_string_to_int_rejected():
    src = 'fn main() -> int:\n    let x: str = 42\n    return 0\n'
    with pytest.raises(LuminaError, match="Tipo inválido"):
        _analyze(src)


# ============================================================
# ReturnStmt
# ============================================================
def test_return_type_mismatch():
    src = 'fn f() -> int:\n    return "texto"\n\nfn main() -> int:\n    return 0\n'
    with pytest.raises(LuminaError, match="Tipo inválido em retorno de 'f'"):
        _analyze(src)


# ============================================================
# AssignStmt
# ============================================================
def test_assign_type_mismatch():
    src = (
        'fn main() -> int:\n'
        '    mut x: int = 10\n'
        '    x = "texto"\n'
        '    return 0\n'
    )
    with pytest.raises(LuminaError, match="Tipo inválido em atribuição"):
        _analyze(src)


def test_assign_to_immutable_rejected():
    src = (
        'fn main() -> int:\n'
        '    let x: int = 10\n'
        '    x = 20\n'
        '    return 0\n'
    )
    with pytest.raises(LuminaError, match="imutável"):
        _analyze(src)


# ============================================================
# Condições: bool e int aceitos; outros rejeitados
# ============================================================
def test_if_condition_bool_ok():
    src = 'fn main() -> int:\n    if true:\n        return 1\n    return 0\n'
    _analyze(src)


def test_if_condition_int_ok():
    # `if <int>` é permitido (0 = false, != 0 = true), idiomático em C/Python
    src = 'fn main() -> int:\n    if 5:\n        return 1\n    return 0\n'
    _analyze(src)


def test_if_condition_string_rejected():
    src = 'fn main() -> int:\n    if "texto":\n        return 1\n    return 0\n'
    with pytest.raises(LuminaError, match="Condição de 'if'"):
        _analyze(src)


def test_while_condition_bool_ok():
    src = (
        'fn main() -> int:\n'
        '    mut i = 0\n'
        '    while i < 5:\n'
        '        i = i + 1\n'
        '    return 0\n'
    )
    _analyze(src)


def test_while_condition_string_rejected():
    src = (
        'fn main() -> int:\n'
        '    while "texto":\n'
        '        return 0\n'
        '    return 0\n'
    )
    with pytest.raises(LuminaError, match="Condição de 'while'"):
        _analyze(src)


def test_assert_bool_ok():
    src = 'fn main() -> int:\n    assert(true)\n    return 0\n'
    _analyze(src)


def test_assert_string_rejected():
    src = 'fn main() -> int:\n    assert("texto")\n    return 0\n'
    with pytest.raises(LuminaError, match="Condição de 'assert'"):
        _analyze(src)


# ============================================================
# Funções
# ============================================================
def test_function_arity_mismatch():
    src = (
        'fn soma(a: int, b: int) -> int:\n'
        '    return a + b\n'
        '\n'
        'fn main() -> int:\n'
        '    let x = soma(1)\n'
        '    return 0\n'
    )
    with pytest.raises(LuminaError, match="espera 2 args"):
        _analyze(src)


def test_function_arg_type_mismatch():
    src = (
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    let y = dobro("texto")\n'
        '    return 0\n'
    )
    with pytest.raises(LuminaError, match="Tipo inválido"):
        _analyze(src)


# ============================================================
# Variáveis
# ============================================================
def test_undeclared_variable():
    src = 'fn main() -> int:\n    let x = y\n    return 0\n'
    with pytest.raises(LuminaError, match="não declarada"):
        _analyze(src)


def test_suggestion_for_typo():
    src = (
        'fn main() -> int:\n'
        '    let contador = 10\n'
        '    return contadro\n'
    )
    with pytest.raises(LuminaError, match="Você quis dizer 'contador'"):
        _analyze(src)


# ============================================================
# Estruturas
# ============================================================
def test_undefined_struct_rejected():
    src = 'fn main() -> int:\n    let p: Pessoa = none\n    return 0\n'
    with pytest.raises(LuminaError, match="não declarado"):
        _analyze(src)


def test_struct_literal_ok():
    src = (
        'struct Ponto:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = Ponto { x: 1, y: 2 }\n'
        '    return 0\n'
    )
    _analyze(src)


def test_struct_literal_missing_field():
    src = (
        'struct Ponto:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = Ponto { x: 1 }\n'
        '    return 0\n'
    )
    with pytest.raises(LuminaError, match="Campos faltando"):
        _analyze(src)


def test_struct_literal_unknown_field():
    src = (
        'struct Ponto:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = Ponto { x: 1, y: 2, z: 3 }\n'
        '    return 0\n'
    )
    with pytest.raises(LuminaError, match="não existe"):
        _analyze(src)


# ============================================================
# Generics
# ============================================================
def test_generic_identity_ok():
    src = (
        'fn identidade<T>(x: T) -> T:\n'
        '    return x\n'
        '\n'
        'fn main() -> int:\n'
        '    let a = identidade(10)\n'
        '    let b = identidade(3.14)\n'
        '    return 0\n'
    )
    _analyze(src)


# ============================================================
# Enums / match
# ============================================================
def test_enum_multi_payload_ok():
    src = (
        'enum Par:\n'
        '    Dois(int, int)\n'
        '    Zero\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = Dois(1, 2)\n'
        '    match p:\n'
        '        case Dois(a, b): return a\n'
        '        case Zero: return 0\n'
        '    return 0\n'
    )
    _analyze(src)