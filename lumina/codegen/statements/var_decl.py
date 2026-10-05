from llvmlite import ir
from ...ast import (
    CallExpr, ArrayExpr, LambdaExpr, VariableExpr, NumberExpr,
    MemberExpr, IndexExpr,
    CompoundAssignStmt,
)
from ...errors import LuminaError
from ..constants import I64_BYTES, STACK_ALLOC_LIMIT


class VarDeclMixin:

    def _zero_and_store_struct(self, ptr, struct_ty, name):
        zero_fields = []
        for ft in struct_ty.elements:
            if isinstance(ft, ir.PointerType):
                zero_fields.append(ir.Constant(ft, None))
            elif isinstance(ft, ir.DoubleType):
                zero_fields.append(ir.Constant(ft, 0.0))
            elif isinstance(ft, ir.IntType):
                zero_fields.append(ir.Constant(ft, 0))
            else:
                zero_fields.append(ir.Constant(ft, None))
        try:
            zero_val = ir.Constant(struct_ty, zero_fields)
        except Exception:
            zero_val = None

        ptr_pointee = ptr.type.pointee

        if ptr_pointee == struct_ty:
            if zero_val is not None:
                self.builder.store(zero_val, ptr)
            return

        try:
            n_fields = len(struct_ty.elements)
        except Exception:
            n_fields = 4
        size = I64_BYTES * n_fields if n_fields > 0 else I64_BYTES
        raw = self.builder.call(
            self.malloc,
            [ir.Constant(self.i64_ty, size)],
            name=name + "_storage_raw",
        )
        storage = self.builder.bitcast(
            raw, struct_ty.as_pointer(), name=name + "_storage"
        )
        if zero_val is not None:
            try:
                self.builder.store(zero_val, storage)
            except Exception:
                pass

        if storage.type != ptr_pointee:
            if isinstance(ptr_pointee, ir.PointerType):
                storage = self.builder.bitcast(storage, ptr_pointee, name=name + "_cast")
            else:
                storage_int = self.builder.ptrtoint(storage, self.i64_ty, name=name + "_int")
                storage = self.builder.inttoptr(storage_int, ptr_pointee, name=name + "_cast")
        self.builder.store(storage, ptr)

    # ==================================================================
    # v0.7.0: dois caminhos de stack alloc.
    #
    #   1. N literal ≤ STACK_ALLOC_LIMIT → `alloca [elem; N]`
    #   2. N dinâmico, seguro → VLA via `alloca elem, N`
    #
    # "Seguro" exige: não estar em loop; estar no bloco de topo da
    # função (não em if/else); sem escape; sem `free`.
    #
    # Qualquer dúvida cai para GC/malloc.
    #
    # Nota importante sobre escape analysis: escrever `buf[i] = v`
    # marca `buf` como escaping (conservador — pode ser refinado
    # em v0.8.x). Por isso, `alloc(N); buf[i] = v` no mesmo escopo
    # NÃO usa stack, apesar do tamanho conhecido. Documentado em
    # `docs/engineering/bugs.md`.
    # ==================================================================
    def _try_stack_alloc(self, node):
        if node.value is None:
            return None

        callee = getattr(getattr(node.value, 'callee', None), 'name', None)
        if callee not in ('alloc', 'alloc_bytes'):
            return None

        escapes = getattr(self, 'escapes', set())
        freed = getattr(self, 'freed_vars', set())
        if node.name in escapes or node.name in freed:
            return None

        args = getattr(node.value, 'args', None) or []
        if not args:
            return None

        elem_ty = self.i64_ty if callee == 'alloc' else self.i8_ty

        # ------------------------------------------------------------------
        # Caminho 1: N literal.
        # ------------------------------------------------------------------
        if isinstance(args[0], NumberExpr):
            try:
                n = int(args[0].value, 0)
            except (ValueError, AttributeError):
                return None

            if n <= 0:
                raise LuminaError(
                    message=(
                        f"alloc({n}) inválido: tamanho deve ser positivo. "
                        f"Se o tamanho é dinâmico, use uma variável "
                        f"(desabilita stack alloc e usa GC/malloc)."
                    ),
                    filename=getattr(self, 'current_filename', '<codegen>'),
                    line=getattr(args[0], 'line', 0) or 0,
                    col=getattr(args[0], 'col', 0) or 0,
                    source_code=getattr(self, 'source_code', '') or '',
                )

            if n > STACK_ALLOC_LIMIT:
                return None

            arr_ty = ir.ArrayType(elem_ty, n)
            arr_ptr = self.builder.alloca(arr_ty, name=node.name + "_stack")

            zero = ir.Constant(self.i32_ty, 0)
            first_elem = self.builder.gep(
                arr_ptr, [zero, zero], name=node.name + "_first"
            )

            slot_ty = elem_ty.as_pointer()
            slot = self.builder.alloca(slot_ty, name=node.name)

            self.builder.store(first_elem, slot)
            self.symbol_table[node.name] = slot
            self.var_types[node.name] = "ptr"
            self.array_lengths[node.name] = n

            return slot

        # ------------------------------------------------------------------
        # Caminho 2: N dinâmico — VLA, mas só se seguro.
        # ------------------------------------------------------------------
        in_loop = bool(getattr(self, 'loop_stack', None))
        if in_loop:
            return None

        current_body = getattr(self, 'current_body_bb', None)
        if current_body is None or self.builder.block != current_body:
            return None

        n_val = self.visit(args[0])
        if n_val.type != self.i64_ty:
            if isinstance(n_val.type, ir.IntType) and n_val.type.width < 64:
                n_val = self.builder.sext(n_val, self.i64_ty, name=f"{node.name}_vla_sext")
            elif n_val.type == self.f64_ty:
                n_val = self.builder.fptosi(n_val, self.i64_ty, name=f"{node.name}_vla_fptosi")
            else:
                # Não é int — não dá para alloca dinâmico.
                return None

        vla_ptr = self.builder.alloca(
            elem_ty, n_val, name=node.name + "_vla"
        )

        slot_ty = elem_ty.as_pointer()
        slot = self.builder.alloca(slot_ty, name=node.name)

        self.builder.store(vla_ptr, slot)
        self.symbol_table[node.name] = slot
        self.var_types[node.name] = "ptr"
        # `array_lengths` não é setado (tamanho dinâmico).
        # `heap_allocs` não é setado — é stack.

        return slot

    def visit_VarDecl(self, node):
        if self._try_stack_alloc(node):
            return

        val = self.visit(node.value) if node.value else None
        var_type = node.var_type if node.var_type else "int"

        callee_name = (
            getattr(node.value.callee, 'name', None)
            if isinstance(node.value, CallExpr) else None
        )
        is_alloc_call = callee_name == "alloc"
        is_alloc_bytes_call = callee_name == "alloc_bytes"

        is_struct_like = (
            (var_type in self.struct_types and not var_type.endswith("*"))
            or ("<" in var_type and var_type.split("<")[0] in self.struct_defs)
        )

        if is_alloc_call:
            llvm_ty = self.i64_ty.as_pointer()
        elif is_alloc_bytes_call:
            llvm_ty = self.i8_ty.as_pointer()
        elif is_struct_like:
            struct_ty = self.get_llvm_type(var_type)
            llvm_ty = struct_ty.as_pointer()
        elif (val is not None
                and isinstance(val.type, ir.PointerType)
                and isinstance(val.type.pointee, ir.IdentifiedStructType)):
            llvm_ty = val.type
        elif val is not None and isinstance(val.type, ir.IdentifiedStructType):
            llvm_ty = val.type
        elif (val is not None
                and isinstance(val.type, ir.PointerType)
                and not isinstance(val.type.pointee, ir.ArrayType)):
            llvm_ty = val.type
        else:
            llvm_ty = self.get_llvm_type(var_type)

        ptr = self.builder.alloca(llvm_ty, name=node.name)
        self.symbol_table[node.name] = ptr
        self.var_types[node.name] = var_type

        if val is not None:
            if is_alloc_call:
                val = self.builder.bitcast(val, self.i64_ty.as_pointer(), name="alloc_bitcast")
                self.builder.store(val, ptr)
            elif isinstance(val.type, ir.PointerType) and isinstance(ptr.type.pointee, ir.PointerType):
                if val.type != ptr.type.pointee:
                    val = self.builder.bitcast(val, ptr.type.pointee, name="ptr_cast")
                self.builder.store(val, ptr)
            elif val.type == ptr.type.pointee:
                self.builder.store(val, ptr)
            elif isinstance(val.type, ir.IdentifiedStructType) and ptr.type.pointee == val.type.as_pointer():
                tmp = self.builder.alloca(val.type, name="struct_tmp")
                self.builder.store(val, tmp)
                self.builder.store(tmp, ptr)
            elif ptr.type.pointee == self.i64_ty and val.type == self.voidptr_ty:
                res = self.builder.call(self.atoi, [val], name="str_to_int_call")
                self.builder.store(res, ptr)
            elif ptr.type.pointee == self.voidptr_ty and val.type == self.i64_ty:
                int_buf = self.builder.alloca(ir.ArrayType(self.i8_ty, 32), name="int_to_str_buf")
                int_buf_ptr = self.builder.bitcast(int_buf, self.voidptr_ty, name="int_str_ptr")
                fmt_str = self.create_global_string("%ld")
                self.builder.call(self.snprintf, [int_buf_ptr, ir.Constant(self.i64_ty, 32), fmt_str, val], name="int_to_str_call")
                self.builder.store(int_buf_ptr, ptr)
            elif ptr.type.pointee == self.i64_ty and val.type == self.f64_ty:
                val = self.builder.fptosi(val, self.i64_ty, name="float_to_int_store")
                self.builder.store(val, ptr)
            elif ptr.type.pointee == self.f64_ty and val.type == self.i64_ty:
                val = self.builder.sitofp(val, self.f64_ty, name="int_to_float_store")
                self.builder.store(val, ptr)
            else:
                target_ty = ptr.type.pointee
                if isinstance(val.type, ir.IntType) and isinstance(target_ty, ir.IntType):
                    if val.type.width < target_ty.width:
                        if val.type.width == 1:
                            val = self.builder.zext(val, target_ty, name="zext_cast")
                        else:
                            val = self.builder.sext(val, target_ty, name="sext_cast")
                    else:
                        val = self.builder.trunc(val, target_ty, name="trunc_cast")
                elif isinstance(val.type, ir.PointerType) and isinstance(target_ty, ir.IntType):
                    val = self.builder.ptrtoint(val, target_ty, name="ptrtoint_cast")
                elif isinstance(val.type, ir.IntType) and isinstance(target_ty, ir.PointerType):
                    val = self.builder.inttoptr(val, target_ty, name="inttoptr_cast")
                elif isinstance(val.type, ir.PointerType) and isinstance(target_ty, ir.PointerType):
                    val = self.builder.bitcast(val, target_ty, name="ptr_bitcast")
                else:
                    try:
                        val = self.builder.bitcast(val, target_ty, name="final_cast")
                    except Exception:
                        pass
                self.builder.store(val, ptr)

        elif is_struct_like:
            struct_ty = self.get_llvm_type(var_type)
            self._zero_and_store_struct(ptr, struct_ty, node.name)

        else:
            try:
                if isinstance(ptr.type.pointee, ir.PointerType):
                    zero = ir.Constant(ptr.type.pointee, None)
                elif isinstance(ptr.type.pointee, ir.DoubleType):
                    zero = ir.Constant(ptr.type.pointee, 0.0)
                else:
                    zero = ir.Constant(ptr.type.pointee, 0)
                self.builder.store(zero, ptr)
            except Exception:
                pass

        if isinstance(node.value, LambdaExpr) and getattr(node.value, 'free_vars', None):
            self.closure_vars.add(node.name)
        elif isinstance(node.value, VariableExpr) and node.value.name in self.closure_vars:
            self.closure_vars.add(node.name)

        if isinstance(node.value, CallExpr):
            callee_name_v = getattr(node.value.callee, 'name', None)
            if callee_name_v in ('alloc', 'alloc_bytes') and node.value.args:
                from ...ast import NumberExpr
                arg0 = node.value.args[0]
                if isinstance(arg0, NumberExpr) and not arg0.is_float:
                    try:
                        self.array_lengths[node.name] = int(arg0.value, 0)
                    except (ValueError, TypeError):
                        pass

        if isinstance(node.value, ArrayExpr):
            self.array_lengths[node.name] = len(node.value.elements)

        if is_alloc_call or is_alloc_bytes_call:
            self.heap_allocs.add(node.name)

    # ==================================================================
    # CompoundAssignStmt (P-10-2)
    # ==================================================================
    def _resolve_lvalue(self, target):
        """Retorna `(ptr, llvm_ty)` para o lvalue, ou `(None, None)`.

        Resolve o endereço do alvo UMA vez. Usado por
        `visit_CompoundAssignStmt`.
        """
        # VariableExpr (local ou global)
        if isinstance(target, VariableExpr):
            gv = getattr(self, 'global_mut_vars', {}).get(target.name)
            if gv is not None:
                return gv, gv.type.pointee
            ptr = self.symbol_table.get(target.name)
            if ptr is None:
                return None, None
            return ptr, ptr.type.pointee

        # obj.field
        if isinstance(target, MemberExpr):
            obj_val = self.visit(target.obj)
            if not (isinstance(obj_val.type, ir.PointerType)
                    and isinstance(obj_val.type.pointee, ir.IdentifiedStructType)):
                return None, None
            struct_name = obj_val.type.pointee.name
            field_idx = self.struct_fields.get(struct_name, {}).get(target.member)
            if field_idx is None:
                return None, None
            ptr = self.builder.gep(
                obj_val,
                [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, field_idx)],
                name=f"{target.member}_ptr",
            )
            return ptr, ptr.type.pointee

        # arr[idx] — agora com slices (FIX #1)
        if isinstance(target, IndexExpr):
            arr_val = self.visit(target.array)
            idx_val = self.visit(target.index)
            if not isinstance(arr_val.type, ir.PointerType):
                return None, None

            # v0.8.0: slice → extrai `.data` antes do GEP.
            # Sem isto, `s[0] += 1` faz GEP em `%Slice_T_*` (o struct)
            # em vez de no backing buffer (`T*`).
            if (isinstance(arr_val.type.pointee, ir.IdentifiedStructType)
                    and arr_val.type.pointee.name.startswith("Slice_")):
                data_gep = self.builder.gep(
                    arr_val,
                    [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
                    name="slice_ca_data_gep",
                )
                data_ptr = self.builder.load(data_gep, name="slice_ca_data")
                ptr = self.builder.gep(data_ptr, [idx_val], name="slice_ca_idx_ptr")
            elif isinstance(arr_val.type.pointee, ir.ArrayType):
                ptr = self.builder.gep(
                    arr_val,
                    [ir.Constant(self.i32_ty, 0), idx_val],
                    name="idx_ptr",
                )
            else:
                ptr = self.builder.gep(arr_val, [idx_val], name="idx_ptr")
            return ptr, ptr.type.pointee

        return None, None

    def _apply_binop(self, op, lhs, rhs):
        """Aplica `lhs op rhs` com coerção de tipos padrão Lumina."""
        if isinstance(lhs.type, ir.IntType) and isinstance(rhs.type, ir.IntType):
            if lhs.type.width != rhs.type.width:
                if lhs.type.width < rhs.type.width:
                    lhs = self.builder.sext(lhs, rhs.type, name="compound_sext_l")
                else:
                    rhs = self.builder.sext(rhs, lhs.type, name="compound_sext_r")
        elif lhs.type == self.f64_ty or rhs.type == self.f64_ty:
            if lhs.type != self.f64_ty:
                lhs = self.builder.sitofp(lhs, self.f64_ty, name="compound_itof_l")
            if rhs.type != self.f64_ty:
                rhs = self.builder.sitofp(rhs, self.f64_ty, name="compound_itof_r")

        if lhs.type == self.f64_ty:
            ops = {
                '+': self.builder.fadd,
                '-': self.builder.fsub,
                '*': self.builder.fmul,
                '/': self.builder.fdiv,
            }
        else:
            ops = {
                '+': self.builder.add,
                '-': self.builder.sub,
                '*': self.builder.mul,
                '/': self.builder.sdiv,
                '&': self.builder.and_,
                '|': self.builder.or_,
                '^': self.builder.xor,
            }

        fn = ops.get(op)
        if fn is None:
            return lhs
        return fn(lhs, rhs, name=f"compound_{op}")

    def visit_CompoundAssignStmt(self, node):
        """`x op= y` com avaliação única do lvalue."""
        ptr, target_ty = self._resolve_lvalue(node.target)
        if ptr is None:
            return

        old_val = self.builder.load(ptr, name="compound_old")
        rhs = self.visit(node.value)

        result = self._apply_binop(node.op, old_val, rhs)
        result = self._coerce_val_to(result, target_ty, name="compound")
        self.builder.store(result, ptr)