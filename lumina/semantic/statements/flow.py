"""ReturnStmt, DeferStmt, AssertStmt, BenchStmt."""
from ...ast import ReturnStmt, DeferStmt, AssertStmt, BenchStmt


class FlowMixin:

    def _analyze_return(self, node):
        expected = getattr(self, 'current_ret_type', None)
        is_single = len(node.values) == 1

        for val in node.values:
            self.check_escape(val)
            actual = self.visit(val)
            if is_single and expected and expected != "void" and actual:
                self._require_assignable(
                    expected, actual,
                    context=f"retorno de "
                            f"'{getattr(self, 'current_func_name', 'função')}'",
                )

    def _analyze_defer(self, node):
        for stmt in node.body:
            self.analyze_stmt(stmt)

    def _analyze_assert(self, node):
        cond_type = self.visit(node.condition)
        self._require_bool(cond_type, context="Condição de 'assert'")

    def _analyze_bench(self, node):
        for stmt in node.body:
            self.analyze_stmt(stmt)
