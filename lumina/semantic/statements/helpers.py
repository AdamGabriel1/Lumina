"""Helpers compartilhados: validações de tipo, lookup de variante de enum,
inferência de tipo de BinaryExpr.
"""
from ...ast import BinaryExpr
from ...errors import LuminaError
from ..types import is_assignable


class HelpersMixin:

    def _require_assignable(self, target_type, value_type, context, line=0, col=0):
        if target_type is None or value_type is None:
            return
        if is_assignable(target_type, value_type):
            return
        raise LuminaError(
            f"Tipo inválido em {context}: esperado '{target_type}', "
            f"obteve '{value_type}'.",
            self.filename, line, col, self.source_code,
        )

    def _require_bool(self, cond_type, context, line=0, col=0):
        if cond_type in ("bool", "int", None, "Unknown"):
            return
        raise LuminaError(
            f"{context} deve ser 'bool' ou 'int', obteve '{cond_type}'.",
            self.filename, line, col, self.source_code,
        )

    def _find_enum_of_variant(self, variant_name, require_no_payload=False):
        """Retorna o nome do enum que contém `variant_name`, ou None.

        Se `require_no_payload=True`, ignora variantes com payload.
        Usado em `visit_VariableExpr` para aceitar `Stop` bare (só quando
        a variante não tem payload — `Some` bare seria ambíguo).
        """
        for enum_name, enum_def in self.struct_defs.items():
            if not hasattr(enum_def, 'variants'):
                continue
            for v in enum_def.variants:
                if v[0] != variant_name:
                    continue
                if require_no_payload:
                    payloads = v[1] if len(v) > 1 else []
                    if payloads:
                        return None
                return enum_name
        return None

    def _infer_binary_type(self, node: BinaryExpr):
        """Infere o tipo de uma expressão binária.

        Regras (heurísticas — olha o tipo dos lados, não o valor):
          - Comparações (==, !=, <, >, <=, >=) → "bool"
          - `and`/`or` → "bool"
          - `+` com str de um lado → "str"
          - Se algum lado é float → "float"
          - Se algum lado é struct → o tipo da struct (sobrecarga)
          - Caso contrário → "int"
        """
        if node.op in ('==', '!=', '<', '>', '<=', '>='):
            return "bool"
        if node.op in ('and', 'or'):
            return "bool"

        lt = self.visit(node.left)
        rt = self.visit(node.right)

        if node.op == '+' and (lt == "str" or rt == "str"):
            return "str"

        if lt and lt.split('<')[0] in self.structs:
            return lt
        if rt and rt.split('<')[0] in self.structs:
            return rt

        if lt == "float" or rt == "float":
            return "float"

        return "int"
