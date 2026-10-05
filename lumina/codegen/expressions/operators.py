from llvmlite import ir
from ...ast import (
    VariableExpr, BinaryExpr, UnaryExpr, CastExpr,
    AddressOfExpr, DerefExpr, PropagateExpr,
)


class OperatorsMixin:

    # ------------------------------------------------------------------
    # Helpers de normalização
    # ------------------------------------------------------------------
    def _normalize_ints(self, left, right):
        """Se um lado é i64 e o outro é iN (N<64), estende o menor.

        Cobre i1 (bool), i8 (char), i32, etc. Também converte ponteiros
        em i64 quando o outro lado é int (permitido por design).
        """
        if isinstance(left.type, ir.PointerType) and right.type == self.i64_ty:
            left = self.builder.ptrtoint(left, self.i64_ty, name="bin_ptrtoint_l")
        elif left.type == self.i64_ty and isinstance(right.type, ir.PointerType):
            right = self.builder.ptrtoint(right, self.i64_ty, name="bin_ptrtoint_r")

        if (isinstance(left.type, ir.IntType) and isinstance(right.type, ir.IntType)
                and left.type != right.type):
            target = self.i64_ty
            if left.type.width < 64:
                if left.type.width == 1:
                    left = self.builder.zext(left, target, name="bin_zext_l")
                else:
                    left = self.builder.sext(left, target, name="bin_sext_l")
            if right.type.width < 64:
                if right.type.width == 1:
                    right = self.builder.zext(right, target, name="bin_zext_r")
                else:
                    right = self.builder.sext(right, target, name="bin_sext_r")

        return left, right

    def _try_struct_operator(self, node, left, right):
        """Se ambos são ponteiros para o mesmo struct, procura
        Struct___op__ e chama. Retorna o valor ou None.
        """
        if not (isinstance(left.type, ir.PointerType)
                and isinstance(left.type.pointee, ir.IdentifiedStructType)):
            return None
        if left.type != right.type:
            return None

        struct_name = left.type.pointee.name
        op_map = {
            '+': '__add__', '-': '__sub__', '*': '__mul__', '/': '__div__',
            '==': '__eq__', '!=': '__ne__', '<': '__lt__', '>': '__gt__',
            '<=': '__le__', '>=': '__ge__',
        }
        method_name = op_map.get(node.op)
        if not method_name:
            return None

        real_name = f"{struct_name}_{method_name}"
        if real_name not in self.functions_table:
            return None

        func = self.functions_table[real_name][0]
        result = self.builder.call(func, [left, right], name=f"op_{real_name}")

        # Se o operador retorna struct por ponteiro, o ponteiro aponta
        # para a stack do callee — inválido após o retorno. Copia os
        # campos para um slot novo na stack do caller.
        if (isinstance(result.type, ir.PointerType)
                and isinstance(result.type.pointee, ir.IdentifiedStructType)):
            struct_ty = result.type.pointee
            slot = self.builder.alloca(struct_ty, name=f"op_{real_name}_copy")
            for i in range(len(struct_ty.elements)):
                src = self.builder.gep(
                    result,
                    [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, i)],
                    name=f"op_src_{i}",
                )
                dst = self.builder.gep(
                    slot,
                    [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, i)],
                    name=f"op_dst_{i}",
                )
                field = self.builder.load(src, name=f"op_field_{i}")
                self.builder.store(field, dst)
            return slot

        return result

    def _try_string_concat(self, node, left, right):
        """Retorna o resultado de `str + str` (i8*), ou None se não se aplica."""
        if node.op != '+':
            return None
        if left.type != self.voidptr_ty or right.type != self.voidptr_ty:
            return None

        len1 = self.builder.call(self.strlen, [left], name="sconcat_len1")
        len2 = self.builder.call(self.strlen, [right], name="sconcat_len2")
        sum_len = self.builder.add(len1, len2, name="sconcat_sum")
        total_len = self.builder.add(sum_len, ir.Constant(self.i64_ty, 1), name="sconcat_total")
        buf = self.builder.call(self.malloc, [total_len], name="sconcat_buf")
        self.builder.call(self.strcpy, [buf, left], name="sconcat_cpy")
        self.builder.call(self.strcat, [buf, right], name="sconcat_cat")
        return buf

    # ------------------------------------------------------------------
    # Binários
    # ------------------------------------------------------------------
    def visit_BinaryExpr(self, node):
        # Short-circuit: avalia `left` e decide se avalia `right`.
        #
        # FIX: este é o ÚNICO branch de `and`/`or`. Antes havia um
        # segundo bloco mais abaixo com o comentário "sem short-circuit
        # por enquanto" — era código morto, inalcançável (o `return`
        # deste bloco já sai). Foi removido.
        if node.op in ('and', 'or'):
            left = self.visit(node.left)
            if not (isinstance(left.type, ir.IntType) and left.type.width == 1):
                left = self.builder.icmp_signed(
                    "!=", left, ir.Constant(left.type, 0), name="to_bool_l"
                )

            rhs_bb = self.builder.append_basic_block(name=f"{node.op}_rhs")
            end_bb = self.builder.append_basic_block(name=f"{node.op}_end")
            pred_bb = self.builder.block

            if node.op == 'and':
                self.builder.cbranch(left, rhs_bb, end_bb)
            else:
                self.builder.cbranch(left, end_bb, rhs_bb)

            self.builder.position_at_end(rhs_bb)
            right = self.visit(node.right)
            if not (isinstance(right.type, ir.IntType) and right.type.width == 1):
                right = self.builder.icmp_signed(
                    "!=", right, ir.Constant(right.type, 0), name="to_bool_r"
                )
            rhs_end_bb = self.builder.block
            self.builder.branch(end_bb)

            self.builder.position_at_end(end_bb)
            phi = self.builder.phi(ir.IntType(1), name=f"{node.op}_result")
            default = ir.Constant(ir.IntType(1), 0 if node.op == 'and' else 1)
            phi.add_incoming(default, pred_bb)
            phi.add_incoming(right, rhs_end_bb)
            return phi

        left = self.visit(node.left)
        right = self.visit(node.right)

        if left is None or right is None:
            return ir.Constant(self.i64_ty, 0)

        # Concatenação de strings com '+' (quando já são str+str)
        concat = self._try_string_concat(node, left, right)
        if concat is not None:
            return concat

        # Overload de operador em struct
        struct_result = self._try_struct_operator(node, left, right)
        if struct_result is not None:
            return struct_result

        # Coerção: se um lado é string, converte o número
        if left.type == self.voidptr_ty and right.type in (self.i64_ty, self.f64_ty):
            if right.type == self.f64_ty:
                fmt = self.create_global_string("%f")
            else:
                fmt = self.create_global_string("%ld")
            buf = self._fn_emit_alloca("num_to_str", ir.ArrayType(self.i8_ty, 64))
            buf_ptr = self.builder.bitcast(buf, self.voidptr_ty, name="num_to_str_ptr")
            self.builder.call(self.snprintf, [buf_ptr, ir.Constant(self.i64_ty, 64), fmt, right], name="num_to_str_call")
            right = buf_ptr
        elif right.type == self.voidptr_ty and left.type in (self.i64_ty, self.f64_ty):
            if left.type == self.f64_ty:
                fmt = self.create_global_string("%f")
            else:
                fmt = self.create_global_string("%ld")
            buf = self._fn_emit_alloca("num_to_str", ir.ArrayType(self.i8_ty, 64))
            buf_ptr = self.builder.bitcast(buf, self.voidptr_ty, name="num_to_str_ptr")
            self.builder.call(self.snprintf, [buf_ptr, ir.Constant(self.i64_ty, 64), fmt, left], name="num_to_str_call")
            left = buf_ptr

        # Tenta concat após coerção (ex: `"count: " + 42`)
        concat = self._try_string_concat(node, left, right)
        if concat is not None:
            return concat

        # Matemática
        if node.op in ('+', '-', '*', '/', '%'):
            if left.type == self.voidptr_ty or right.type == self.voidptr_ty:
                return ir.Constant(self.i64_ty, 0)

            left, right = self._normalize_ints(left, right)

            if left.type == self.f64_ty or right.type == self.f64_ty:
                left = self.to_float_if_needed(left)
                right = self.to_float_if_needed(right)
                if node.op == '+':
                    return self.builder.fadd(left, right, name="fadd")
                elif node.op == '-':
                    return self.builder.fsub(left, right, name="fsub")
                elif node.op == '*':
                    return self.builder.fmul(left, right, name="fmul")
                elif node.op == '/':
                    return self.builder.fdiv(left, right, name="fdiv")
            else:
                if node.op == '+':
                    return self.builder.add(left, right, name="add")
                elif node.op == '-':
                    return self.builder.sub(left, right, name="sub")
                elif node.op == '*':
                    return self.builder.mul(left, right, name="mul")
                elif node.op == '/':
                    return self.builder.sdiv(left, right, name="div")
                elif node.op == '%':
                    return self.builder.srem(left, right, name="mod")

        # Bitwise e shifts
        if node.op in ('&', '|', '^', '<<', '>>'):
            if left.type == self.voidptr_ty or right.type == self.voidptr_ty:
                return ir.Constant(self.i64_ty, 0)
            left, right = self._normalize_ints(left, right)
            if left.type != right.type:
                if isinstance(left.type, ir.IntType) and isinstance(right.type, ir.IntType):
                    if left.type.width < right.type.width:
                        left = self.builder.sext(left, right.type, name="bw_ext_l")
                    else:
                        right = self.builder.sext(right, left.type, name="bw_ext_r")
            if node.op == '&':
                return self.builder.and_(left, right, name="bitand")
            if node.op == '|':
                return self.builder.or_(left, right, name="bitor")
            if node.op == '^':
                return self.builder.xor(left, right, name="bitxor")
            if node.op == '<<':
                return self.builder.shl(left, right, name="shl")
            if node.op == '>>':
                return self.builder.ashr(left, right, name="ashr")

        # Comparações
        if node.op in ('==', '!=', '<', '>', '<=', '>='):
            if left.type != right.type:
                left, right = self._normalize_ints(left, right)
            if left.type != right.type:
                if isinstance(left.type, ir.PointerType) and right.type == self.i64_ty:
                    left = self.builder.ptrtoint(left, self.i64_ty, name="cmp_ptrtoint_l")
                elif left.type == self.i64_ty and isinstance(right.type, ir.PointerType):
                    right = self.builder.ptrtoint(right, self.i64_ty, name="cmp_ptrtoint_r")
                elif isinstance(left.type, ir.PointerType) and isinstance(right.type, ir.PointerType):
                    right = self.builder.bitcast(right, left.type, name="cmp_ptr_bitcast")

            # Comparar strings (i8*) por conteúdo via strcmp.
            if node.op in ('==', '!=') and left.type == self.voidptr_ty and right.type == self.voidptr_ty:
                null_ptr = ir.Constant(self.voidptr_ty, None)
                a_null = self.builder.icmp_signed("==", left, null_ptr, name="a_null")
                b_null = self.builder.icmp_signed("==", right, null_ptr, name="b_null")
                either_null = self.builder.or_(a_null, b_null, name="either_null")

                null_bb = self.builder.append_basic_block(name="strcmp_null")
                str_bb = self.builder.append_basic_block(name="strcmp_ok")
                end_bb = self.builder.append_basic_block(name="strcmp_end")

                self.builder.cbranch(either_null, null_bb, str_bb)

                self.builder.position_at_end(null_bb)
                if node.op == '==':
                    ptr_eq = self.builder.icmp_signed("==", left, right, name="ptr_eq")
                else:
                    ptr_eq = self.builder.icmp_signed("!=", left, right, name="ptr_ne")
                self.builder.branch(end_bb)

                self.builder.position_at_end(str_bb)
                cmp = self.builder.call(self.strcmp, [left, right], name="strcmp_call")
                zero = ir.Constant(ir.IntType(32), 0)
                if node.op == '==':
                    str_eq = self.builder.icmp_signed("==", cmp, zero, name="str_eq")
                else:
                    str_eq = self.builder.icmp_signed("!=", cmp, zero, name="str_ne")
                self.builder.branch(end_bb)

                self.builder.position_at_end(end_bb)
                phi = self.builder.phi(ir.IntType(1), name="str_cmp_res")
                phi.add_incoming(ptr_eq, null_bb)
                phi.add_incoming(str_eq, str_bb)
                return phi
            if left.type == self.f64_ty or right.type == self.f64_ty:
                left = self.to_float_if_needed(left)
                right = self.to_float_if_needed(right)
                return self.builder.fcmp_ordered(node.op, left, right, name="fcmp")
            else:
                return self.builder.icmp_signed(node.op, left, right, name="icmp")

        return ir.Constant(self.i64_ty, 0)

    def visit_UnaryExpr(self, node):
        val = self.visit(node.val)
        if node.op == '-':
            return self.builder.neg(val, name="neg") if val.type == self.i64_ty else self.builder.fneg(val, name="fneg")
        elif node.op == 'not':
            if isinstance(val.type, ir.IntType) and val.type.width == 1:
                one = ir.Constant(ir.IntType(1), 1)
                return self.builder.xor(val, one, name="not_bool")
            elif isinstance(val.type, ir.IntType):
                zero = ir.Constant(val.type, 0)
                return self.builder.icmp_signed("==", val, zero, name="not_int")
            elif isinstance(val.type, ir.PointerType):
                null = ir.Constant(val.type, None)
                return self.builder.icmp_signed("==", val, null, name="not_ptr")
            return val
        elif node.op == '~':
            # ADR 0003: `~x` fora de quote: é bitwise NOT (int).
            if isinstance(val.type, ir.IntType):
                return self.builder.not_(val, name="bitnot")
            # Fallback: tipo desconhecido — retorna como está.
            return val
        return val

    def visit_CastExpr(self, node):
        val = self.visit(node.expr)
        # `get_llvm_param_type` (não `get_llvm_type`): structs são
        # sempre por ponteiro. Sem isso, `x as Struct` retorna `%Struct`
        # em vez de `%Struct*` e o cast é no-op silencioso.
        target_ty = self.get_llvm_param_type(node.target_type)
        if val.type == target_ty:
            return val
        if val.type == self.i64_ty and target_ty == self.f64_ty:
            return self.builder.sitofp(val, self.f64_ty, name="int_to_float")
        elif val.type == self.f64_ty and target_ty == self.i64_ty:
            return self.builder.fptosi(val, self.i64_ty, name="float_to_int")
        elif isinstance(val.type, ir.PointerType) and target_ty == self.i64_ty:
            return self.builder.ptrtoint(val, self.i64_ty, name="ptr_to_int")
        elif val.type == self.i64_ty and isinstance(target_ty, ir.PointerType):
            return self.builder.inttoptr(val, target_ty, name="int_to_ptr")
        elif isinstance(val.type, ir.IntType) and isinstance(target_ty, ir.IntType):
            if val.type.width < target_ty.width:
                if val.type.width == 1:
                    return self.builder.zext(val, target_ty, name="cast_zext")
                return self.builder.sext(val, target_ty, name="cast_sext")
            return self.builder.trunc(val, target_ty, name="cast_trunc")
        elif isinstance(val.type, ir.PointerType) and isinstance(target_ty, ir.PointerType):
            # `ptr → Struct*` ou `StructA* → StructB*`: bitcast.
            if val.type != target_ty:
                return self.builder.bitcast(val, target_ty, name="cast_ptr")
            return val
        return val

    def visit_AddressOfExpr(self, node):
        if isinstance(node.val, VariableExpr):
            ptr = self.symbol_table.get(node.val.name)
            if ptr:
                # Structs são armazenadas por ponteiro em Lumina: o
                # slot é `%Struct**`, e a "variável" é o valor
                # `%Struct*` dentro dele. Para `&s` dar `%Struct*`
                # (o que o usuário espera), carregamos.
                #
                # Primitivos (i64, f64) são armazenados por valor:
                # o slot já é o endereço, então devolvemos direto.
                if (isinstance(ptr.type.pointee, ir.PointerType)
                        and isinstance(ptr.type.pointee.pointee,
                                       ir.IdentifiedStructType)):
                    return self.builder.load(
                        ptr, name=node.val.name + "_addr",
                    )
                return ptr
            if node.val.name in self.functions_table:
                func, _ = self.functions_table[node.val.name]
                return self.builder.bitcast(
                    func, self.voidptr_ty, name=node.val.name + "_rawfn",
                )
        return self.visit(node.val)

    def visit_DerefExpr(self, node):
        ptr = self.visit(node.val)
        if not isinstance(ptr.type, ir.PointerType):
            return ir.Constant(self.i64_ty, 0)
        return self.builder.load(ptr, name="deref_load")

    def visit_PropagateExpr(self, node):
        result_ptr = self.visit(node.val)

        if not (isinstance(result_ptr.type, ir.PointerType)
                and isinstance(result_ptr.type.pointee, ir.IdentifiedStructType)):
            return result_ptr

        struct_name = result_ptr.type.pointee.name
        if struct_name != "Result":
            return result_ptr

        tag_ptr = self.builder.gep(
            result_ptr,
            [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 0)],
            name="prop_tag_ptr",
        )
        tag_val = self.builder.load(tag_ptr, name="prop_tag")

        is_err = self.builder.icmp_signed(
            "!=", tag_val, ir.Constant(self.i32_ty, 0), name="prop_iserr",
        )

        err_bb = self.builder.append_basic_block(name="prop_err")
        ok_bb = self.builder.append_basic_block(name="prop_ok")

        self.builder.cbranch(is_err, err_bb, ok_bb)

        self.builder.position_at_end(err_bb)
        func_ret_ty = self.functions_table[self.current_func_name][1].return_type
        if result_ptr.type != func_ret_ty:
            if isinstance(func_ret_ty, ir.PointerType):
                ret_val = self.builder.bitcast(result_ptr, func_ret_ty, name="prop_ret_cast")
            else:
                ret_val = self.builder.ptrtoint(result_ptr, func_ret_ty, name="prop_ret_int")
        else:
            ret_val = result_ptr
        self.builder.ret(ret_val)

        self.builder.position_at_end(ok_bb)
        payload_ptr = self.builder.gep(
            result_ptr,
            [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, 1)],
            name="prop_payload_ptr",
        )
        payload_val = self.builder.load(payload_ptr, name="prop_payload")

        return payload_val

    def visit_ChainedComparisonExpr(self, node):
        """`a < b < c < d` avalia cada operando UMA vez."""
        counter = getattr(self, '_chain_counter', 0)
        self._chain_counter = counter + 1

        slots = []
        for i, operand in enumerate(node.operands):
            v = self.visit(operand)
            slot_name = f"__chain_{counter}_{i}"
            slot = self.builder.alloca(v.type, name=slot_name)
            self.builder.store(v, slot)
            slots.append((slot_name, slot, v.type))

        for slot_name, slot, ty in slots:
            self.symbol_table[slot_name] = slot
            self.var_types[slot_name] = self._llvm_ty_to_str(ty)

        try:
            result = None
            for i, op in enumerate(node.ops):
                left_var = VariableExpr(slots[i][0], 0, 0)
                right_var = VariableExpr(slots[i + 1][0], 0, 0)
                cmp_node = BinaryExpr(op, left_var, right_var)
                cmp_val = self.visit_BinaryExpr(cmp_node)

                if result is None:
                    result = cmp_val
                else:
                    result = self.builder.and_(
                        result, cmp_val, name=f"chain_and_{i}"
                    )
        finally:
            for slot_name, _, _ in slots:
                self.symbol_table.pop(slot_name, None)
                self.var_types.pop(slot_name, None)

        if result is None:
            return ir.Constant(ir.IntType(1), 1)
        return result