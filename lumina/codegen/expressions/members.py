from llvmlite import ir
from ...ast import BinaryExpr, SliceExpr, VariableExpr, ArrayExpr


class MembersMixin:

    def _normalize_loaded(self, val, name_hint="load"):
        if isinstance(val.type, ir.IntType) and val.type.width < 64:
            if val.type.width == 1:
                return self.builder.zext(val, self.i64_ty, name=f"{name_hint}_zext")
            return self.builder.sext(val, self.i64_ty, name=f"{name_hint}_sext")
        if isinstance(val.type, ir.PointerType):
            return self.builder.ptrtoint(val, self.i64_ty, name=f"{name_hint}_ptrtoint")
        return val

    def _is_slice_ptr(self, val):
        """True se `val` é ponteiro para `%Slice_T_*`."""
        return (
            isinstance(val.type, ir.PointerType)
            and isinstance(val.type.pointee, ir.IdentifiedStructType)
            and val.type.pointee.name.startswith("Slice_")
        )

    def visit_VariableExpr(self, node):
        ptr = self.symbol_table.get(node.name)
        if ptr:
            return self.builder.load(ptr, name=node.name + "_load")

        lookup = self._find_enum_variant(node.name)
        if lookup is not None:
            enum_name, variant_idx = lookup
            enum_def = self.struct_defs[enum_name]
            for v in enum_def.variants:
                if v[0] != node.name:
                    continue
                payloads = v[1] if len(v) > 1 else []
                if not payloads:
                    type_params = getattr(enum_def, 'type_params', None) or []
                    if type_params:
                        default_args = ["int"] * len(type_params)
                        concrete = f"{enum_name}<{','.join(default_args)}>"
                        return self._construct_enum(concrete, variant_idx, [])
                    return self._construct_enum(enum_name, variant_idx, [])
                break

        if node.name in self.functions_table:
            func, _ = self.functions_table[node.name]
            return self._wrap_fn_as_closure(func, name_hint=node.name)

        gv = getattr(self, 'global_mut_vars', {}).get(node.name)
        if gv is not None:
            return self.builder.load(gv, name=f"g_{node.name}_load")

        global_node = getattr(self, 'global_var_decls', {}).get(node.name)
        if global_node is not None:
            return self.visit(global_node.value)

        return ir.Constant(self.i64_ty, 0)

    # ==================================================================
    # v0.8.0: `.data` e `.len` em slices.
    # ==================================================================
    def visit_MemberExpr(self, node):
        obj_val = self.visit(node.obj)

        if self._is_slice_ptr(obj_val):
            if node.member == "data":
                data_gep = self.builder.gep(
                    obj_val,
                    [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
                    name="slice_data_gep",
                )
                return self.builder.load(data_gep, name="slice_data")
            if node.member == "len":
                len_gep = self.builder.gep(
                    obj_val,
                    [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 1)],
                    name="slice_len_gep",
                )
                return self.builder.load(len_gep, name="slice_len")

        if not (isinstance(obj_val.type, ir.PointerType)
                and isinstance(obj_val.type.pointee, ir.IdentifiedStructType)):
            return ir.Constant(self.i64_ty, 0)

        struct_name = obj_val.type.pointee.name
        field_idx = self.struct_fields.get(struct_name, {}).get(node.member)
        if field_idx is None:
            return ir.Constant(self.i64_ty, 0)

        safe = node.is_safe or getattr(self, '_safe_mode', False)

        if not safe:
            elem_ptr = self.builder.gep(
                obj_val,
                [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, field_idx)],
            )
            return self.builder.load(elem_ptr, name=node.member + "_load")

        null_ptr = ir.Constant(obj_val.type, None)
        is_null = self.builder.icmp_signed("==", obj_val, null_ptr, name="safe_nav_isnull")

        null_bb = self.builder.append_basic_block(name="safe_nav_null")
        ok_bb = self.builder.append_basic_block(name="safe_nav_ok")
        end_bb = self.builder.append_basic_block(name="safe_nav_end")

        self.builder.cbranch(is_null, null_bb, ok_bb)

        self.builder.position_at_end(null_bb)
        self.builder.branch(end_bb)

        self.builder.position_at_end(ok_bb)
        elem_ptr = self.builder.gep(
            obj_val,
            [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, field_idx)],
        )
        field_val = self.builder.load(elem_ptr, name=node.member + "_load")
        self.builder.branch(end_bb)

        self.builder.position_at_end(end_bb)
        if isinstance(field_val.type, ir.PointerType):
            default_val = ir.Constant(field_val.type, None)
        else:
            default_val = ir.Constant(field_val.type, 0)
        phi = self.builder.phi(field_val.type, name="safe_nav_result")
        phi.add_incoming(default_val, null_bb)
        phi.add_incoming(field_val, ok_bb)
        return phi

    # ==================================================================
    # v0.8.0: `s[i]` reconhece slices.
    # ==================================================================
    def visit_IndexExpr(self, node):
        arr_val = self.visit(node.array)

        if self._is_slice_ptr(arr_val):
            return self._index_slice(node, arr_val)

        idx_val = self.visit(node.index)

        if not isinstance(arr_val.type, ir.PointerType):
            return ir.Constant(self.i64_ty, 0)

        if getattr(self, '_safe_mode', False):
            null_ptr = ir.Constant(arr_val.type, None)
            is_null = self.builder.icmp_signed("==", arr_val, null_ptr, name="safe_idx_isnull")

            null_bb = self.builder.append_basic_block(name="safe_idx_null")
            ok_bb = self.builder.append_basic_block(name="safe_idx_ok")
            end_bb = self.builder.append_basic_block(name="safe_idx_end")

            self.builder.cbranch(is_null, null_bb, ok_bb)

            self.builder.position_at_end(ok_bb)
            raw = self._load_index(arr_val, idx_val)
            self.builder.branch(end_bb)

            self.builder.position_at_end(null_bb)
            if isinstance(raw.type, ir.PointerType):
                default_val = ir.Constant(raw.type, None)
            elif raw.type == self.f64_ty:
                default_val = ir.Constant(raw.type, 0.0)
            else:
                default_val = ir.Constant(raw.type, 0)
            self.builder.branch(end_bb)

            self.builder.position_at_end(end_bb)
            phi = self.builder.phi(raw.type, name="safe_idx_result")
            phi.add_incoming(default_val, null_bb)
            phi.add_incoming(raw, ok_bb)
            return phi

        return self._load_index(arr_val, idx_val)

    def _index_slice(self, node, slice_ptr):
        idx_val = self.visit(node.index)
        if idx_val.type != self.i64_ty:
            idx_val = self._to_i64_int(idx_val, "slice_idx")

        data_gep = self.builder.gep(
            slice_ptr,
            [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
            name="slice_data_gep",
        )
        data_ptr = self.builder.load(data_gep, name="slice_data")

        len_gep = self.builder.gep(
            slice_ptr,
            [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 1)],
            name="slice_len_gep",
        )
        len_val = self.builder.load(len_gep, name="slice_len")

        safe = getattr(self, '_safe_mode', False)

        if safe:
            zero = ir.Constant(self.i64_ty, 0)
            is_neg = self.builder.icmp_signed("<", idx_val, zero, name="slice_idx_neg")
            is_oob = self.builder.icmp_signed(">=", idx_val, len_val, name="slice_idx_oob")
            invalid = self.builder.or_(is_neg, is_oob, name="slice_idx_invalid")

            bad_bb = self.builder.append_basic_block(name="slice_idx_bad")
            ok_bb = self.builder.append_basic_block(name="slice_idx_ok")
            end_bb = self.builder.append_basic_block(name="slice_idx_end")

            self.builder.cbranch(invalid, bad_bb, ok_bb)

            self.builder.position_at_end(ok_bb)
            elem_ptr = self.builder.gep(data_ptr, [idx_val], name="slice_elem_ptr")
            elem_ty = elem_ptr.type.pointee
            raw_ok = self._load_elem_from_ptr(elem_ptr, elem_ty)
            self.builder.branch(end_bb)

            self.builder.position_at_end(bad_bb)
            self.builder.branch(end_bb)

            self.builder.position_at_end(end_bb)
            if isinstance(raw_ok.type, ir.PointerType):
                default_val = ir.Constant(raw_ok.type, None)
            elif raw_ok.type == self.f64_ty:
                default_val = ir.Constant(raw_ok.type, 0.0)
            else:
                default_val = ir.Constant(raw_ok.type, 0)
            phi = self.builder.phi(raw_ok.type, name="slice_elem_result")
            phi.add_incoming(default_val, bad_bb)
            phi.add_incoming(raw_ok, ok_bb)
            return phi

        elem_ptr = self.builder.gep(data_ptr, [idx_val], name="slice_elem_ptr")
        elem_ty = elem_ptr.type.pointee
        return self._load_elem_from_ptr(elem_ptr, elem_ty)

    def _load_elem_from_ptr(self, elem_ptr, elem_ty):
        raw = self.builder.load(elem_ptr, name="elem_load")
        if elem_ty == self.i64_ty:
            return raw
        if elem_ty == self.f64_ty:
            return raw
        if isinstance(elem_ty, ir.PointerType):
            return raw
        if isinstance(elem_ty, ir.IntType) and elem_ty.width < 64:
            if elem_ty.width == 1:
                return self.builder.zext(raw, self.i64_ty, name="elem_zext")
            return self.builder.sext(raw, self.i64_ty, name="elem_sext")
        return raw

    def _load_index(self, arr_val, idx_val):
        if isinstance(arr_val.type.pointee, ir.ArrayType):
            elem_ptr = self.builder.gep(arr_val, [ir.Constant(self.i32_ty, 0), idx_val])
            elem_ty = elem_ptr.type.pointee
            raw = self.builder.load(elem_ptr, name="arr_idx_load")
        else:
            elem_ty = arr_val.type.pointee
            elem_ptr = self.builder.gep(arr_val, [idx_val])
            raw = self.builder.load(elem_ptr, name="ptr_idx_load")

        if elem_ty == self.i64_ty:
            return raw
        if elem_ty == self.f64_ty:
            return raw
        if isinstance(elem_ty, ir.PointerType):
            return raw
        if isinstance(elem_ty, ir.IntType) and elem_ty.width < 64:
            if elem_ty.width == 1:
                return self.builder.zext(raw, self.i64_ty, name="idx_zext")
            return self.builder.sext(raw, self.i64_ty, name="idx_sext")
        return raw

    def _to_i64_int(self, val, name_hint):
        if val.type == self.i64_ty:
            return val
        if isinstance(val.type, ir.IntType):
            if val.type.width == 1:
                return self.builder.zext(val, self.i64_ty, name=f"{name_hint}_zext")
            return self.builder.sext(val, self.i64_ty, name=f"{name_hint}_sext")
        return val

    # ==================================================================
    # v0.8.0: `visit_SliceExpr` — view `[T]`.
    #
    # FIX: `is_string` computado ANTES do teste `legacy or is_string`.
    # ==================================================================
    def visit_SliceExpr(self, node):
        import os
        legacy = os.environ.get("LUMINA_LEGACY_SLICE_COPY") == "1"

        arr_val = self.visit(node.array)

        if node.start is not None:
            start_val = self.visit(node.start)
            start_val = self._to_i64_int(start_val, "slice_start")
        else:
            start_val = ir.Constant(self.i64_ty, 0)

        # FIX: computar is_string imediatamente.
        is_string = (
            arr_val.type == self.voidptr_ty
            or (
                isinstance(arr_val.type, ir.PointerType)
                and arr_val.type.pointee == self.i8_ty
            )
        )

        if legacy or is_string:
            return self._legacy_slice_copy(node, arr_val, start_val)

        # ---- Slice → slice: composição ----
        if self._is_slice_ptr(arr_val):
            slice_in_ty = arr_val.type.pointee
            elem_ty = slice_in_ty.elements[0].pointee

            data_gep = self.builder.gep(
                arr_val,
                [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
                name="subslice_data_gep",
            )
            base_data = self.builder.load(data_gep, name="subslice_data")

            len_gep = self.builder.gep(
                arr_val,
                [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 1)],
                name="subslice_len_gep",
            )
            total_len = self.builder.load(len_gep, name="subslice_len")

            if node.end is not None:
                end_val = self.visit(node.end)
                end_val = self._to_i64_int(end_val, "slice_end")
            else:
                end_val = total_len

            length = self.builder.sub(end_val, start_val, name="subslice_len")
            data_ptr = self.builder.gep(base_data, [start_val], name="subslice_data_ptr")

            elem_lumina = self._llvm_ty_to_str(elem_ty)
            slice_out_ty = self.get_or_create_slice_type(f"[{elem_lumina}]")
            slice_out_ptr = self.builder.alloca(slice_out_ty, name="subslice_tmp")

            out_data_gep = self.builder.gep(
                slice_out_ptr,
                [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
                name="subslice_out_data_gep",
            )
            data_field_ty = slice_out_ty.elements[0]
            if data_ptr.type != data_field_ty:
                data_ptr = self.builder.bitcast(
                    data_ptr, data_field_ty, name="subslice_data_cast"
                )
            self.builder.store(data_ptr, out_data_gep)

            out_len_gep = self.builder.gep(
                slice_out_ptr,
                [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 1)],
                name="subslice_out_len_gep",
            )
            self.builder.store(length, out_len_gep)
            return slice_out_ptr

        # ---- Array nativo → view ----
        elem_ty = None
        total_len = None
        use_array_gep = False

        if isinstance(arr_val.type, ir.PointerType):
            if isinstance(arr_val.type.pointee, ir.ArrayType):
                elem_ty = arr_val.type.pointee.element
                total_len = ir.Constant(self.i64_ty, arr_val.type.pointee.count)
                use_array_gep = True
            else:
                elem_ty = arr_val.type.pointee

        if isinstance(node.array, VariableExpr):
            n = getattr(self, 'array_lengths', {}).get(node.array.name)
            if n is not None:
                total_len = ir.Constant(self.i64_ty, n)

        if isinstance(node.array, ArrayExpr):
            total_len = ir.Constant(self.i64_ty, len(node.array.elements))

        if elem_ty is None:
            return ir.Constant(self.i64_ty, 0)

        if node.end is not None:
            end_val = self.visit(node.end)
            end_val = self._to_i64_int(end_val, "slice_end")
        elif total_len is not None:
            end_val = total_len
        else:
            end_val = start_val

        length = self.builder.sub(end_val, start_val, name="slice_len")

        if use_array_gep:
            base_ptr = self.builder.gep(
                arr_val,
                [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
                name="slice_base",
            )
        else:
            base_ptr = arr_val

        data_ptr = self.builder.gep(base_ptr, [start_val], name="slice_data")

        elem_lumina = self._llvm_ty_to_str(elem_ty)
        slice_ty = self.get_or_create_slice_type(f"[{elem_lumina}]")
        slice_ptr = self.builder.alloca(slice_ty, name="slice_tmp")

        data_gep = self.builder.gep(
            slice_ptr,
            [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
            name="slice_data_gep",
        )
        data_field_ty = slice_ty.elements[0]
        if data_ptr.type != data_field_ty:
            data_ptr = self.builder.bitcast(data_ptr, data_field_ty, name="slice_data_cast")
        self.builder.store(data_ptr, data_gep)

        len_gep = self.builder.gep(
            slice_ptr,
            [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 1)],
            name="slice_len_gep",
        )
        self.builder.store(length, len_gep)

        return slice_ptr

    # ------------------------------------------------------------------
    # `--legacy-slice-copy` + retrocompat de strings: cópia explícita.
    # ------------------------------------------------------------------
    def _legacy_slice_copy(self, node, arr_val, start_val):
        is_string = (
            arr_val.type == self.voidptr_ty
            or (
                isinstance(arr_val.type, ir.PointerType)
                and arr_val.type.pointee == self.i8_ty
            )
        )

        if is_string:
            if node.end is not None:
                end_val = self.visit(node.end)
                end_val = self._to_i64_int(end_val, "slice_end")
            else:
                end_val = self.builder.call(self.strlen, [arr_val], name="slice_strlen")

            length = self.builder.sub(end_val, start_val, name="slice_len")
            length_plus = self.builder.add(
                length, ir.Constant(self.i64_ty, 1), name="slice_len_plus"
            )
            buf = self.builder.call(self.malloc, [length_plus], name="slice_buf")
            start_ptr = self.builder.gep(arr_val, [start_val], name="slice_start_ptr")
            self.builder.call(self.strncpy, [buf, start_ptr, length], name="slice_cpy")
            end_ptr = self.builder.gep(buf, [length], name="slice_end_ptr")
            self.builder.store(ir.Constant(self.i8_ty, 0), end_ptr)
            return buf

        # Array numérico: copia para `T*`.
        elem_ty = arr_val.type.pointee
        if node.end is not None:
            end_val = self.visit(node.end)
            end_val = self._to_i64_int(end_val, "slice_end")
        else:
            n = None
            if isinstance(node.array, VariableExpr):
                n = getattr(self, 'array_lengths', {}).get(node.array.name)
            if n is not None:
                end_val = ir.Constant(self.i64_ty, n)
            else:
                end_val = start_val

        length = self.builder.sub(end_val, start_val, name="slice_len")
        elem_bytes = 8 if not isinstance(elem_ty, ir.IntType) else max(1, elem_ty.width // 8)
        byte_count = self.builder.mul(
            length, ir.Constant(self.i64_ty, elem_bytes), name="slice_arr_bytes"
        )
        raw = self.builder.call(self.malloc, [byte_count], name="slice_arr_buf")
        out = self.builder.bitcast(raw, elem_ty.as_pointer(), name="slice_arr_cast")
        src = self.builder.gep(arr_val, [start_val], name="slice_arr_src")

        loop_bb = self.builder.append_basic_block(name="slice_loop")
        end_bb = self.builder.append_basic_block(name="slice_end")
        pred_bb = self.builder.block
        self.builder.branch(loop_bb)
        self.builder.position_at_end(loop_bb)
        i = self.builder.phi(self.i64_ty, name="slice_i")
        i.add_incoming(ir.Constant(self.i64_ty, 0), pred_bb)
        src_ptr = self.builder.gep(src, [i], name="slice_src_ptr")
        v = self.builder.load(src_ptr, name="slice_val")
        dst_ptr = self.builder.gep(out, [i], name="slice_dst_ptr")
        self.builder.store(v, dst_ptr)
        nxt = self.builder.add(i, ir.Constant(self.i64_ty, 1), name="slice_i_next")
        i.add_incoming(nxt, self.builder.block)
        cond = self.builder.icmp_signed("<", nxt, length, name="slice_cond")
        self.builder.cbranch(cond, loop_bb, end_bb)
        self.builder.position_at_end(end_bb)
        return out