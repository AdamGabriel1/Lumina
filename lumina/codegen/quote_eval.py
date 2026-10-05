"""Compile-time interpreter for macro bodies — ADR 0003 Phase 2."""

import copy

from ..ast import (
    NumberExpr, StringExpr, BoolExpr, NoneExpr, NilExpr,
    VariableExpr, BinaryExpr, UnaryExpr, CallExpr, MemberExpr,
    IndexExpr, SliceExpr, ArrayExpr, StructLiteralExpr, StructLiteralField,
    QuoteExpr, UnquoteExpr, UnquoteSpliceExpr,
    TupleExpr, CastExpr, AddressOfExpr, DerefExpr, PropagateExpr,
    VarDecl, AssignStmt, ReturnStmt, IfStmt, WhileStmt, ForStmt,
    DeferStmt, AssertStmt, BreakStmt, ContinueStmt, CompoundAssignStmt,
    Expr, BlockExpr,
)


class QuoteError(Exception):
    def __init__(self, msg, node=None):
        super().__init__(msg)
        self.msg = msg
        self.node = node


class _Return(Exception):
    def __init__(self, value):
        self.value = value


def _is_python_value(v):
    return isinstance(v, (int, float, bool, str)) and not isinstance(v, bool) or isinstance(v, bool)


def _unbox(v):
    """Converte literais AST em valores Python.

    Fix 2: quando `VariableExpr` resolve para um nó literal, o
    interpreter precisa do **valor** para computar em compile-time.
    Sem isso, `if flag > 0` constrói um `BinaryExpr` em vez de
    avaliar — e nós de AST são truthy.
    """
    if isinstance(v, NumberExpr):
        if v.is_float:
            try:
                return float(v.value)
            except (ValueError, TypeError):
                return 0.0
        try:
            return int(v.value, 0)
        except (ValueError, TypeError):
            return 0
    if isinstance(v, StringExpr):
        return v.value
    if isinstance(v, BoolExpr):
        return v.value
    return v


