"""Análise semântica de expressões.

Composto por mixins focados:
  - LiteralsMixin   — Number, Bool, String, None, Nil, Variable, Member,
                      Index, Slice, Cast
  - OperatorsMixin  — Binary, Unary, AddressOf, Deref, Propagate
  - CallsMixin      — CallExpr + _resolve_kwargs
  - ComptimeMixin   — ComptimeExpr + _constant_fold
  - AggregatesMixin — Array, Tuple, StructLiteral, MatchExpr
  - ClosuresMixin   — LambdaExpr (free_vars + escopo)

Todos operam sobre o mesmo `self` (que é um `SemanticAnalyzer`).
"""
from ...ast.visitor import NodeVisitor

from .literals import LiteralsMixin
from .operators import OperatorsMixin
from .calls import CallsMixin
from .comptime import ComptimeMixin
from .aggregates import AggregatesMixin
from .closures import ClosuresMixin


class ExpressionAnalyzer(
    LiteralsMixin,
    OperatorsMixin,
    CallsMixin,
    ComptimeMixin,
    AggregatesMixin,
    ClosuresMixin,
    NodeVisitor,
):
    """Combina todos os visitors de expressão via MRO."""

    def generic_visit(self, node):
        return None
