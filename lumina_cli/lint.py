"""`lumina lint` — análise estática sem gerar código.

Checks:
  W001: variável declarada e nunca usada
  W002: variável sombrando outra do mesmo escopo
  W003: código inalcançável após return/break/continue
  W004: parâmetro de função nunca usado
  W005: função com corpo vazio

Exit code = nº de warnings (0 = limpo).
"""
import json

from lumina.ast import (
    Function, VarDecl, VariableExpr, CallExpr, AssignStmt, ReturnStmt,
    BreakStmt, ContinueStmt, IfStmt, WhileStmt, ForStmt, MatchStmt,
    DeferStmt, BenchStmt, MemberExpr, IndexExpr,
    UnaryExpr, BinaryExpr, StructLiteralExpr, LambdaExpr,
    CastExpr, DerefExpr, AddressOfExpr, PropagateExpr,
    ImportStmt, ExternDecl,
    StringExpr, NumberExpr, BoolExpr, ArrayExpr, TupleExpr,
    SliceExpr, NoneExpr, NilExpr, ComptimeExpr, InterpolatedStringExpr,
)
from lumina.lexer import Lexer
from lumina.parser import Parser
from lumina.errors import LuminaError

from .utils import Color, paint, info, success


class Warning:
    __slots__ = ("code", "message", "line", "col")

    def __init__(self, code, message, line=0, col=0):
        self.code = code
        self.message = message
        self.line = line
        self.col = col


def _collect(node, into):
    """Coleta todos os nomes de VariableExpr em `node`, recursivamente.

    Aceita listas (para iterar blocos), statements e expressões.
    Um único ponto de entrada evita a recursão mútua que estourava
    a stack em versões anteriores.
    """
    if node is None:
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            _collect(item, into)
        return

    # ----- Expressões -----
    if isinstance(node, VariableExpr):
        into.add(node.name)
        return
    if isinstance(node, CallExpr):
        _collect(node.callee, into)
        for a in node.args:
            _collect(a, into)
        return
    if isinstance(node, BinaryExpr):
        _collect(node.left, into)
        _collect(node.right, into)
        return
    if isinstance(node, UnaryExpr):
        _collect(node.val, into)
        return
    if isinstance(node, MemberExpr):
        _collect(node.obj, into)
        return
    if isinstance(node, IndexExpr):
        _collect(node.array, into)
        _collect(node.index, into)
        return
    if isinstance(node, SliceExpr):
        _collect(node.array, into)
        if node.start is not None:
            _collect(node.start, into)
        if node.end is not None:
            _collect(node.end, into)
        return
    if isinstance(node, StructLiteralExpr):
        for f in node.fields:
            _collect(f.value, into)
        return
    if isinstance(node, LambdaExpr):
        _collect(node.body, into)
        return
    if isinstance(node, CastExpr):
        _collect(node.expr, into)
        return
    if isinstance(node, DerefExpr):
        _collect(node.val, into)
        return
    if isinstance(node, AddressOfExpr):
        _collect(node.val, into)
        return
    if isinstance(node, PropagateExpr):
        _collect(node.val, into)
        return
    if isinstance(node, ComptimeExpr):
        _collect(node.expr, into)
        return
    if isinstance(node, InterpolatedStringExpr):
        _collect(node.parts, into)
        return
    if isinstance(node, ArrayExpr):
        _collect(node.elements, into)
        return
    if isinstance(node, TupleExpr):
        _collect(node.elements, into)
        return
    if isinstance(node, (NumberExpr, StringExpr, BoolExpr, NoneExpr, NilExpr)):
        return

    # ----- Statements -----
    if isinstance(node, VarDecl):
        _collect(node.value, into)
        return
    if isinstance(node, AssignStmt):
        _collect(node.target, into)
        _collect(node.value, into)
        return
    if isinstance(node, ReturnStmt):
        _collect(node.values, into)
        return
    if isinstance(node, IfStmt):
        _collect(node.condition, into)
        _collect(node.then_body, into)
        _collect(node.else_body, into)
        return
    if isinstance(node, WhileStmt):
        _collect(node.condition, into)
        _collect(node.body, into)
        return
    if isinstance(node, ForStmt):
        if node.iterable is not None:
            _collect(node.iterable, into)
        if node.start is not None:
            _collect(node.start, into)
        if node.end is not None:
            _collect(node.end, into)
        _collect(node.body, into)
        return
    if isinstance(node, MatchStmt):
        _collect(node.condition, into)
        for c in node.cases:
            if len(c) >= 4:
                if c[2] is not None:
                    _collect(c[2], into)
                if isinstance(c[3], list):
                    _collect(c[3], into)
        _collect(node.default, into)
        return
    if isinstance(node, (DeferStmt, BenchStmt)):
        _collect(node.body, into)
        return
    # Function / StructDecl / EnumDecl / ImportStmt / ExternDecl
    # → não percorremos aqui (são top-level).


# ============================================================
# Checks
# ============================================================
def _check_unused(decls, warnings):
    for d in decls:
        if isinstance(d, Function):
            _check_unused_fn(d, warnings)
        elif hasattr(d, 'methods'):
            for m in d.methods:
                _check_unused_fn(m, warnings)


