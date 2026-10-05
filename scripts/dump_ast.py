#!/usr/bin/env python3
"""Dumpa a AST do parser Python no mesmo formato do `dump_node`
self-hosted (`lumina_core/parser.lm`).

Formato: `<depth> <KIND> <payload>`
Ordem dos filhos: left → right → ext → body (todos via sibling chain).

Uso:
    python3 scripts/dump_ast.py <arquivo.lm>
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lumina.lexer import Lexer
from lumina.parser import Parser
from lumina.ast import (
    Function, VarDecl, Param, ReturnStmt, IfStmt, WhileStmt, ForStmt,
    BreakStmt, ContinueStmt, ImportStmt, ExternDecl, DeferStmt, AssertStmt,
    BenchStmt, MatchStmt, CompoundAssignStmt, DestructureStmt,
    NumberExpr, StringExpr, BoolExpr, VariableExpr, BinaryExpr, UnaryExpr,
    CallExpr, ArrayExpr, IndexExpr, SliceExpr, MemberExpr,
    AddressOfExpr, DerefExpr, PropagateExpr, ComptimeExpr,
    StructLiteralExpr, CastExpr, LambdaExpr, NoneExpr, NilExpr, TupleExpr,
    InterpolatedStringExpr, StructDecl, EnumDecl, TraitDecl, ImplBlock,
    TypeAlias, AssignStmt, MatchExpr,
    ChainedComparisonExpr,
)
from lumina.ast.expressions import StructLiteralField


KIND_NAMES = {
    "Program": "PROGRAM",
    "Function": "FUNCTION",
    "Param": "PARAM",
    "VarDecl": "VAR_DECL",
    "AssignStmt": "ASSIGN",
    "ReturnStmt": "RETURN",
    "IfStmt": "IF",
    "WhileStmt": "WHILE",
    "ForStmt": "FOR",
    "BreakStmt": "BREAK",
    "ContinueStmt": "CONTINUE",
    "ImportStmt": "IMPORT",
    "ExternDecl": "EXTERN",
    "DeferStmt": "DEFER",
    "AssertStmt": "ASSERT",
    "BenchStmt": "BENCH",
    "MatchStmt": "MATCH",
    "CompoundAssignStmt": "COMPOUND_ASSIGN",
    "DestructureStmt": "DESTRUCTURE",
    "BinaryExpr": "BINARY",
    "UnaryExpr": "UNARY",
    "NumberExpr": "NUMBER",
    "StringExpr": "STRING",
    "BoolExpr": "BOOL",
    "VariableExpr": "VARIABLE",
    "CallExpr": "CALL",
    "ArrayExpr": "ARRAY",
    "IndexExpr": "INDEX",
    "SliceExpr": "SLICE",
    "MemberExpr": "MEMBER",
    "AddressOfExpr": "ADDRESS_OF",
    "DerefExpr": "DEREF",
    "PropagateExpr": "PROPAGATE",
    "ComptimeExpr": "COMPTIME",
    "StructLiteralExpr": "STRUCT_LITERAL",
    "CastExpr": "CAST",
    "LambdaExpr": "LAMBDA",
    "NoneExpr": "NONE",
    "NilExpr": "NIL",
    "TupleExpr": "TUPLE",
    "InterpolatedStringExpr": "FSTRING",
    "StructDecl": "STRUCT_DECL",
    "EnumDecl": "ENUM_DECL",
    "TraitDecl": "TRAIT_DECL",
    "ImplBlock": "IMPL_BLOCK",
    "TypeAlias": "TYPE_ALIAS",
    "StructLiteralField": "FIELD",
    "MatchExpr": "MATCH",
}


def kind_name(node):
    return KIND_NAMES.get(type(node).__name__, type(node).__name__.upper())


def payload(node):
    """Payload textual — mesma lógica de `_payload_for_dump` no self-hosted.

    Nós cujo str_val é `name:type` no self-hosted emitem só o `name`.
    Outros emitem o valor bruto.
    """
    if isinstance(node, (Function, VarDecl, Param, ExternDecl,
                         StructDecl, EnumDecl, TypeAlias, ImplBlock)):
        if isinstance(node, ImplBlock):
            return node.struct_name
        return getattr(node, 'name', '')
    if isinstance(node, ForStmt):
        return node.var_name
    if isinstance(node, StructLiteralField):
        return node.name
    if isinstance(node, (NumberExpr, StringExpr)):
        return node.value
    if isinstance(node, BoolExpr):
        return "true" if node.value else "false"
    if isinstance(node, VariableExpr):
        return node.name
    if isinstance(node, (BinaryExpr, UnaryExpr)):
        return node.op
    if isinstance(node, MemberExpr):
        return node.member
    if isinstance(node, CastExpr):
        return node.target_type
    if isinstance(node, ImportStmt):
        return node.filename
    if isinstance(node, StructLiteralExpr):
        return node.struct_name
    if isinstance(node, CallExpr):
        # Sem payload — o nome fica no filho callee.
        return ""
    if isinstance(node, InterpolatedStringExpr):
        return ""
    if isinstance(node, CompoundAssignStmt):
        return node.op
    return ""


def emit(node, depth):
    print(f"{depth} {kind_name(node)} {payload(node)}")


def dump_sibling(nodes, depth):
    """Percorre uma lista de nós, emitindo cada um no `depth`."""
    if nodes is None:
        return
    for n in nodes:
        dump_node(n, depth)


def _as_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def dump_node(node, depth):
    if node is None:
        return

    # ChainedComparisonExpr é desugarizado para BinaryExpr aninhado
    # antes de emitir. Não emite header próprio — o self-hosted
    # parseia direto como BinaryExpr aninhado.
    if isinstance(node, ChainedComparisonExpr):
        left = node.operands[0]
        for i, op in enumerate(node.ops):
            right = node.operands[i + 1]
            left = BinaryExpr(op, left, right)
        dump_node(left, depth)
        return

    emit(node, depth)

    # ordem: left → right → ext → body, espelhando dump_node do self-hosted.

    if isinstance(node, Function):
        dump_sibling(_as_list(node.params), depth + 1)
        dump_sibling(_as_list(node.body), depth + 1)

    elif isinstance(node, VarDecl):
        if node.value is not None:
            dump_node(node.value, depth + 1)

    elif isinstance(node, AssignStmt):
        dump_node(node.target, depth + 1)
        dump_node(node.value, depth + 1)

    elif isinstance(node, CompoundAssignStmt):
        dump_node(node.target, depth + 1)
        dump_node(node.value, depth + 1)

    elif isinstance(node, ReturnStmt):
        dump_sibling(_as_list(node.values), depth + 1)

    elif isinstance(node, IfStmt):
        dump_node(node.condition, depth + 1)
        if node.else_body:
            dump_sibling(node.else_body, depth + 1)
        if node.then_body:
            dump_sibling(node.then_body, depth + 1)

    elif isinstance(node, WhileStmt):
        dump_node(node.condition, depth + 1)
        dump_sibling(node.body, depth + 1)

    elif isinstance(node, ForStmt):
        if node.iterable is not None:
            dump_node(node.iterable, depth + 1)
        if node.start is not None:
            dump_node(node.start, depth + 1)
        if node.end is not None:
            dump_node(node.end, depth + 1)
        dump_sibling(node.body, depth + 1)

    elif isinstance(node, BinaryExpr):
        dump_node(node.left, depth + 1)
        dump_node(node.right, depth + 1)


    elif isinstance(node, ChainedComparisonExpr):
        # Desugar para BinaryExpr aninhado, alinhando com o parser
        # self-hosted (que parseia `0 < x < 10` como `(0 < x) < 10`).
        left = node.operands[0]
        for i, op in enumerate(node.ops):
            right = node.operands[i + 1]
            left = BinaryExpr(op, left, right)
        dump_node(left, depth)

    elif isinstance(node, UnaryExpr):
        dump_node(node.val, depth + 1)

    elif isinstance(node, CallExpr):
        callee = node.callee
        if isinstance(callee, MemberExpr):
            # self-hosted normaliza callee de método para VARIABLE <name>
            # (perde o wrapping de MemberExpr). Emitimos igual.
            print(f"{depth + 1} VARIABLE {callee.member}")
        else:
            dump_node(callee, depth + 1)
        dump_sibling(_as_list(node.args), depth + 1)

    elif isinstance(node, ArrayExpr):
        dump_sibling(_as_list(node.elements), depth + 1)

    elif isinstance(node, TupleExpr):
        dump_sibling(_as_list(node.elements), depth + 1)

    elif isinstance(node, IndexExpr):
        dump_node(node.array, depth + 1)
        dump_node(node.index, depth + 1)

    elif isinstance(node, SliceExpr):
        dump_node(node.array, depth + 1)
        if node.start is not None:
            dump_node(node.start, depth + 1)
        if node.end is not None:
            dump_node(node.end, depth + 1)

    elif isinstance(node, MemberExpr):
        dump_node(node.obj, depth + 1)

    elif isinstance(node, AddressOfExpr):
        dump_node(node.val, depth + 1)

    elif isinstance(node, DerefExpr):
        dump_node(node.val, depth + 1)

    elif isinstance(node, PropagateExpr):
        dump_node(node.val, depth + 1)

    elif isinstance(node, CastExpr):
        dump_node(node.expr, depth + 1)

    elif isinstance(node, LambdaExpr):
        dump_sibling(_as_list(node.params), depth + 1)
        dump_sibling(_as_list(node.body), depth + 1)

    elif isinstance(node, StructLiteralExpr):
        for f in node.fields:
            emit(f, depth + 1)
            dump_node(f.value, depth + 2)

    elif isinstance(node, StructDecl):
        for fname, ftype in node.fields.items():
            # Emitir FIELD com payload `name:type`
            print(f"{depth + 1} FIELD {fname}")

    elif isinstance(node, ImplBlock):
        dump_sibling(_as_list(node.methods), depth + 1)

    elif isinstance(node, TraitDecl):
        dump_sibling(_as_list(node.methods), depth + 1)

    elif isinstance(node, EnumDecl):
        for vname, payloads in node.variants:
            print(f"{depth + 1} ENUM_VARIANT {vname}")

    elif isinstance(node, MatchStmt):
        dump_node(node.condition, depth + 1)
        for case in node.cases:
            if len(case) >= 4:
                variant, binding, guard, body = case
                # NONE wrapper: alinha com self-hosted, que usa um
                # NK_NONE intermediário para agrupar (variant + body).
                print(f"{depth + 1} NONE ")
                if isinstance(variant, str):
                    print(f"{depth + 2} VARIABLE {variant}")
                elif variant is not None:
                    dump_node(variant, depth + 2)
                if binding:
                    bs = binding if isinstance(binding, list) else [binding]
                    for b in bs:
                        print(f"{depth + 2} VARIABLE {b}")
                dump_sibling(body, depth + 2)
        if node.default:
            dump_sibling(node.default, depth + 1)

    elif isinstance(node, MatchExpr):
        # MatchExpr.cases: lista de tuplas (val, res).
        dump_node(node.condition, depth + 1)
        for case in node.cases:
            if isinstance(case, tuple) and len(case) >= 2:
                val, res = case
                print(f"{depth + 1} NONE ")
                dump_node(val, depth + 2)
                dump_node(res, depth + 2)
        if node.default:
            dump_node(node.default, depth + 1)

    elif isinstance(node, ComptimeExpr):
        # O self-hosted não faz constant folding no dump; percorre
        # o `.expr` original. Alinha aqui.
        dump_node(node.expr, depth + 1)

    elif isinstance(node, DeferStmt):
        dump_sibling(_as_list(node.body), depth + 1)

    elif isinstance(node, AssertStmt):
        dump_node(node.condition, depth + 1)

    elif isinstance(node, BenchStmt):
        dump_sibling(_as_list(node.body), depth + 1)

    elif isinstance(node, DestructureStmt):
        dump_node(node.value, depth + 1)

    elif isinstance(node, ImportStmt):
        pass

    elif isinstance(node, ExternDecl):
        dump_sibling(_as_list(node.params), depth + 1)


def main():
    if len(sys.argv) < 2:
        print("uso: dump_ast.py <arquivo.lm>", file=sys.stderr)
        return 1

    path = sys.argv[1]
    src = Path(path).read_text()
    tokens = Lexer(src, path).tokenize()
    ast = Parser(tokens, path, src).parse()

    # Espelha o main do self-hosted: PROGRAM na raiz + decls em depth 1.
    print("0 PROGRAM ")
    for decl in ast:
        dump_node(decl, 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())