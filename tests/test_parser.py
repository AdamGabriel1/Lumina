"""Testes do parser.

Cobrem:
  - Funções e declarações
  - VarDecl (let, mut, :=)
  - Expressões (binárias, unárias, pipe, cast)
  - Controle de fluxo (if/elif/else, while, for)
  - Structs, enums, traits, impl
  - SliceExpr (nó dedicado)
  - Match e guard
  - Lambdas
"""
import pytest
from lumina.ast import (
    Function, StructDecl, EnumDecl, VarDecl, AssignStmt, IfStmt,
    WhileStmt, ForStmt, ReturnStmt, MatchStmt, TraitDecl, ImplBlock,
    BinaryExpr, UnaryExpr, CallExpr, IndexExpr, SliceExpr,
    MemberExpr, VariableExpr, NumberExpr, StringExpr, BoolExpr,
    LambdaExpr, CastExpr, StructLiteralExpr, ArrayExpr,
)
from lumina.errors import LuminaError


# ============================================================
# Declarações de topo
# ============================================================
def test_empty_module(parse):
    assert parse("") == []


def test_simple_function(parse):
    src = "fn main() -> int:\n    return 0\n"
    ast = parse(src)
    assert len(ast) == 1
    assert isinstance(ast[0], Function)
    assert ast[0].name == "main"
    assert ast[0].return_type == "int"


def test_function_with_params(parse):
    src = "fn soma(a: int, b: int) -> int:\n    return a + b\n"
    ast = parse(src)
    assert len(ast[0].params) == 2


def test_function_generic(parse):
    src = "fn identidade<T>(x: T) -> T:\n    return x\n"
    ast = parse(src)
    assert ast[0].type_params == ["T"]


def test_function_exported(parse):
    src = "export fn fib(n: int) -> int:\n    return n\n"
    ast = parse(src)
    assert ast[0].is_exported


def test_struct_decl(parse):
    src = "struct Ponto:\n    x: int\n    y: int\n"
    ast = parse(src)
    assert isinstance(ast[0], StructDecl)
    assert ast[0].name == "Ponto"
    assert list(ast[0].fields.keys()) == ["x", "y"]


def test_enum_decl(parse):
    src = "enum Par:\n    Dois(int, int)\n    Zero\n"
    ast = parse(src)
    assert isinstance(ast[0], EnumDecl)
    assert ast[0].name == "Par"
    assert len(ast[0].variants) == 2


def test_trait_decl(parse):
    src = "trait Greeter:\n    fn greet():\n        print(1)\n"
    ast = parse(src)
    assert isinstance(ast[0], TraitDecl)


def test_impl_block(parse):
    src = "struct A:\n    x: int\n\nimpl A:\n    fn f():\n        return 0\n"
    ast = parse(src)
    assert any(isinstance(d, ImplBlock) for d in ast)


# ============================================================
# VarDecl
# ============================================================
def test_var_decl_let(parse):
    src = "fn main() -> int:\n    let x: int = 10\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var, VarDecl)
    assert var.name == "x"
    assert var.var_type == "int"
    assert var.is_mutable is False


def test_var_decl_mut(parse):
    src = "fn main() -> int:\n    mut x: int = 10\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert var.is_mutable is True


def test_var_decl_short_syntax(parse):
    src = "fn main() -> int:\n    x := 10\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var, VarDecl)
    assert var.name == "x"
    assert var.is_mutable is True


# ============================================================
# Expressões
# ============================================================
def test_binary_add(parse):
    src = "fn main() -> int:\n    let x = 1 + 2\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, BinaryExpr)
    assert var.value.op == "+"


def test_binary_precedence(parse):
    # `1 + 2 * 3` deve parsear como `1 + (2 * 3)`
    src = "fn main() -> int:\n    let x = 1 + 2 * 3\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert var.value.op == "+"
    assert var.value.right.op == "*"


def test_pipe_operator(parse):
    src = "fn main() -> int:\n    let x = 5 |> dobrar\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    # `5 |> dobrar` vira `dobrar(5)` — CallExpr com 1 arg
    assert isinstance(var.value, CallExpr)
    assert len(var.value.args) == 1


def test_unary_negation(parse):
    src = "fn main() -> int:\n    let x = -5\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, UnaryExpr)
    assert var.value.op == "-"


def test_member_access(parse):
    src = "fn main() -> int:\n    let x = p.x\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, MemberExpr)
    assert var.value.member == "x"


