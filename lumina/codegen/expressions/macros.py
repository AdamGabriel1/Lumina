"""Expansão de macros (@macro) em compile-time.

Uma macro é uma Function com attr 'macro'. Há duas formas de invocação:

  1. `nome(args)` — expressão. O corpo deve ser um único
     `return <expr>`. O valor da expressão é inlineado no call site.

  2. `nome!(args)` — statement. O corpo pode ter qualquer número de
     statements. Cada statement é inlineado no call site, com os
     parâmetros substituídos pelos argumentos.

A substituição é feita em duas funções:
  - `_substitute_in_expr(expr, mapping)` — para expressões
  - `_substitute_in_stmt(stmt, mapping)` — para statements
"""
import copy

from ...ast import (
    # Expressões
    VariableExpr, BinaryExpr, UnaryExpr, CallExpr, MemberExpr,
    IndexExpr, SliceExpr, CastExpr, AddressOfExpr, DerefExpr,
    StructLiteralExpr, NumberExpr, StringExpr, BoolExpr,
    NoneExpr, NilExpr, LambdaExpr, PropagateExpr, ComptimeExpr,
    InterpolatedStringExpr, ArrayExpr, MatchExpr, StructLiteralField,
    Expr as AstExpr,
    # Statements
    VarDecl, AssignStmt, ReturnStmt, IfStmt, WhileStmt, ForStmt,
    DeferStmt, AssertStmt, DestructureStmt,
)


