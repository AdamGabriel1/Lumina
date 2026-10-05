"""Codegen de `MacroCallStmt` — invocação de macro em posição de statement.

Diferente das macros usadas como expressão (que só permitem corpo
`return <expr>`), uma macro invocada via `nome!(args)` inlineia o
corpo inteiro no call site, permitindo múltiplos statements.
"""
from ...ast import MacroCallStmt


class MacroStmtMixin:

    def visit_MacroCallStmt(self, node):
        macro_fn = getattr(self, 'macros', {}).get(node.name)
        if macro_fn is None:
            # Semantic deveria ter reclamado antes; aqui é defesa.
            from ...errors import LuminaError
            raise LuminaError(
                f"'{node.name}' não é uma macro declarada.",
                self.filename if hasattr(self, 'filename') else '<codegen>',
                node.line, node.col, '',
            )

        expanded_stmts = self._expand_macro_stmt(macro_fn, node.args)
        for stmt in expanded_stmts:
            if self.builder.block.is_terminated:
                break
            self.visit(stmt)
