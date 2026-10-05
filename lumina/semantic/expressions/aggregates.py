"""Agregados: ArrayExpr, TupleExpr, StructLiteralExpr, MatchExpr."""
from ...ast import (
    ArrayExpr, TupleExpr, StructLiteralExpr, MatchExpr, VariableExpr,
)
from ...errors import LuminaError
from ..types import is_assignable


class AggregatesMixin:

    def visit_ArrayExpr(self, node):
        for el in node.elements:
            self.visit(el)
        return "array"

    def visit_TupleExpr(self, node):
        for el in node.elements:
            self.visit(el)
        return "ptr"

    def visit_StructLiteralExpr(self, node):
        if node.struct_name not in self.struct_defs:
            raise LuminaError(
                f"Struct '{node.struct_name}' não declarada.",
                self.filename, getattr(node, 'line', 0),
                getattr(node, 'col', 0), self.source_code,
            )

        struct_def = self.struct_defs[node.struct_name]
        defined_fields = set(struct_def.fields.keys())
        passed_fields = set()

        for field in node.fields:
            if field.name not in struct_def.fields:
                raise LuminaError(
                    f"Campo '{field.name}' não existe na Struct "
                    f"'{node.struct_name}'.",
                    self.filename, getattr(node, 'line', 0),
                    getattr(node, 'col', 0), self.source_code,
                )

            # Valida tipo do valor contra o tipo declarado do campo.
            field_decl_type = struct_def.fields[field.name]
            value_type = self.visit(field.value)

            if value_type is not None and not is_assignable(field_decl_type, value_type):
                raise LuminaError(
                    f"Tipo inválido para campo '{field.name}' de "
                    f"'{node.struct_name}': esperado '{field_decl_type}', "
                    f"obteve '{value_type}'.",
                    self.filename,
                    getattr(field.value, 'line', 0) or getattr(node, 'line', 0),
                    getattr(field.value, 'col', 0) or getattr(node, 'col', 0),
                    self.source_code,
                )

            passed_fields.add(field.name)

        missing = defined_fields - passed_fields
        if missing:
            raise LuminaError(
                f"Campos faltando na inicialização da Struct "
                f"'{node.struct_name}': {', '.join(missing)}",
                self.filename, getattr(node, 'line', 0),
                getattr(node, 'col', 0), self.source_code,
            )
        return node.struct_name

    def visit_MatchExpr(self, node):
        self.visit(node.condition)

        for val, res in node.cases:
            self.push_scope()
            if isinstance(val, StructLiteralExpr):
                if val.struct_name not in self.struct_defs:
                    raise LuminaError(
                        f"Struct '{val.struct_name}' não declarada.",
                        self.filename, getattr(node, 'line', 0),
                        getattr(node, 'col', 0), self.source_code,
                    )

                for field in val.fields:
                    if isinstance(field.value, VariableExpr):
                        field_type = self.struct_defs[val.struct_name].fields.get(
                            field.name, "int",
                        )
                        self.declare_var(field.value.name, field_type, True)
                    else:
                        self.visit(field.value)
            else:
                self.visit(val)
            self.visit(res)
            self.pop_scope()

        if node.default:
            self.visit(node.default)
        return None
