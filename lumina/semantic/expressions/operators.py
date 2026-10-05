"""Operadores: binário, unário, endereço, deref, propagação de erro."""
from ...ast import (
    BinaryExpr, UnaryExpr, AddressOfExpr, DerefExpr, PropagateExpr,
    VariableExpr,
)
from ...errors import LuminaError
from ..types import is_assignable


class OperatorsMixin:

    def visit_BinaryExpr(self, node):
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)

        if node.op in ('==', '!=', '<', '>', '<=', '>='):
            if left_type and right_type and left_type != right_type:
                if not (is_assignable(left_type, right_type)
                        or is_assignable(right_type, left_type)):
                    raise LuminaError(
                        f"Tipos incompatíveis na comparação: "
                        f"'{left_type}' e '{right_type}'",
                        self.filename, getattr(node, 'line', 0),
                        getattr(node, 'col', 0), self.source_code,
                    )
            return "bool"

        if node.op in ('and', 'or'):
            # `int` é aceito como bool (0 = false, != 0 = true),
            # consistente com `_require_bool` usado em if/while/assert.
            valid = {"bool", "int", None}
            if left_type not in valid or right_type not in valid:
                raise LuminaError(
                    f"Operador lógico '{node.op}' requer operandos 'bool' "
                    f"ou 'int', obteve '{left_type}' e '{right_type}'.",
                    self.filename, getattr(node, 'line', 0),
                    getattr(node, 'col', 0), self.source_code,
                )
            return "bool"

        if left_type and left_type.split('<')[0] in self.structs:
            struct_name = left_type.split('<')[0]
            op_map = {
                '+': '__add__', '-': '__sub__', '*': '__mul__',
                '/': '__div__', '==': '__eq__',
            }
            method_name = op_map.get(node.op)
            if method_name:
                real_method_name = f"{struct_name}_{method_name}"
                if real_method_name not in self.functions:
                    raise LuminaError(
                        f"Operador '{node.op}' não definido para a struct "
                        f"'{struct_name}'.",
                        self.filename, getattr(node, 'line', 0),
                        getattr(node, 'col', 0), self.source_code,
                    )
        return left_type

    # FIX: `visit_UnaryExpr` retornava `None`, quebrando a inferência
    # de `let x = -5` (x ficava sem tipo) e `let y = not b` (idem).
    # Agora retorna o tipo do valor, com o operador `not` forçando bool.
    def visit_UnaryExpr(self, node):
        val_type = self.visit(node.val)

        if node.op == 'not':
            return "bool"

        if node.op == '-':
            # `-int` → int, `-float` → float. Se o operando já é
            # `bool` ou desconhecido, propaga como está.
            if val_type in ("int", "float", "bool"):
                return val_type
            return val_type  # pode ser None — sem info

        # Operador unário desconhecido: propaga o tipo do operando.
        return val_type

    def visit_AddressOfExpr(self, node):
        if isinstance(node.val, VariableExpr) and node.val.name in self.functions:
            return "ptr"
        self.visit(node.val)
        return "ptr"

    def visit_DerefExpr(self, node):
        self.visit(node.val)
        return None

    def visit_PropagateExpr(self, node):
        self.visit(node.val)
        if (not hasattr(self, 'current_ret_type')
                or not self.current_ret_type.startswith("Result")):
            raise LuminaError(
                "Operador '?' só pode ser usado em funções que retornam 'Result'.",
                self.filename, getattr(node, 'line', 0),
                getattr(node, 'col', 0), self.source_code,
            )
        return None