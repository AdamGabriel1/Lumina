"""Closures — análise de variáveis livres e escopo da lambda."""
from .helpers import _collect_var_refs, _collect_declared


class ClosuresMixin:

    def visit_LambdaExpr(self, node):
        # 1) Encontra variáveis livres (antes de entrar no escopo da lambda).
        refs = set()
        for stmt in node.body:
            _collect_var_refs(stmt, refs)

        declared = {p.name for p in node.params}
        for stmt in node.body:
            _collect_declared(stmt, declared)

        free = []
        for name in sorted(refs):
            if name in declared:
                continue
            # Visível no escopo externo?
            visible = False
            for scope in reversed(self.scopes):
                if name in scope:
                    visible = True
                    break
            if visible:
                free.append(name)

        node.free_vars = free

        # 2) Análise normal do body.
        self.push_scope()
        for param in node.params:
            self.declare_var(param.name, param.type_ann, True)
        for stmt in node.body:
            self.analyze_stmt(stmt)
        self.pop_scope()
        param_types = [p.type_ann for p in node.params]
        return f"fn({','.join(param_types)}) -> {node.return_type}"
