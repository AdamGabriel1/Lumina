"""Corpo de função — geração de IR para o corpo de `fn`."""
from llvmlite import ir

from .context import push_context, normalize_attrs
from ..errors import LuminaError


class FunctionBodyMixin:

    def generate_function_body(self, node):
        func = self.functions_table[node.name][0]
        func_type = self.functions_table[node.name][1]

        attrs_norm = normalize_attrs(getattr(node, 'attrs', None))
        # v0.7.0: safe-by-default global.
        # `@safe` foi removido como opt-in — agora é o padrão.
        # `@unsafe` é o opt-out (não adiciona null checks em
        # MemberExpr/IndexExpr).
        is_unsafe = any(name == 'unsafe' for name, _args in attrs_norm)
        is_safe = not is_unsafe

        entry_bb = func.append_basic_block(name=f"{node.name}_entry")
        body_bb = func.append_basic_block(name=f"{node.name}_body")

        # Reset defensivo: se um generate_function_body anterior abortou
        # no meio, esses campos podem estar com valor sujo. push_context
        # garante que serão restaurados no final deste bloco.
        self._reset_function_codegen_state()

        # Builder começa no bloco de entrada.
        fresh_builder = ir.IRBuilder(entry_bb)

        with push_context(
            self,
            builder=fresh_builder,
            symbol_table={},
            var_types={},
            current_func_name=node.name,
            current_body_bb=body_bb,
            defer_stack=[],
            closure_vars=set(),
            _safe_mode=is_safe,
            _current_scc_slots=None,
            _current_scc_ids=None,
            _current_scc_id_slot=None,
            _current_scc_dispatch_bb=None,
            _fn_entry_block=entry_bb,
            _fn_return_type=func_type.return_type,
        ):
            # ----------------------------------------------------------
            # Fase 1 — entry_bb: setup de frame.
            # ----------------------------------------------------------
            if node.name == "main" and self.use_gc:
                gc_init = self.module.globals.get("GC_init")
                if gc_init is not None:
                    self.builder.call(gc_init, [], name="gc_init_call")

            if node.name == "main":
                argc_gv = self.module.globals.get("__lumina_argc")
                argv_gv = self.module.globals.get("__lumina_argv")
                if argc_gv is not None:
                    self.builder.store(func.args[0], argc_gv)
                if argv_gv is not None:
                    self.builder.store(func.args[1], argv_gv)

            for i, p in enumerate(node.params):
                p_name = p.name
                p_type = p.type_ann
                p_ty = self.get_llvm_param_type(p_type)
                ptr = self.builder.alloca(p_ty, name=p_name)
                self.builder.store(func.args[i], ptr)
                self.symbol_table[p_name] = ptr
                self.var_types[p_name] = p_type

            self.builder.branch(body_bb)
            self.builder.position_at_end(body_bb)

            # ----------------------------------------------------------
            # Fase 2 — body_bb: init runtime de globais, depois user code.
            # ----------------------------------------------------------
            if node.name == "main":
                for gv, init_expr in getattr(self, '_deferred_globals', []):
                    try:
                        val = self.visit(init_expr)
                        target_ty = gv.type.pointee
                        val = self._coerce_val_to(val, target_ty, name=gv.name)
                        self.builder.store(val, gv)
                    except Exception:
                        pass

            # ----------------------------------------------------------
            # Fase 3 — user code.
            # ----------------------------------------------------------
            for stmt in node.body:
                self.visit(stmt)

            self._fn_ensure_terminator()