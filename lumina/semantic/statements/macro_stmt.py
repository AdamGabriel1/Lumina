"""Análise semântica de `MacroCallStmt` — `nome!(args)` em statement."""
from ...errors import LuminaError


class MacroStmtMixin:

    def _analyze_macro_call_stmt(self, node):
        if node.name not in self.macros:
            raise LuminaError(
                f"'{node.name}!' não é uma macro. "
                f"Declare com `@macro` ou use chamada normal `{node.name}(...)`.",
                self.filename, node.line, node.col, self.source_code,
            )

        macro_fn = self.macros[node.name]
        expected = len(macro_fn.params)
        got = len(node.args)
        if got != expected:
            raise LuminaError(
                f"Macro '{node.name}' espera {expected} args, recebeu {got}.",
                self.filename, node.line, node.col, self.source_code,
            )

        for arg in node.args:
            self.visit(arg)
