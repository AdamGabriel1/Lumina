from llvmlite import ir


class FlowMixin:

    # ==================================================================
    # Escopo de defer
    # ==================================================================
    def _begin_scope(self):
        return len(getattr(self, 'defer_stack', []) or [])

    def _emit_scope_defers(self, start):
        stack = getattr(self, 'defer_stack', None)
        if not stack:
            return
        for body in reversed(stack[start:]):
            for stmt in body:
                if self.builder.block.is_terminated:
                    return
                self.visit(stmt)

    def _end_scope(self, start):
        stack = getattr(self, 'defer_stack', None)
        if not stack:
            return
        if not self.builder.block.is_terminated:
            self._emit_scope_defers(start)
        del stack[start:]

    def _emit_all_defers(self):
        self._emit_scope_defers(0)

    # ------------------------------------------------------------------
    # Helper: coerção de tipo antes do store
    # ------------------------------------------------------------------
    def _coerce_val_to(self, val, target_ty, name="val"):
        if val.type == target_ty:
            return val

        # v0.8.0: slice → ptr: extrai `.data`.
        if (isinstance(val.type, ir.PointerType)
                and isinstance(val.type.pointee, ir.IdentifiedStructType)
                and val.type.pointee.name.startswith("Slice_")
                and isinstance(target_ty, ir.PointerType)):
            data_gep = self.builder.gep(
                val,
                [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
                name=f"{name}_slice_data_gep",
            )
            data_ptr = self.builder.load(data_gep, name=f"{name}_slice_data")
            if data_ptr.type != target_ty:
                data_ptr = self.builder.bitcast(data_ptr, target_ty, name=f"{name}_slice_data_cast")
            return data_ptr

        # v0.8.0: ptr → slice: NÃO é feito implicitamente
        # (falta `.len`). Se o target é slice e o valor é ptr,
        # deixa cair no fallback (bitcast) que vai falhar no LLVM
        # com mensagem obscura. Alternativa: construir slice de
        # tamanho 0. Vou deixar assim por enquanto — o usuário
        # deve usar `as_slice(p, n)`.

        # int ↔ int
        if isinstance(val.type, ir.IntType) and isinstance(target_ty, ir.IntType):
            if val.type.width == 1 and target_ty.width > 1:
                return self.builder.zext(val, target_ty, name=f"{name}_zext")
            if val.type.width < target_ty.width:
                return self.builder.sext(val, target_ty, name=f"{name}_sext")
            if val.type.width > target_ty.width:
                return self.builder.trunc(val, target_ty, name=f"{name}_trunc")
            return val

        # int → float
        if isinstance(val.type, ir.IntType) and isinstance(target_ty, ir.DoubleType):
            return self.builder.sitofp(val, target_ty, name=f"{name}_sitofp")

        # float → int
        if isinstance(val.type, ir.DoubleType) and isinstance(target_ty, ir.IntType):
            return self.builder.fptosi(val, target_ty, name=f"{name}_fptosi")

        # i64 → str (via snprintf)
        if target_ty == self.voidptr_ty and val.type == self.i64_ty:
            int_buf = self.builder.alloca(
                ir.ArrayType(self.i8_ty, 32), name=f"{name}_int_buf"
            )
            int_buf_ptr = self.builder.bitcast(
                int_buf, self.voidptr_ty, name=f"{name}_int_buf_ptr"
            )
            fmt_str = self.create_global_string("%ld")
            self.builder.call(
                self.snprintf,
                [int_buf_ptr, ir.Constant(self.i64_ty, 32), fmt_str, val],
                name=f"{name}_snprintf",
            )
            return int_buf_ptr

        # str → i64 (via atoi)
        if target_ty == self.i64_ty and val.type == self.voidptr_ty:
            return self.builder.call(self.atoi, [val], name=f"{name}_atoi")

        # ptr → int
        if isinstance(val.type, ir.PointerType) and isinstance(target_ty, ir.IntType):
            return self.builder.ptrtoint(val, target_ty, name=f"{name}_ptrtoint")

        # int → ptr
        if isinstance(val.type, ir.IntType) and isinstance(target_ty, ir.PointerType):
            return self.builder.inttoptr(val, target_ty, name=f"{name}_inttoptr")

        # ptr → ptr
        if isinstance(val.type, ir.PointerType) and isinstance(target_ty, ir.PointerType):
            # Se o target espera um struct e val é ptr para o mesmo struct,
            # carrega o valor.
            if (isinstance(val.type.pointee, ir.IdentifiedStructType)
                    and val.type.pointee == target_ty.pointee):
                return self.builder.load(val, name=f"{name}_load")
            return self.builder.bitcast(val, target_ty, name=f"{name}_bitcast")

        # struct (valor) → ptr pro mesmo tipo
        if (isinstance(val.type, ir.IdentifiedStructType)
                and isinstance(target_ty, ir.PointerType)
                and val.type == target_ty.pointee):
            tmp = self.builder.alloca(val.type, name=f"{name}_struct_tmp")
            self.builder.store(val, tmp)
            return tmp

        try:
            return self.builder.bitcast(val, target_ty, name=f"{name}_final_cast")
        except Exception:
            return val

    # ------------------------------------------------------------------
    # Assign
    # ------------------------------------------------------------------
    def visit_AssignStmt(self, node):
        """
        Atribuição: `x = v`, `obj.field = v`, `arr[i] = v`.

        Toda coerção de tipo é delegada a `_coerce_val_to`, que cobre
        int↔int, int↔float, ptr↔int, ptr↔ptr, struct-by-ptr e str.

        A versão anterior tinha uma cadeia de casts ad-hoc na branch de
        MemberExpr que executava `ptrtoint double → i64` incondicionalmente
        quando os tipos não batiam — quebrava `b.data = 2.5` em `Box<float>`
        e `b.data = "hello"` em `Box<str>`.
        """
        val = self.visit(node.value)

        # ------------------------------------------------------------------
        # Alvo: variável local ou global mutável
        # ------------------------------------------------------------------
        if hasattr(node.target, 'name'):
            gv = getattr(self, 'global_mut_vars', {}).get(node.target.name)
            if gv is not None:
                target_ty = gv.type.pointee
                val = self._coerce_val_to(val, target_ty, name=node.target.name)
                self.builder.store(val, gv)
                return

            ptr = self.symbol_table.get(node.target.name)
            if ptr is not None:
                target_ty = ptr.type.pointee
                val = self._coerce_val_to(val, target_ty, name=node.target.name)
                self.builder.store(val, ptr)
            return

        # ------------------------------------------------------------------
        # Alvo: membro de struct (`obj.field = v`)
        # ------------------------------------------------------------------
        if hasattr(node.target, 'member'):
            obj_val = self.visit(node.target.obj)
            if (isinstance(obj_val.type, ir.PointerType)
                    and isinstance(obj_val.type.pointee, ir.IdentifiedStructType)):
                struct_name = obj_val.type.pointee.name
                fields_map = self.struct_fields.get(struct_name, {})
                field_idx = fields_map.get(node.target.member)
                if field_idx is not None:
                    elem_ptr = self.builder.gep(
                        obj_val,
                        [ir.Constant(self.i32_ty, 0),
                         ir.Constant(self.i32_ty, field_idx)],
                        name=f"{node.target.member}_ptr",
                    )
                    target_ty = elem_ptr.type.pointee
                    val = self._coerce_val_to(
                        val, target_ty, name=node.target.member
                    )
                    self.builder.store(val, elem_ptr)
            return

        # Alvo: índice de array/ptr/slice (`arr[i] = v`)
        if hasattr(node.target, 'index'):
            arr_val = self.visit(node.target.array)
            idx_val = self.visit(node.target.index)
            if isinstance(arr_val.type, ir.PointerType):
                # v0.8.0: slice → extrai `.data` primeiro.
                if (isinstance(arr_val.type.pointee, ir.IdentifiedStructType)
                        and arr_val.type.pointee.name.startswith("Slice_")):
                    data_gep = self.builder.gep(
                        arr_val,
                        [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
                        name="slice_assign_data_gep",
                    )
                    data_ptr = self.builder.load(data_gep, name="slice_assign_data")
                    elem_ptr = self.builder.gep(data_ptr, [idx_val], name="slice_assign_elem_ptr")
                elif isinstance(arr_val.type.pointee, ir.ArrayType):
                    elem_ptr = self.builder.gep(
                        arr_val,
                        [ir.Constant(self.i32_ty, 0), idx_val],
                        name="idx_ptr",
                    )
                else:
                    elem_ptr = self.builder.gep(
                        arr_val, [idx_val], name="idx_ptr"
                    )
                elem_ty = elem_ptr.type.pointee
                val = self._coerce_val_to(val, elem_ty, name="elem")
                self.builder.store(val, elem_ptr)
            return

    # ------------------------------------------------------------------
    # Return
    # ------------------------------------------------------------------
    def visit_ReturnStmt(self, node):
        if self.builder.block.is_terminated:
            return

        ret_ty = self.functions_table[self.current_func_name][1].return_type

        if ret_ty != self.void_ty and self._try_tail_call(node):
            return

        if ret_ty == self.void_ty:
            for v in node.values:
                self.visit(v)
            self._emit_all_defers()
            self.builder.ret_void()
            return

        if not node.values:
            self._emit_all_defers()
            self.builder.ret_void()
            return

        val = self.visit(node.values[0])
        if val.type != ret_ty:
            val = self._coerce_ret(val, ret_ty)

        self._emit_all_defers()
        self.builder.ret(val)

    def _coerce_ret(self, val, ret_ty):
        """
        Coerção para `return`. Diferente de `_coerce_val_to`:
        `i64 → ptr` faz `inttoptr` (reinterpretar bits), NÃO
        `snprintf` (formatar como string).

        Isso importa quando um `str` é retornado através de uma
        camada que o converteu para `i64` (closure fat pointer,
        impl Box<T> com base genérica, etc). O i64 contém os bits
        do ponteiro; reinterpretar é o comportamento correto.
        """
        if ret_ty == self.f64_ty and val.type == self.i64_ty:
            return self.builder.sitofp(val, self.f64_ty, name="ret_cast")
        if ret_ty == self.i64_ty and val.type == self.f64_ty:
            return self.builder.fptosi(val, self.i64_ty, name="ret_cast")
        if isinstance(ret_ty, ir.PointerType) and val.type == self.i64_ty:
            return self.builder.inttoptr(val, ret_ty, name="ret_inttoptr")
        if ret_ty == self.i64_ty and isinstance(val.type, ir.PointerType):
            return self.builder.ptrtoint(val, self.i64_ty, name="ret_ptrtoint")
        if isinstance(ret_ty, ir.PointerType) and isinstance(val.type, ir.PointerType):
            if ret_ty != val.type:
                return self.builder.bitcast(val, ret_ty, name="ret_ptr_cast")
            return val
        if (isinstance(val.type, ir.PointerType)
                and isinstance(val.type.pointee, ir.IdentifiedStructType)
                and val.type.pointee == ret_ty):
            return self.builder.load(val, name="ret_struct_load")
        if ret_ty == self.i64_ty and isinstance(val.type, ir.IntType) and val.type.width < 64:
            if val.type.width == 1:
                return self.builder.zext(val, self.i64_ty, name="ret_zext")
            return self.builder.sext(val, self.i64_ty, name="ret_sext")
        if (isinstance(ret_ty, ir.IntType) and ret_ty.width < 64
                and isinstance(val.type, ir.IntType)
                and val.type.width > ret_ty.width):
            return self.builder.trunc(val, ret_ty, name="ret_trunc")
        return val

    def visit_DestructureStmt(self, node):
        val = self.visit(node.value)

        # Struct (identificada ou literal)
        if (isinstance(val.type, ir.PointerType)
                and isinstance(val.type.pointee,
                               (ir.IdentifiedStructType, ir.LiteralStructType))):
            for i, name in enumerate(node.names):
                ep = self.builder.gep(
                    val,
                    [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, i)],
                    name=name + "_ptr",
                )
                fv = self.builder.load(ep, name=name)
                var_ptr = self.builder.alloca(fv.type, name=name)
                self.builder.store(fv, var_ptr)
                self.symbol_table[name] = var_ptr
                self.var_types[name] = self._llvm_ty_to_str(fv.type)
            return

        # ArrayType* (alloca de ArrayType)
        if (isinstance(val.type, ir.PointerType)
                and isinstance(val.type.pointee, ir.ArrayType)):
            elem_ty = val.type.pointee.element
            for i, name in enumerate(node.names):
                ep = self.builder.gep(
                    val,
                    [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, i)],
                    name=name + "_ptr",
                )
                fv = self.builder.load(ep, name=name)
                var_ptr = self.builder.alloca(elem_ty, name=name)
                self.builder.store(fv, var_ptr)
                self.symbol_table[name] = var_ptr
                self.var_types[name] = self._llvm_ty_to_str(elem_ty)
            return

        # Raw T* (alloc'd array)
        if isinstance(val.type, ir.PointerType):
            elem_ty = val.type.pointee
            for i, name in enumerate(node.names):
                ep = self.builder.gep(
                    val, [ir.Constant(self.i64_ty, i)],
                    name=name + "_ptr",
                )
                fv = self.builder.load(ep, name=name)
                fv = self._normalize_loaded(fv, name_hint=name)
                var_ptr = self.builder.alloca(fv.type, name=name)
                self.builder.store(fv, var_ptr)
                self.symbol_table[name] = var_ptr
                self.var_types[name] = self._llvm_ty_to_str(fv.type)
            return

    def visit_DeferStmt(self, node):
        if not hasattr(self, 'defer_stack'):
            self.defer_stack = []
        self.defer_stack.append(list(node.body))

    def visit_AssertStmt(self, node):
        cond = self.visit(node.condition)
        if cond.type != ir.IntType(1):
            cond = self.builder.icmp_signed(
                "!=", cond, ir.Constant(cond.type, 0), name="assert_cond"
            )

        ok_bb = self.builder.append_basic_block(name="assert_ok")
        fail_bb = self.builder.append_basic_block(name="assert_fail")
        self.builder.cbranch(cond, ok_bb, fail_bb)

        self.builder.position_at_end(fail_bb)
        fflush_fn = self.module.globals.get("fflush")
        if fflush_fn is None:
            fflush_ty = ir.FunctionType(ir.IntType(32), [self.i8_ty.as_pointer()])
            fflush_fn = ir.Function(self.module, fflush_ty, name="fflush")
        self.builder.call(
            fflush_fn, [ir.Constant(self.i8_ty.as_pointer(), None)]
        )
        abort_fn = self.module.globals.get("abort")
        if abort_fn is None:
            abort_ty = ir.FunctionType(ir.VoidType(), [])
            abort_fn = ir.Function(self.module, abort_ty, name="abort")
        self.builder.call(abort_fn, [])
        self.builder.unreachable()

        self.builder.position_at_end(ok_bb)

    def visit_BenchStmt(self, node):
        start = self._begin_scope()
        for stmt in node.body:
            if self.builder.block.is_terminated:
                break
            self.visit(stmt)
        self._end_scope(start)

    def visit_BreakStmt(self, node):
        if not getattr(self, 'loop_stack', None):
            return
        _, break_bb, scope_start = self.loop_stack[-1]
        self._emit_scope_defers(scope_start)
        if not self.builder.block.is_terminated:
            self.builder.branch(break_bb)

    def visit_ContinueStmt(self, node):
        if not getattr(self, 'loop_stack', None):
            return
        continue_bb, _, scope_start = self.loop_stack[-1]
        self._emit_scope_defers(scope_start)
        if not self.builder.block.is_terminated:
            self.builder.branch(continue_bb)

    def _try_tail_call(self, node):
        from ...ast import CallExpr as _CallExpr, VariableExpr as _VarExpr
        if len(node.values) != 1:
            return False
        val = node.values[0]
        if not isinstance(val, _CallExpr):
            return False
        if not isinstance(val.callee, _VarExpr):
            return False
        target = val.callee.name

        # ---- Caso 1: mutual TCO ----
        scc_slots = getattr(self, '_current_scc_slots', None)
        if scc_slots is not None and target in scc_slots:
            arg_vals = [self.visit(a) for a in val.args]
            slots = scc_slots[target]
            for i, slot_ptr in enumerate(slots):
                expected = slot_ptr.type.pointee
                a = arg_vals[i]
                if a.type != expected:
                    a = self._coerce_arg(a, expected, suffix=f"_scc{i}")
                self.builder.store(a, slot_ptr)

            target_id = self._current_scc_ids[target]
            self.builder.store(
                ir.Constant(self.i32_ty, target_id),
                self._current_scc_id_slot,
            )

            self._emit_all_defers()
            if self.builder.block.is_terminated:
                return True
            self.builder.branch(self._current_scc_dispatch_bb)
            return True

        # ---- Caso 2: self-recursion ----
        if target != getattr(self, 'current_func_name', None):
            return False
        body_bb = getattr(self, 'current_body_bb', None)
        if body_bb is None:
            return False

        fn_def = self.function_defs.get(self.current_func_name)
        if fn_def is None:
            return False

        func, func_type = self.functions_table[self.current_func_name]

        if len(val.args) != len(fn_def.params):
            return False

        arg_vals = []
        for i, arg_node in enumerate(val.args):
            v = self.visit(arg_node)
            expected = func_type.args[i] if i < len(func_type.args) else None
            if expected is not None and v.type != expected:
                v = self._coerce_arg(v, expected, suffix=f"_tco{i}")
            arg_vals.append(v)

        for i, p in enumerate(fn_def.params):
            ptr = self.symbol_table.get(p.name)
            if ptr is None:
                return False
            self.builder.store(arg_vals[i], ptr)

        self._emit_all_defers()
        if self.builder.block.is_terminated:
            return True
        self.builder.branch(body_bb)
        return True