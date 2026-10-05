"""MatchStmt — análise de cases com bindings, guards e escopo."""
from ...ast import MatchStmt, StructLiteralExpr, VariableExpr


class MatchStmtMixin:

    def _analyze_match_stmt(self, node):
        cond_type = self.visit(node.condition)

        # Para enums, precisamos do def para saber o tipo de cada payload.
        enum_def = None
        if cond_type:
            base = cond_type.split('<')[0] if isinstance(cond_type, str) else cond_type
            candidate = self.struct_defs.get(base)
            if candidate is not None and hasattr(candidate, 'variants'):
                enum_def = candidate

        for case in node.cases:
            variant_name, var_name, guard, body = case
            self.push_scope()

            if var_name:
                names = var_name if isinstance(var_name, list) else [var_name]

                # FIX: struct pattern (`case Ponto { x, y }`).
                # O parser emite `variant_name` como `StructLiteralExpr`
                # e `bindings` como a lista de variáveis. Cada binding
                # deve receber o tipo do CAMPO correspondente, não o
                # tipo do struct inteiro.
                if isinstance(variant_name, StructLiteralExpr):
                    struct_def = self.struct_defs.get(variant_name.struct_name)
                    if struct_def is not None and hasattr(struct_def, 'fields'):
                        for field in variant_name.fields:
                            if not isinstance(field.value, VariableExpr):
                                continue
                            binding_name = field.value.name
                            ftype = struct_def.fields.get(field.name, "int")
                            self.declare_var(binding_name, ftype, False)

                elif variant_name is None:
                    # Self-binding: `case s if ...` — tipo do próprio alvo.
                    binding_type = cond_type or "int"
                    for name in names:
                        self.declare_var(name, binding_type, False)

                elif enum_def is not None:
                    # Payloads da variante: [str, int, ...]
                    payload_types = self._variant_payload_types(
                        enum_def, variant_name, cond_type,
                    )
                    for i, name in enumerate(names):
                        bt = payload_types[i] if i < len(payload_types) else "int"
                        self.declare_var(name, bt, False)

                else:
                    # Match sobre int/str sem enum.
                    # NOTA: não usar `cond_type` aqui — para struct pattern
                    # sem fields acessíveis, o binding é o próprio valor.
                    binding_type = cond_type if cond_type in ("int", "str", "bool") else "int"
                    for name in names:
                        self.declare_var(name, binding_type, False)

            if guard:
                guard_type = self.visit(guard)
                self._require_bool(guard_type, context="Guard de 'case'")

            for stmt in body:
                self.analyze_stmt(stmt)

            self.pop_scope()

        if node.default:
            self.push_scope()
            for stmt in node.default:
                self.analyze_stmt(stmt)
            self.pop_scope()

    def _variant_payload_types(self, enum_def, variant_name, cond_type):
        """Retorna os tipos concretos dos payloads de uma variante.

        Se o enum é genérico (`Box<T>`), substitui os type params
        pelos args do `cond_type` (`Box<str>` → `["str"]`).
        """
        from ..types import parse_generic, substitute_generic

        type_map = {}
        base_decl = getattr(enum_def, 'type_params', None) or []
        if base_decl and cond_type:
            _, args = parse_generic(cond_type)
            for tp, arg in zip(base_decl, args):
                type_map[tp] = arg

        for v in enum_def.variants:
            if v[0] != variant_name:
                continue
            payloads = v[1] if len(v) > 1 else []
            if not isinstance(payloads, list):
                payloads = [payloads] if payloads else []
            return [substitute_generic(t, type_map) for t in payloads]
        return []