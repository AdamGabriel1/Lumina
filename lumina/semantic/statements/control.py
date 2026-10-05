"""IfStmt, WhileStmt, ForStmt — controle de fluxo com escopo de bloco.

v0.8.0: `_infer_for_elem_type` reconhece `[T]` (slice).
"""
from ...ast import IfStmt, WhileStmt, ForStmt, ArrayExpr, StringExpr, VariableExpr
from ...errors import LuminaError


class ControlMixin:

    _HINT_LLVM_GROUPS = (
        frozenset({"int"}),
        frozenset({"float"}),
        frozenset({"bool"}),
        frozenset({"str", "fn"}),
    )

    def _analyze_if(self, node):
        cond_type = self.visit(node.condition)
        self._require_bool(cond_type, context="Condição de 'if'")

        self.push_scope()
        for stmt in node.then_body:
            self.analyze_stmt(stmt)
        self.pop_scope()

        if node.else_body:
            self.push_scope()
            for stmt in node.else_body:
                self.analyze_stmt(stmt)
            self.pop_scope()

    def _analyze_while(self, node):
        cond_type = self.visit(node.condition)
        self._require_bool(cond_type, context="Condição de 'while'")

        self.push_scope()
        for stmt in node.body:
            self.analyze_stmt(stmt)
        self.pop_scope()

    def _analyze_for(self, node):
        iter_type = None
        if node.iterable is not None:
            iter_type = self.visit(node.iterable)
        else:
            self.visit(node.start)
            self.visit(node.end)

        self.push_scope()

        if node.index_var is not None:
            self.declare_var(node.index_var, "int", False)

        elem_type = self._resolve_for_elem_type(node, iter_type)
        self.declare_var(node.var_name, elem_type, False)

        for stmt in node.body:
            self.analyze_stmt(stmt)
        self.pop_scope()

    def _resolve_for_elem_type(self, node, iter_type):
        inferred = self._infer_for_elem_type_no_hint(node, iter_type)
        hint = getattr(node, 'elem_type', None)
        if hint:
            if inferred is not None and not self._is_hint_compatible(hint, inferred):
                self._raise_hint_mismatch(node, hint, inferred)
            return hint
        return inferred if inferred else "int"

    def _infer_for_elem_type_no_hint(self, node, iter_type):
        # v0.8.0: slice `[T]` → T.
        if (iter_type and isinstance(iter_type, str)
                and iter_type.startswith("[") and iter_type.endswith("]")):
            return iter_type[1:-1]

        if isinstance(node.iterable, ArrayExpr) and node.iterable.elements:
            first_t = self.visit(node.iterable.elements[0])
            if first_t:
                return first_t

        if isinstance(node.iterable, VariableExpr):
            registered = getattr(self, 'array_elem_types', {}).get(
                node.iterable.name
            )
            if registered:
                return registered

        if isinstance(node.iterable, StringExpr):
            return "int"

        if iter_type == "str":
            return "int"

        return None

    def _is_hint_compatible(self, hint, inferred):
        if hint == inferred:
            return True
        if inferred == "ptr" or hint == "ptr":
            return True
        for group in self._HINT_LLVM_GROUPS:
            if hint in group and inferred in group:
                return True
        return False

    def _raise_hint_mismatch(self, node, hint, inferred):
        line = getattr(node.iterable, 'line', 0) if node.iterable else 0
        col = getattr(node.iterable, 'col', 0) if node.iterable else 0
        raise LuminaError(
            message=(
                f"Hint de tipo '{hint}' é incompatível com o tipo "
                f"inferido '{inferred}' do iterável no `for`. "
                f"Remova a anotação `: {hint}` (o tipo '{inferred}' "
                f"é inferido automaticamente) ou converta "
                f"explicitamente dentro do corpo."
            ),
            filename=self.filename,
            line=line,
            col=col,
            source_code=self.source_code,
        )