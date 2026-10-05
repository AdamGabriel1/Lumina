"""Materialização de funções genéricas (monomorphization).

v0.7.0: safe-by-default. Cópias especializadas herdam o `_safe_mode`
do contexto de geração (que agora é `True` por padrão), a menos que
a `gen_def` original tenha `@unsafe`.
"""
from llvmlite import ir

from .context import push_context, normalize_attrs
from ..semantic.types import substitute_generic
from ..errors import LuminaError


class GenericsMixin:

    def materialize_generic(self, gen_def, type_map):
        type_params = getattr(gen_def, 'type_params', None) or []

        def _sanitize(s):
            return (s.replace("<", "_").replace(">", "_")
                     .replace(",", "_").replace(" ", ""))

        suffix_parts = [_sanitize(type_map.get(tp, "unknown"))
                        for tp in type_params]
        mangled = f"{gen_def.name}__{'_'.join(suffix_parts)}"

        # Reuso: já materializado nesta mesma compilação.
        if mangled in self.functions_table:
            return mangled

        def resolve_lumina(name):
            return substitute_generic(name, type_map)

        ret_lumina = resolve_lumina(gen_def.return_type)
        ret_ty = self.get_llvm_param_type(ret_lumina)

        param_tys = []
        for p in gen_def.params:
            param_lumina = resolve_lumina(p.type_ann)
            param_tys.append(self.get_llvm_param_type(param_lumina))

        func_type = ir.FunctionType(ret_ty, param_tys)
        func = ir.Function(self.module, func_type, name=mangled)

        # v0.7.0: safe-by-default. `@unsafe` na gen_def original
        # desliga null checks na cópia especializada.
        attrs_norm = normalize_attrs(getattr(gen_def, 'attrs', None))
        self._apply_llvm_attrs(func, attrs_norm)
        is_unsafe = any(name == 'unsafe' for name, _args in attrs_norm)
        is_safe = not is_unsafe

        # Registra antes de emitir o corpo (recursão / referências circulares).
        self.functions_table[mangled] = (func, func_type)
        self.function_defs[mangled] = gen_def

        entry_bb = func.append_basic_block(name=f"{mangled}_entry")
        body_bb = func.append_basic_block(name=f"{mangled}_body")
        fresh_builder = ir.IRBuilder(entry_bb)

        with push_context(
            self,
            builder=fresh_builder,
            symbol_table={},
            var_types={},
            current_func_name=mangled,
            current_body_bb=body_bb,
            defer_stack=[],
            closure_vars=set(),
            _safe_mode=is_safe,
            _current_scc_slots=None,
            _current_scc_ids=None,
            _current_scc_id_slot=None,
            _current_scc_dispatch_bb=None,
            _fn_entry_block=entry_bb,
            _fn_return_type=ret_ty,
        ):
            for i, p in enumerate(gen_def.params):
                p_name = p.name
                p_ty = param_tys[i]
                ptr = self.builder.alloca(p_ty, name=p_name)
                self.builder.store(func.args[i], ptr)
                self.symbol_table[p_name] = ptr
                self.var_types[p_name] = resolve_lumina(p.type_ann)

            self.builder.branch(body_bb)
            self.builder.position_at_end(body_bb)

            for stmt in gen_def.body:
                self.visit(stmt)

            # Fallback de retorno.
            if not self.builder.block.is_terminated:
                if isinstance(ret_ty, ir.VoidType):
                    self.builder.ret_void()
                elif isinstance(ret_ty, ir.LiteralStructType):
                    zero_fields = [ir.Constant(ft, 0) for ft in ret_ty.elements]
                    self.builder.ret(ir.Constant(ret_ty, zero_fields))
                else:
                    self.builder.ret(self._zero_for_type(ret_ty))

        return mangled

    # ==================================================================
    # Inferência de tipos a partir de nós da AST
    # ==================================================================
    def _infer_arg_type_lumina(self, arg_node):
        from ..ast import (
            NumberExpr, StringExpr, BoolExpr, NilExpr, VariableExpr,
            CallExpr, MemberExpr, StructLiteralExpr, LambdaExpr,
        )

        if isinstance(arg_node, NumberExpr):
            return "float" if arg_node.is_float else "int"
        if isinstance(arg_node, StringExpr):
            return "str"
        if isinstance(arg_node, BoolExpr):
            return "bool"
        if isinstance(arg_node, NilExpr):
            return "nil"

        if isinstance(arg_node, VariableExpr):
            vt = getattr(self, 'var_types', {}).get(arg_node.name)
            if vt:
                return vt
            if arg_node.name in getattr(self, 'struct_defs', {}):
                return arg_node.name

        if isinstance(arg_node, CallExpr):
            callee = getattr(arg_node, 'callee', None)
            callee_name = None
            if callee is not None:
                callee_name = getattr(callee, 'name', None) or \
                              getattr(callee, 'member', None)

            if callee_name:
                lookup = self._find_enum_variant(callee_name)
                if lookup is not None:
                    enum_name, _variant_idx = lookup
                    return enum_name

                fn_def = getattr(self, 'function_defs', {}).get(callee_name)
                if fn_def is not None and not getattr(fn_def, 'type_params', None):
                    return fn_def.return_type

        if isinstance(arg_node, MemberExpr):
            obj_type = self.var_types.get(getattr(arg_node.obj, 'name', None))
            if obj_type:
                base = obj_type.split('<')[0]
                sdef = self.struct_defs.get(base)
                if sdef is not None:
                    return sdef.fields.get(arg_node.member)

        if isinstance(arg_node, StructLiteralExpr):
            return arg_node.struct_name

        if isinstance(arg_node, LambdaExpr):
            params = ",".join(p.type_ann for p in arg_node.params)
            return f"fn({params}) -> {arg_node.return_type}"

        return None

    def _infer_type_map_lumina(self, gen_def, node):
        from ..semantic.types import unify_type

        type_map = {}
        params = gen_def.params
        args = node.args

        if len(args) == len(params) + 1 and params:
            args = args[1:]

        for p, arg_node in zip(params, args):
            arg_type = self._infer_arg_type_lumina(arg_node)
            if arg_type is None:
                continue
            unify_type(p.type_ann, arg_type, type_map)

        return type_map