class QuoteInterpreter:

    def __init__(self, macros=None):
        self.env = {}
        self._gensym_counter = 0
        self._macros = macros or {}

    # ==================================================================
    # Ponto de entrada
    # ==================================================================
    def interpret_expression(self, body, initial_env):
        return self.interpret_body(body, initial_env)

    def interpret_body(self, body, env):
        saved_env = self.env
        self.env = dict(env)
        try:
            if len(body) == 1:
                stmt = body[0]
                if isinstance(stmt, ReturnStmt):
                    if not stmt.values:
                        raise QuoteError("corpo da macro deve ter `return <expr>`", stmt)
                    return self._to_ast(self._eval(stmt.values[0]))
                if isinstance(stmt, Expr):
                    return self._to_ast(self._eval(stmt))

            try:
                for stmt in body:
                    self._exec_stmt(stmt)
            except _Return as r:
                return self._to_ast(r.value)
            raise QuoteError("corpo da macro deve ter `return <expr>`")
        finally:
            self.env = saved_env

    # ==================================================================
    # Statements
    # ==================================================================
    def _exec_stmt(self, stmt):
        if stmt is None:
            return

        if isinstance(stmt, VarDecl):
            v = self._eval(stmt.value) if stmt.value is not None else None
            self.env[stmt.name] = v
            return

        if isinstance(stmt, ReturnStmt):
            v = self._eval(stmt.values[0]) if stmt.values else None
            raise _Return(v)

        if isinstance(stmt, AssignStmt):
            if not isinstance(stmt.target, VariableExpr):
                raise QuoteError(
                    "dentro da macro, atribuição só é permitida a variável simples",
                    stmt,
                )
            self.env[stmt.target.name] = self._eval(stmt.value)
            return

        if isinstance(stmt, IfStmt):
            cond = self._eval(stmt.condition)
            if self._truthy(cond):
                for s in stmt.then_body:
                    self._exec_stmt(s)
            elif stmt.else_body:
                for s in stmt.else_body:
                    self._exec_stmt(s)
            return

        if isinstance(stmt, WhileStmt):
            guard = 0
            while self._truthy(self._eval(stmt.condition)):
                for s in stmt.body:
                    self._exec_stmt(s)
                guard += 1
                if guard > 10_000:
                    raise QuoteError("loop `while` da macro rodou demais", stmt)
            return

        if isinstance(stmt, Expr):
            self._eval(stmt)
            return

        raise QuoteError(
            f"statement não suportado no corpo da macro: {type(stmt).__name__}",
            stmt,
        )

    # ==================================================================
    # Avaliação de expressões
    # ==================================================================
    def _eval(self, expr):
        if expr is None:
            return None

        if isinstance(expr, NumberExpr):
            return _unbox(expr)

        if isinstance(expr, StringExpr):
            return expr.value

        if isinstance(expr, BoolExpr):
            return expr.value

        if isinstance(expr, (NoneExpr, NilExpr)):
            return copy.deepcopy(expr)

        if isinstance(expr, VariableExpr):
            if expr.name in self.env:
                # Fix 2: unbox literais para que computações em
                # compile-time funcionem.
                return _unbox(self.env[expr.name])
            return copy.deepcopy(expr)

        if isinstance(expr, BinaryExpr):
            left = self._eval(expr.left)
            right = self._eval(expr.right)
            if _is_python_value(left) and _is_python_value(right):
                try:
                    return self._apply_binop(expr.op, left, right)
                except QuoteError:
                    raise
                except Exception as e:
                    raise QuoteError(
                        f"erro avaliando `{expr.op}` em compile-time: {e}", expr,
                    )
            return BinaryExpr(expr.op, self._to_ast(left), self._to_ast(right))

        if isinstance(expr, UnaryExpr):
            inner = self._eval(expr.val)
            if _is_python_value(inner) and expr.op in ('-', 'not', '~'):
                return self._apply_unop(expr.op, inner)
            return UnaryExpr(expr.op, self._to_ast(inner))

        if isinstance(expr, CallExpr):
            return self._eval_call(expr)

        if isinstance(expr, QuoteExpr):
            return self._build_quote(expr.statements)

        if isinstance(expr, UnquoteExpr):
            raise QuoteError("`~x` só pode aparecer dentro de um `quote:`", expr)

        if isinstance(expr, UnquoteSpliceExpr):
            raise QuoteError("`~@xs` só pode aparecer dentro de um `quote:`", expr)

        if isinstance(expr, ArrayExpr):
            elements = []
            for e in expr.elements:
                v = self._eval(e)
                if isinstance(v, list):
                    elements.extend(v)
                else:
                    elements.append(self._to_ast(v))
            return ArrayExpr(elements)

        if isinstance(expr, MemberExpr):
            obj = self._eval(expr.obj)
            return MemberExpr(self._to_ast(obj), expr.member, expr.is_safe)

        if isinstance(expr, IndexExpr):
            return IndexExpr(
                self._to_ast(self._eval(expr.array)),
                self._to_ast(self._eval(expr.index)),
            )

        return copy.deepcopy(expr)

    def _eval_call(self, node):
        name = None
        if isinstance(node.callee, VariableExpr):
            name = node.callee.name

        if name in self._macros:
            nested_fn = self._macros[name]
            if len(node.args) != len(nested_fn.params):
                raise QuoteError(
                    f"macro '{name}' espera {len(nested_fn.params)} args, "
                    f"recebeu {len(node.args)}", node,
                )
            args_ast = [self._to_ast(self._eval(a)) for a in node.args]
            env = {p.name: a for p, a in zip(nested_fn.params, args_ast)}
            return self.interpret_body(nested_fn.body, env)

        if name == "gensym":
            if not node.args:
                raise QuoteError("`gensym` requer um argumento (nome base)", node)
            base = self._eval(node.args[0])
            if not isinstance(base, str):
                raise QuoteError("`gensym` requer literal de string", node)
            self._gensym_counter += 1
            mangled = f"__{base}_{self._gensym_counter}"
            return VariableExpr(mangled)

        if name == "len":
            if not node.args:
                raise QuoteError("`len` requer um argumento", node)
            arg = self._eval(node.args[0])
            if isinstance(arg, (list, str)):
                return len(arg)
            raise QuoteError(
                "`len` dentro de macro só aceita listas ou strings", node,
            )

        raise QuoteError(
            f"função não suportada no corpo da macro: {name!r}", node,
        )

    def _apply_binop(self, op, l, r):
        if op == '+':  return l + r
        if op == '-':  return l - r
        if op == '*':  return l * r
        if op == '/':
            if isinstance(l, int) and isinstance(r, int):
                return l // r
            return l / r
        if op == '%':  return l % r
        if op == '==': return l == r
        if op == '!=': return l != r
        if op == '<':  return l < r
        if op == '>':  return l > r
        if op == '<=': return l <= r
        if op == '>=': return l >= r
        if op == 'and': return bool(l) and bool(r)
        if op == 'or':  return bool(l) or bool(r)
        raise QuoteError(f"binop não suportado no corpo da macro: {op!r}")

    def _apply_unop(self, op, v):
        if op == '-':   return -v
        if op == 'not': return not v
        if op == '~':   return ~v
        raise QuoteError(f"unop não suportado no corpo da macro: {op!r}")

    # ==================================================================
    # Construção de quote
    # ==================================================================
    def _build_quote(self, stmts):
        if not stmts:
            raise QuoteError("`quote:` vazio")

        # Fix 1: se o último item é uma Expr, separa em `final_expr`.
        # Isso permite que o codegen saiba qual valor retornar.
        if isinstance(stmts[-1], Expr) and not isinstance(stmts[-1], (ReturnStmt,)):
            body = stmts[:-1]
            final = stmts[-1]
            if not body:
                return self._build_expr(final)
            built_body = []
            for s in body:
                if isinstance(s, Expr):
                    built_body.append(self._build_expr(s))
                else:
                    built_body.append(self._build_stmt(s))
            return BlockExpr(
                statements=built_body,
                final_expr=self._build_expr(final),
            )

        if len(stmts) == 1:
            s = stmts[0]
            if isinstance(s, Expr):
                return self._build_expr(s)
            return self._build_stmt(s)

        built = []
        for s in stmts:
            if isinstance(s, Expr):
                built.append(self._build_expr(s))
            else:
                built.append(self._build_stmt(s))
        return BlockExpr(statements=built, final_expr=None)

    def _build_expr(self, expr):
        if expr is None:
            return None

        if isinstance(expr, UnquoteExpr):
            v = self._eval(expr.expr)
            if isinstance(v, list):
                raise QuoteError(
                    "`~x` produziu uma lista; use `~@x` para espalhar", expr,
                )
            # Invariante: `_build_expr` sempre retorna nó AST. `_to_ast`
            # envolve primitivos Python (int/float/bool/str) em literais;
            # para nós AST, é no-op.
            return self._to_ast(v)

        if isinstance(expr, UnquoteSpliceExpr):
            v = self._eval(expr.expr)
            if not isinstance(v, list):
                raise QuoteError("`~@xs` requer uma lista", expr)
            return v

        if isinstance(expr, (NumberExpr, StringExpr, BoolExpr, NoneExpr, NilExpr)):
            return copy.deepcopy(expr)

        if isinstance(expr, VariableExpr):
            return copy.deepcopy(expr)

        if isinstance(expr, BinaryExpr):
            return BinaryExpr(
                expr.op,
                self._build_expr(expr.left),
                self._build_expr(expr.right),
            )

        if isinstance(expr, UnaryExpr):
            return UnaryExpr(expr.op, self._build_expr(expr.val))

        if isinstance(expr, CallExpr):
            return CallExpr(
                self._build_expr(expr.callee),
                [self._build_expr(a) for a in expr.args],
                expr.is_method,
            )

        if isinstance(expr, QuoteExpr):
            return QuoteExpr([self._build_stmt(s) for s in expr.statements])

        if isinstance(expr, ArrayExpr):
            flat = []
            for e in expr.elements:
                b = self._build_expr(e)
                if isinstance(b, list):
                    flat.extend(b)
                else:
                    flat.append(b)
            return ArrayExpr(flat)

        if isinstance(expr, MemberExpr):
            return MemberExpr(
                self._build_expr(expr.obj), expr.member, expr.is_safe,
            )

        if isinstance(expr, IndexExpr):
            return IndexExpr(
                self._build_expr(expr.array), self._build_expr(expr.index),
            )

        if isinstance(expr, SliceExpr):
            return SliceExpr(
                self._build_expr(expr.array),
                self._build_expr(expr.start) if expr.start else None,
                self._build_expr(expr.end) if expr.end else None,
            )

        if isinstance(expr, StructLiteralExpr):
            return StructLiteralExpr(
                expr.struct_name,
                [
                    StructLiteralField(f.name, self._build_expr(f.value))
                    for f in expr.fields
                ],
            )

        if isinstance(expr, TupleExpr):
            return TupleExpr([self._build_expr(e) for e in expr.elements])

        if isinstance(expr, CastExpr):
            return CastExpr(self._build_expr(expr.expr), expr.target_type)

        if isinstance(expr, AddressOfExpr):
            return AddressOfExpr(self._build_expr(expr.val))

        if isinstance(expr, DerefExpr):
            return DerefExpr(self._build_expr(expr.val))

        if isinstance(expr, PropagateExpr):
            return PropagateExpr(self._build_expr(expr.val))

        return copy.deepcopy(expr)

    def _build_stmt(self, stmt):
        if stmt is None:
            return None

        if isinstance(stmt, VarDecl):
            name = self._coerce_name(stmt.name, stmt)
            value = self._build_expr(stmt.value) if stmt.value is not None else None
            return VarDecl(name, stmt.var_type, value, stmt.is_mutable,
                           stmt.line, stmt.col)

        if isinstance(stmt, AssignStmt):
            return AssignStmt(
                self._build_expr(stmt.target),
                self._build_expr(stmt.value),
            )

        if isinstance(stmt, ReturnStmt):
            return ReturnStmt(
                [self._build_expr(v) for v in stmt.values],
                stmt.line, stmt.col,
            )

        if isinstance(stmt, IfStmt):
            cond = self._build_expr(stmt.condition)
            then_b = [self._build_stmt(s) for s in stmt.then_body]
            else_b = (
                [self._build_stmt(s) for s in stmt.else_body]
                if stmt.else_body else None
            )
            return IfStmt(cond, then_b, else_b)

        if isinstance(stmt, WhileStmt):
            return WhileStmt(
                self._build_expr(stmt.condition),
                [self._build_stmt(s) for s in stmt.body],
            )

        if isinstance(stmt, ForStmt):
            return ForStmt(
                stmt.var_name,
                self._build_expr(stmt.start) if stmt.start else None,
                self._build_expr(stmt.end) if stmt.end else None,
                self._build_expr(stmt.iterable) if stmt.iterable else None,
                [self._build_stmt(s) for s in stmt.body],
                index_var=stmt.index_var,
                elem_type=getattr(stmt, 'elem_type', None),
            )

        if isinstance(stmt, DeferStmt):
            return DeferStmt(
                [self._build_stmt(s) for s in stmt.body],
                stmt.is_errdefer,
            )

        if isinstance(stmt, AssertStmt):
            return AssertStmt(self._build_expr(stmt.condition))

        if isinstance(stmt, BreakStmt):
            return BreakStmt()
        if isinstance(stmt, ContinueStmt):
            return ContinueStmt()

        if isinstance(stmt, CompoundAssignStmt):
            return CompoundAssignStmt(
                self._build_expr(stmt.target),
                stmt.op,
                self._build_expr(stmt.value),
            )

        if isinstance(stmt, Expr):
            return self._build_expr(stmt)

        return copy.deepcopy(stmt)

    # ==================================================================
    # Helpers
    # ==================================================================
    def _coerce_name(self, field, node):
        if isinstance(field, str):
            return field
        if isinstance(field, VariableExpr):
            return field.name
        if isinstance(field, StringExpr):
            return field.value
        raise QuoteError(
            f"não é possível usar {type(field).__name__} como nome de binding",
            node,
        )

    def _to_ast(self, v):
        if v is None:
            raise QuoteError("expansão da macro produziu `None`")
        if isinstance(v, bool):
            return BoolExpr(v)
        if isinstance(v, int):
            return NumberExpr(str(v), is_float=False)
        if isinstance(v, float):
            return NumberExpr(repr(v), is_float=True)
        if isinstance(v, str):
            return StringExpr(v)
        return v

    def _truthy(self, v):
        if isinstance(v, bool):          return v
        if isinstance(v, (int, float)):  return v != 0
        if isinstance(v, str):           return len(v) > 0
        if v is None:                    return False
        return True