def test_call_expression(parse):
    src = "fn main() -> int:\n    let x = foo(1, 2, 3)\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, CallExpr)
    assert len(var.value.args) == 3


def test_cast_expression(parse):
    src = "fn main() -> int:\n    let x = 10 as float\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, CastExpr)
    assert var.value.target_type == "float"


def test_array_literal(parse):
    src = "fn main() -> int:\n    let x = [1, 2, 3]\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, ArrayExpr)


def test_struct_literal(parse):
    src = (
        "struct P:\n    x: int\n    y: int\n\n"
        "fn main() -> int:\n    let p = P { x: 1, y: 2 }\n    return 0\n"
    )
    ast = parse(src)
    var = ast[1].body[0]
    assert isinstance(var.value, StructLiteralExpr)


# ============================================================
# Index e Slice
# ============================================================
def test_index_simple(parse):
    src = "fn main() -> int:\n    let x = arr[2]\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, IndexExpr)
    assert not isinstance(var.value, SliceExpr)


def test_slice_full(parse):
    src = "fn main() -> int:\n    let x = arr[1..3]\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, SliceExpr)
    assert var.value.start is not None
    assert var.value.end is not None


def test_slice_from_start(parse):
    src = "fn main() -> int:\n    let x = arr[..3]\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, SliceExpr)
    assert var.value.start is None
    assert var.value.end is not None


def test_slice_to_end(parse):
    src = "fn main() -> int:\n    let x = arr[2..]\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, SliceExpr)
    assert var.value.start is not None
    assert var.value.end is None


def test_slice_entire(parse):
    src = "fn main() -> int:\n    let x = arr[..]\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, SliceExpr)
    assert var.value.start is None
    assert var.value.end is None


# ============================================================
# Controle de fluxo
# ============================================================
def test_if_simple(parse):
    src = "fn main() -> int:\n    if x:\n        return 1\n    return 0\n"
    ast = parse(src)
    assert isinstance(ast[0].body[0], IfStmt)


def test_if_else(parse):
    src = (
        "fn main() -> int:\n"
        "    if x:\n"
        "        return 1\n"
        "    else:\n"
        "        return 0\n"
    )
    ast = parse(src)
    if_stmt = ast[0].body[0]
    assert if_stmt.else_body is not None


def test_if_elif_else(parse):
    src = (
        "fn main() -> int:\n"
        "    if x == 1:\n"
        "        return 1\n"
        "    elif x == 2:\n"
        "        return 2\n"
        "    else:\n"
        "        return 3\n"
    )
    ast = parse(src)
    if_stmt = ast[0].body[0]
    assert if_stmt.else_body is not None
    # O elif vira um IfStmt dentro do else_body
    assert isinstance(if_stmt.else_body[0], IfStmt)


def test_while(parse):
    src = "fn main() -> int:\n    while x < 10:\n        x = x + 1\n    return 0\n"
    ast = parse(src)
    assert isinstance(ast[0].body[0], WhileStmt)


def test_for_range(parse):
    src = "fn main() -> int:\n    for i in 0..10:\n        print(i)\n    return 0\n"
    ast = parse(src)
    for_stmt = ast[0].body[0]
    assert isinstance(for_stmt, ForStmt)
    assert for_stmt.var_name == "i"


# ============================================================
# Match
# ============================================================
def test_match_simple(parse):
    src = (
        "fn main() -> int:\n"
        "    match x:\n"
        "        case 1: return 1\n"
        "        default: return 0\n"
    )
    ast = parse(src)
    assert isinstance(ast[0].body[0], MatchStmt)


def test_match_with_guard(parse):
    src = (
        "fn main() -> int:\n"
        "    match x:\n"
        "        case n if n > 10: return 1\n"
        "        default: return 0\n"
    )
    ast = parse(src)
    match_stmt = ast[0].body[0]
    # Case 0 tem guard
    assert match_stmt.cases[0][2] is not None


# ============================================================
# Lambda
# ============================================================
def test_lambda_inline(parse):
    src = "fn main() -> int:\n    let f = fn(x: int) -> int: x * 2\n    return 0\n"
    ast = parse(src)
    var = ast[0].body[0]
    assert isinstance(var.value, LambdaExpr)


# ============================================================
# Erros
# ============================================================
def test_invalid_toplevel(parse):
    with pytest.raises(LuminaError, match="Declaração de nível superior inválida"):
        parse("xyz")


def test_missing_rparen(parse):
    with pytest.raises(LuminaError):
        parse("fn main(:\n    return 0\n")
