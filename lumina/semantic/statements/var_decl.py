"""VarDecl, DestructureStmt, AssignStmt — declarações e atribuições."""
from ...ast import (
    VarDecl, DestructureStmt, AssignStmt, CallExpr, MemberExpr,
    VariableExpr, StringExpr, NumberExpr, BoolExpr, BinaryExpr,
    StructLiteralExpr, ArrayExpr, AddressOfExpr, PropagateExpr,
    LambdaExpr, NoneExpr, ComptimeExpr, NilExpr, TupleExpr,
    DerefExpr, SliceExpr, IndexExpr, CastExpr,
    UnaryExpr,
    CompoundAssignStmt,
)
from ...builtins import BUILTIN_RET
from ...errors import LuminaError
from ..types import parse_fn_type, is_assignable


class VarDeclMixin:

    # ------------------------------------------------------------------
    # VarDecl
    # ------------------------------------------------------------------
    def _analyze_var_decl(self, node):
        if node.var_type is not None:
            vt = node.var_type

            # v0.8.0: slice `[T]` — válido sem checar `structs`.
            is_slice = (
                isinstance(vt, str)
                and vt.startswith("[")
                and vt.endswith("]")
            )
            if not is_slice:
                base_type = vt.split('<')[0]
                is_fn_sig = base_type.startswith("fn(")
                if (base_type not in ("int", "float", "bool", "str", "ptr", "fn")
                        and not is_fn_sig
                        and base_type not in self.structs):
                    raise LuminaError(
                        f"Tipo '{vt}' não declarado.",
                        self.filename, 0, 0, self.source_code,
                    )

        if node.var_type is None and node.value is not None:
            self._infer_var_decl_type(node)

        if (isinstance(node.value, CallExpr)
                and getattr(node.value.callee, 'name', None) == "alloc"):
            self.heap_allocs.add(node.name)

        value_type = None
        if node.value:
            value_type = self.visit(node.value)

        if isinstance(node.value, ArrayExpr) and node.value.elements:
            first_t = self.visit(node.value.elements[0])
            if first_t:
                self.array_elem_types[node.name] = first_t

        if node.var_type is not None and value_type is not None:
            self._require_assignable(
                node.var_type, value_type,
                context=f"declaração de '{node.name}'",
                line=getattr(node, 'line', 0),
                col=getattr(node, 'col', 0),
            )

        self.declare_var(node.name, node.var_type, node.is_mutable)

    def _infer_var_decl_type(self, node):
        if isinstance(node.value, MemberExpr):
            field_type = self.visit(node.value)
            if field_type:
                node.var_type = field_type

        elif isinstance(node.value, BinaryExpr):
            node.var_type = self._infer_binary_type(node.value)

        elif isinstance(node.value, NoneExpr):
            node.var_type = "Option"

        elif isinstance(node.value, NilExpr):
            node.var_type = "ptr"

        elif isinstance(node.value, UnaryExpr):
            inferred = self.visit(node.value)
            if inferred:
                node.var_type = inferred

        elif isinstance(node.value, CastExpr):
            # `let x = expr as T` → x.var_type = T. Sem isso, o slot
            # do codegen defaulta para `int` e o valor é truncado
            # (fptosi) ou o member access subsequente falha com
            # "Tipo 'None' não é uma Struct/Enum".
            inferred = self.visit(node.value)
            node.var_type = inferred if inferred else node.value.target_type

        elif isinstance(node.value, ComptimeExpr):
            folded = self._constant_fold(node.value.expr)
            if folded is not None:
                node.value.folded = folded
                if isinstance(folded, NumberExpr):
                    node.var_type = "float" if folded.is_float else "int"
                elif isinstance(folded, BoolExpr):
                    node.var_type = "bool"
                elif isinstance(folded, StringExpr):
                    node.var_type = "str"

        elif isinstance(node.value, StringExpr):
            node.var_type = "str"

        elif isinstance(node.value, NumberExpr):
            node.var_type = "float" if node.value.is_float else "int"

        elif isinstance(node.value, BoolExpr):
            node.var_type = "bool"

        elif isinstance(node.value, StructLiteralExpr):
            node.var_type = node.value.struct_name

        elif isinstance(node.value, LambdaExpr):
            param_types = [p.type_ann for p in node.value.params]
            node.var_type = (
                f"fn({','.join(param_types)}) -> {node.value.return_type}"
            )

        elif isinstance(node.value, VariableExpr):
            info = self.get_var_info(node.value.name)
            if info and info.get('type'):
                node.var_type = info['type']
            elif node.value.name in self.functions:
                fn_def = self.function_defs.get(node.value.name)
                if fn_def:
                    params = [p.type_ann for p in fn_def.params]
                    node.var_type = (
                        f"fn({','.join(params)}) -> {fn_def.return_type}"
                    )

        elif isinstance(node.value, ArrayExpr):
            node.var_type = "ptr"

        elif isinstance(node.value, TupleExpr):
            node.var_type = "ptr"

        elif isinstance(node.value, AddressOfExpr):
            node.var_type = "ptr"

        elif isinstance(node.value, DerefExpr):
            node.var_type = "int"

        elif isinstance(node.value, PropagateExpr):
            node.var_type = "int"

        elif isinstance(node.value, SliceExpr):
            node.var_type = self.visit(node.value)

        elif isinstance(node.value, IndexExpr):
            inferred = self.visit(node.value)
            node.var_type = inferred if inferred else "int"

        elif isinstance(node.value, SliceExpr):
            node.var_type = self.visit(node.value)

        elif isinstance(node.value, CallExpr):
            node.var_type = self._infer_call_expr_type(node.value)

    def _infer_call_expr_type(self, call_node):
        func_name = None
        _callee = getattr(call_node, 'callee', None)
        if isinstance(_callee, MemberExpr):
            func_name = _callee.member
        elif isinstance(_callee, VariableExpr):
            func_name = _callee.name

        if not call_node.is_method and func_name:
            info = self.get_var_info(func_name)
            if info and info.get('type'):
                sig = parse_fn_type(info['type'])
                if sig is not None:
                    _, ret_type = sig
                    return ret_type if ret_type != "void" else None

        if call_node.is_method:
            obj_node = call_node.args[0]
            if isinstance(obj_node, VariableExpr):
                info = self.get_var_info(obj_node.name)
                if info and info['type']:
                    from ...common.mangle import mangle_method
                    obj_t = info['type']
                    base_name = obj_t.split('<')[0]
                    candidates = []
                    if "<" in obj_t:
                        candidates.append(mangle_method(obj_t, func_name))
                    candidates.append(f"{base_name}_{func_name}")
                    for c in candidates:
                        if c in self.function_defs:
                            return self.function_defs[c].return_type
                    return "int"

        if func_name in self.function_defs:
            fn_def = self.function_defs[func_name]
            ret_t = fn_def.return_type
            type_params = getattr(fn_def, 'type_params', None) or []

            if ret_t in type_params:
                inferred = "int"
                for arg_node, param in zip(call_node.args, fn_def.params):
                    if param.type_ann == ret_t:
                        at = self.visit(arg_node)
                        if at:
                            inferred = at
                        break
                return inferred
            return ret_t

        enum_name = self._find_enum_of_variant(func_name)
        if enum_name is not None:
            return enum_name
        return BUILTIN_RET.get(func_name, "int")

    # ------------------------------------------------------------------
    # DestructureStmt
    # ------------------------------------------------------------------
    def _analyze_destructure(self, node):
        self.visit(node.value)
        for name in node.names:
            self.declare_var(name, "int", node.is_mutable)

    # ------------------------------------------------------------------
    # Helpers de resolução de alvo (compartilhados por AssignStmt e
    # CompoundAssignStmt).
    # ------------------------------------------------------------------
    def _analyze_assign_target(self, target):
        """Resolve o tipo Lumina do alvo de uma atribuição.

        Faz os checks de mutabilidade/escopo e retorna o tipo do alvo
        (ou None). NÃO visita o value.
        """
        if isinstance(target, MemberExpr):
            self.check_escape(target.obj)
            if isinstance(target.obj, VariableExpr):
                info = self.get_var_info(target.obj.name)
                if not info:
                    raise LuminaError(
                        f"Variável '{target.obj.name}' não declarada.",
                        self.filename, 0, 0, self.source_code,
                    )
                if not info['mutable']:
                    raise LuminaError(
                        f"Não pode modificar variável imutável "
                        f"'{target.obj.name}'.",
                        self.filename, 0, 0, self.source_code,
                    )
                base_type = (info['type'].split('<')[0]
                             if info['type'] else "Unknown")
                if base_type not in self.struct_defs:
                    raise LuminaError(
                        f"Variável '{target.obj.name}' não é uma Struct.",
                        self.filename, 0, 0, self.source_code,
                    )
                struct_def = self.struct_defs[base_type]
                if target.member not in struct_def.fields:
                    raise LuminaError(
                        f"Campo '{target.member}' não existe na Struct "
                        f"'{info['type']}'.",
                        self.filename, 0, 0, self.source_code,
                    )
                return struct_def.fields[target.member]
            else:
                self.visit(target.obj)
            return None

        if isinstance(target, DerefExpr):
            return None

        if isinstance(target, IndexExpr):
            self.check_escape(target.array)
            arr_type = self.visit(target.array)
            self.visit(target.index)

            # v0.8.0: slice `[T]` → T.
            if (arr_type and isinstance(arr_type, str)
                    and arr_type.startswith("[") and arr_type.endswith("]")):
                return arr_type[1:-1]

            if arr_type == "str":
                return "int"
            if arr_type == "ptr":
                if isinstance(target.array, VariableExpr):
                    et = getattr(self, 'array_elem_types', {}).get(
                        target.array.name
                    )
                    return et if et else "int"
                return "int"
            if arr_type and "<" in arr_type:
                return None
            return None

        # VariableExpr
        self.check_escape(target)
        info = self.get_var_info(target.name)
        if not info:
            raise LuminaError(
                f"Variável '{target.name}' não declarada.",
                self.filename, 0, 0, self.source_code,
            )
        if not info['mutable']:
            raise LuminaError(
                f"Não pode reatribuir à variável imutável "
                f"'{target.name}'.",
                self.filename, 0, 0, self.source_code,
            )
        return info['type']

    # ------------------------------------------------------------------
    # AssignStmt
    # ------------------------------------------------------------------
    def _analyze_assign(self, node):
        target_type = self._analyze_assign_target(node.target)

        self.check_escape(node.value)
        value_type = self.visit(node.value)

        if target_type is not None and value_type is not None:
            self._require_assignable(target_type, value_type, context="atribuição")

    # ------------------------------------------------------------------
    # CompoundAssignStmt (P-10-2)
    # ------------------------------------------------------------------
    def _analyze_compound_assign(self, node):
        """`x op= y`.

        Target analisado UMA vez (diferente do caminho antigo que
        desaçucarava para `x = x op y`, avaliando o lvalue duas vezes).
        """
        target_type = self._analyze_assign_target(node.target)

        value_type = self.visit(node.value)

        if target_type is not None and value_type is not None:
            self._require_assignable(
                target_type, value_type, context="atribuição composta",
            )