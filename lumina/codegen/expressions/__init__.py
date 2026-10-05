from llvmlite import ir
from ...ast.visitor import NodeVisitor

from .literals import LiteralsMixin
from .operators import OperatorsMixin
from .members import MembersMixin
from .calls import CallsMixin
from .builtins import BuiltinsMixin
from .io_builtins import IOBuiltinsMixin
from .methods import MethodCallsMixin
from .aggregates import AggregatesMixin
from .match import MatchExprMixin
from .macros import MacrosMixin


class ExpressionCodegen(
    LiteralsMixin,
    OperatorsMixin,
    MembersMixin,
    CallsMixin,
    BuiltinsMixin,
    IOBuiltinsMixin,
    MethodCallsMixin,
    AggregatesMixin,
    MatchExprMixin,
    MacrosMixin,
    NodeVisitor,
):
    """Combina todos os visitors de expressão via MRO.

    Ordem dos mixins (todos operam sobre o mesmo `self`):
      1. LiteralsMixin      — NumberExpr, StringExpr, BoolExpr, NoneExpr, NilExpr
      2. OperatorsMixin     — BinaryExpr, UnaryExpr, CastExpr, DerefExpr
      3. MembersMixin       — VariableExpr, MemberExpr, IndexExpr, SliceExpr
      4. CallsMixin         — visit_CallExpr + dispatch (macros, indirect, genéricos)
      5. BuiltinsMixin      — _call_builtin_impl (print, len, alloc, chr, ...)
      6. IOBuiltinsMixin    — _call_io_builtin (write_file, read_file)
      7. MethodCallsMixin   — codegen_method_call + enum constructor
      8. AggregatesMixin    — ArrayExpr, StructLiteralExpr, LambdaExpr, TupleExpr
      9. MatchExprMixin     — MatchExpr
     10. MacrosMixin        — _expand_macro_expr
    """

    def generic_visit(self, node):
        return ir.Constant(self.i64_ty, 0)