def _check_unused_fn(fn, warnings):
    used = set()
    _collect(fn.body, used)

    # W004 — parâmetros
    for p in fn.params:
        name = p.name if hasattr(p, 'name') else p[0]
        if name == 'self' or name.startswith('_'):
            continue
        if name not in used:
            warnings.append(Warning(
                "W004", f"parâmetro '{name}' de '{fn.name}' nunca é usado",
                getattr(fn, 'line', 0), getattr(fn, 'col', 0),
            ))

    # W001 — variáveis locais (só as de topo do corpo)
    body = fn.body or []
    for i, stmt in enumerate(body):
        if not isinstance(stmt, VarDecl) or stmt.name.startswith('_'):
            continue
        refs = set()
        for j, other in enumerate(body):
            if j == i:
                continue
            _collect(other, refs)
        if stmt.name not in refs:
            warnings.append(Warning(
                "W001", f"variável '{stmt.name}' declarada mas nunca usada",
                getattr(stmt, 'line', 0), getattr(stmt, 'col', 0),
            ))


def _check_shadowing(decls, warnings):
    for d in decls:
        if isinstance(d, Function):
            _walk_shadow(d.body, {p.name if hasattr(p, 'name') else p[0]
                                  for p in d.params}, warnings)
        elif hasattr(d, 'methods'):
            for m in d.methods:
                _walk_shadow(m.body, {p.name if hasattr(p, 'name') else p[0]
                                      for p in m.params} | {'self'}, warnings)


def _walk_shadow(stmts, scope, warnings):
    for s in stmts or []:
        if s is None:
            continue
        if isinstance(s, VarDecl):
            if s.name in scope and not s.name.startswith('_'):
                warnings.append(Warning(
                    "W002", f"variável '{s.name}' sombreia outra já visível",
                    getattr(s, 'line', 0), getattr(s, 'col', 0),
                ))
            scope.add(s.name)
        elif isinstance(s, IfStmt):
            _walk_shadow(s.then_body, set(scope), warnings)
            _walk_shadow(s.else_body, set(scope), warnings)
        elif isinstance(s, (WhileStmt, ForStmt, DeferStmt, BenchStmt)):
            _walk_shadow(s.body, set(scope), warnings)
        elif isinstance(s, MatchStmt):
            for c in s.cases:
                if len(c) >= 4 and isinstance(c[3], list):
                    _walk_shadow(c[3], set(scope), warnings)
            _walk_shadow(s.default, set(scope), warnings)


def _check_unreachable(decls, warnings):
    for d in decls:
        if isinstance(d, Function):
            _walk_unreachable(d.body, warnings)
        elif hasattr(d, 'methods'):
            for m in d.methods:
                _walk_unreachable(m.body, warnings)


def _walk_unreachable(stmts, warnings):
    if not stmts:
        return
    seen_terminal = False
    for s in stmts:
        if s is None:
            continue
        if seen_terminal:
            warnings.append(Warning(
                "W003", "código inalcançável após return/break/continue",
                getattr(s, 'line', 0), getattr(s, 'col', 0),
            ))
            break
        if isinstance(s, (ReturnStmt, BreakStmt, ContinueStmt)):
            seen_terminal = True
        if isinstance(s, IfStmt):
            _walk_unreachable(s.then_body, warnings)
            _walk_unreachable(s.else_body, warnings)
        elif isinstance(s, (WhileStmt, ForStmt, DeferStmt, BenchStmt)):
            _walk_unreachable(s.body, warnings)
        elif isinstance(s, MatchStmt):
            for c in s.cases:
                if len(c) >= 4 and isinstance(c[3], list):
                    _walk_unreachable(c[3], warnings)
            _walk_unreachable(s.default, warnings)


def _check_empty_functions(decls, warnings):
    for d in decls:
        if isinstance(d, Function) and not d.body:
            warnings.append(Warning(
                "W005", f"função '{d.name}' tem corpo vazio",
                getattr(d, 'line', 0), getattr(d, 'col', 0),
            ))
        elif hasattr(d, 'methods'):
            for m in d.methods:
                if not m.body:
                    warnings.append(Warning(
                        "W005", f"método '{m.name}' tem corpo vazio",
                        getattr(m, 'line', 0), getattr(m, 'col', 0),
                    ))


def lint_file(filename, format="text", quiet=False):
    try:
        with open(filename, "r") as f:
            source = f.read()
    except Exception as e:
        info(f"⚠️  Não foi possível abrir '{filename}': {e}")
        return []

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens, filename, source).parse()
    except LuminaError as e:
        info(f"⚠️  Erro de parse em '{filename}': {e.message}")
        return []

    warnings = []
    _check_unused(ast, warnings)
    _check_shadowing(ast, warnings)
    _check_unreachable(ast, warnings)
    _check_empty_functions(ast, warnings)
    warnings.sort(key=lambda w: (w.line, w.col, w.code))

    if format == "json":
        print(json.dumps([
            {"file": filename, "line": w.line, "col": w.col,
             "code": w.code, "message": w.message}
            for w in warnings
        ], ensure_ascii=False))
    elif not quiet:
        if not warnings:
            success(f"✅ {filename} — sem warnings")
        else:
            for w in warnings:
                print(f"{filename}:{w.line}:{w.col}: {paint(w.code, Color.WARN)}: {w.message}")
            info(f"📊 {len(warnings)} warning(s) em {filename}")

    return warnings