class MacrosMixin:

    def _is_macro(self, name):
        return name in getattr(self, 'macros', {})

    # ==================================================================
    # Expansão em posição de statement (`nome!(args)`)
    # ==================================================================
    def _expand_macro_stmt(self, macro_fn, arg_nodes):
        """Expande macro_fn como sequência de statements.

        Retorna uma lista de statements com os parâmetros substituídos.
        O corpo inteiro da macro é inlineado.
        """
        params = macro_fn.params

        if len(arg_nodes) != len(params):
            from ...errors import LuminaError
            raise LuminaError(
                f"Macro '{macro_fn.name}' espera {len(params)} args, "
                f"recebeu {len(arg_nodes)}.",
                self.filename if hasattr(self, 'filename') else '<repl>',
                getattr(macro_fn, 'line', 0), getattr(macro_fn, 'col', 0), '',
            )

        mapping = {p.name: arg for p, arg in zip(params, arg_nodes)}
        return [self._substitute_in_stmt(s, mapping) for s in macro_fn.body]

    # ==================================================================
    # Substituição em expressões
    # ==================================================================
    def _substitute_in_expr(self, expr, mapping):
        """Deep-copy de `expr` com VariableExpr(name) → mapping[name]."""
        if isinstance(expr, VariableExpr):
            if expr.name in mapping:
                return copy.deepcopy(mapping[expr.name])
            return copy.deepcopy(expr)

        if isinstance(expr, (NumberExpr, StringExpr, BoolExpr,
                             NoneExpr, NilExpr)):
            return copy.deepcopy(expr)

        if isinstance(expr, BinaryExpr):
            return BinaryExpr(
                expr.op,
                self._substitute_in_expr(expr.left, mapping),
                self._substitute_in_expr(expr.right, mapping),
            )

        if isinstance(expr, UnaryExpr):
            return UnaryExpr(
                expr.op,
                self._substitute_in_expr(expr.val, mapping),
            )

        if isinstance(expr, CallExpr):
            return CallExpr(
                self._substitute_in_expr(expr.callee, mapping),
                [self._substitute_in_expr(a, mapping) for a in expr.args],
                expr.is_method,
            )

        if isinstance(expr, MemberExpr):
            return MemberExpr(
                self._substitute_in_expr(expr.obj, mapping),
                expr.member,
                expr.is_safe,
            )

        if isinstance(expr, IndexExpr):
            return IndexExpr(
                self._substitute_in_expr(expr.array, mapping),
                self._substitute_in_expr(expr.index, mapping),
            )

        if isinstance(expr, SliceExpr):
            return SliceExpr(
                self._substitute_in_expr(expr.array, mapping),
                self._substitute_in_expr(expr.start, mapping) if expr.start else None,
                self._substitute_in_expr(expr.end, mapping) if expr.end else None,
            )

        if isinstance(expr, CastExpr):
            return CastExpr(
                self._substitute_in_expr(expr.expr, mapping),
                expr.target_type,
            )

        if isinstance(expr, AddressOfExpr):
            return AddressOfExpr(self._substitute_in_expr(expr.val, mapping))

        if isinstance(expr, DerefExpr):
            return DerefExpr(self._substitute_in_expr(expr.val, mapping))

        if isinstance(expr, PropagateExpr):
            return PropagateExpr(self._substitute_in_expr(expr.val, mapping))

        if isinstance(expr, StructLiteralExpr):
            new_fields = [
                StructLiteralField(
                    f.name,
                    self._substitute_in_expr(f.value, mapping),
                )
                for f in expr.fields
            ]
            return StructLiteralExpr(expr.struct_name, new_fields)

        if isinstance(expr, ArrayExpr):
            return ArrayExpr(
                [self._substitute_in_expr(e, mapping) for e in expr.elements]
            )

        if isinstance(expr, InterpolatedStringExpr):
            return InterpolatedStringExpr(
                [self._substitute_in_expr(e, mapping) for e in expr.parts]
            )

        if isinstance(expr, ComptimeExpr):
            inner = self._substitute_in_expr(expr.expr, mapping)
            return ComptimeExpr(inner)

        # Fallback: deepcopy sem substituição
        return copy.deepcopy(expr)

    # ==================================================================
    # Substituição em statements
    # ==================================================================
    def _substitute_in_stmt(self, stmt, mapping):
        """Deep-copy de `stmt` com substituição de params.

        Cobre os statement types mais comuns dentro de macros
        (VarDecl, AssignStmt, ReturnStmt, IfStmt, WhileStmt, ForStmt,
        DeferStmt, AssertStmt) e delega a `_substitute_in_expr` para
        bare expressions. Para tipos desconhecidos, faz deepcopy sem
        substituição (o que preserva comportamento, mas pode não
        substituir params — evita crash).
        """
        if stmt is None:
            return None

        # Bare expressions usadas como statements
        if isinstance(stmt, AstExpr):
            return self._substitute_in_expr(stmt, mapping)

        if isinstance(stmt, VarDecl):
            return VarDecl(
                stmt.name,
                stmt.var_type,
                self._substitute_in_expr(stmt.value, mapping) if stmt.value else None,
                stmt.is_mutable,
                stmt.line,
                stmt.col,
            )

        if isinstance(stmt, DestructureStmt):
            return DestructureStmt(
                list(stmt.names),
                self._substitute_in_expr(stmt.value, mapping),
                stmt.is_mutable,
            )

        if isinstance(stmt, AssignStmt):
            return AssignStmt(
                self._substitute_in_expr(stmt.target, mapping),
                self._substitute_in_expr(stmt.value, mapping),
            )

        if isinstance(stmt, ReturnStmt):
            return ReturnStmt(
                [self._substitute_in_expr(v, mapping) for v in stmt.values],
                stmt.line,
                stmt.col,
            )

        if isinstance(stmt, IfStmt):
            return IfStmt(
                self._substitute_in_expr(stmt.condition, mapping),
                [self._substitute_in_stmt(s, mapping) for s in stmt.then_body],
                [self._substitute_in_stmt(s, mapping) for s in stmt.else_body]
                if stmt.else_body else None,
            )

        if isinstance(stmt, WhileStmt):
            return WhileStmt(
                self._substitute_in_expr(stmt.condition, mapping),
                [self._substitute_in_stmt(s, mapping) for s in stmt.body],
            )

        if isinstance(stmt, ForStmt):
            return ForStmt(
                stmt.var_name,
                self._substitute_in_expr(stmt.start, mapping) if stmt.start else None,
                self._substitute_in_expr(stmt.end, mapping) if stmt.end else None,
                self._substitute_in_expr(stmt.iterable, mapping) if stmt.iterable else None,
                [self._substitute_in_stmt(s, mapping) for s in stmt.body],
                index_var=stmt.index_var,   # ← preserva
            )

        if isinstance(stmt, DeferStmt):
            return DeferStmt(
                [self._substitute_in_stmt(s, mapping) for s in stmt.body],
                stmt.is_errdefer,
            )

        if isinstance(stmt, AssertStmt):
            return AssertStmt(self._substitute_in_expr(stmt.condition, mapping))

        # Fallback: deepcopy sem substituição
        return copy.deepcopy(stmt)

    # ==================================================================
    # ADR 0003 — Phase 2: expansão com quote:
    # ==================================================================
    def _expand_macro_expr(self, macro_fn, arg_nodes):
        """Expande `macro_fn` como expressão.

        Usa `QuoteInterpreter` para interpretar o corpo em compile-time.
        Suporta substituição direta **e** construção via `quote:`.
        """
        params = macro_fn.params
        if len(arg_nodes) != len(params):
            from ...errors import LuminaError
            raise LuminaError(
                f"Macro '{macro_fn.name}' espera {len(params)} args, "
                f"recebeu {len(arg_nodes)}.",
                self.filename if hasattr(self, 'filename') else '<repl>',
                getattr(macro_fn, 'line', 0), getattr(macro_fn, 'col', 0), '',
            )

        env = {p.name: a for p, a in zip(params, arg_nodes)}

        from ..quote_eval import QuoteInterpreter, QuoteError
        interp = QuoteInterpreter(macros=self.macros)
        try:
            return interp.interpret_expression(macro_fn.body, env)
        except QuoteError as e:
            from ...errors import LuminaError
            raise LuminaError(
                f"Erro na expansão da macro '{macro_fn.name}': {e.msg}",
                self.filename if hasattr(self, 'filename') else '<repl>',
                getattr(macro_fn, 'line', 0), getattr(macro_fn, 'col', 0), '',
            )

    def visit_QuoteExpr(self, node):
        from ...errors import LuminaError
        raise LuminaError(
            message=(
                "`quote:` só pode aparecer dentro de uma macro `@macro`. "
                "Fora de macros, `quote:` não tem significado — "
                "escreva a expressão diretamente."
            ),
            filename=getattr(self, 'current_filename', '<codegen>'),
            line=getattr(node, 'line', 0) or 0,
            col=getattr(node, 'col', 0) or 0,
            source_code=getattr(self, 'source_code', '') or '',
        )

    def visit_UnquoteExpr(self, node):
        from ...errors import LuminaError
        raise LuminaError(
            message="`~x` só pode aparecer dentro de um bloco `quote:`.",
            filename=getattr(self, 'current_filename', '<codegen>'),
            line=getattr(node, 'line', 0) or 0,
            col=getattr(node, 'col', 0) or 0,
            source_code=getattr(self, 'source_code', '') or '',
        )

    def visit_UnquoteSpliceExpr(self, node):
        from ...errors import LuminaError
        raise LuminaError(
            message="`~@xs` só pode aparecer dentro de um bloco `quote:`.",
            filename=getattr(self, 'current_filename', '<codegen>'),
            line=getattr(node, 'line', 0) or 0,
            col=getattr(node, 'col', 0) or 0,
            source_code=getattr(self, 'source_code', '') or '',
        )