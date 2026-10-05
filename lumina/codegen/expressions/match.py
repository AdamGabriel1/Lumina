from llvmlite import ir
from ...ast import VariableExpr, StructLiteralExpr


class MatchExprMixin:

    def visit_MatchExpr(self, node):
        cond_val = self.visit(node.condition)

        # 1. Match sobre i64 (switch)
        if cond_val.type == self.i64_ty:
            end_bb = self.builder.append_basic_block(name="match_end")
            default_bb = self.builder.append_basic_block(name="match_default")
            sw = self.builder.switch(cond_val, default_bb)
            incoming = []
            phi_ty = None

            for case in node.cases:
                if isinstance(case, tuple):
                    val_node, res_node = case
                else:
                    val_node = case.pattern
                    res_node = case.body

                case_bb = self.builder.append_basic_block(name="match_case")
                val = self.visit(val_node)
                sw.add_case(val, case_bb)
                self.builder.position_at_end(case_bb)
                res_val = self.visit(res_node)

                if phi_ty is None:
                    phi_ty = res_val.type
                elif phi_ty != res_val.type:
                    res_val = self.builder.bitcast(res_val, phi_ty, name="case_cast")

                if not self.builder.block.is_terminated:
                    self.builder.branch(end_bb)
                    incoming.append((res_val, self.builder.block))

            self.builder.position_at_end(default_bb)
            if node.default:
                default_val = self.visit(node.default)
                if phi_ty is None:
                    phi_ty = default_val.type
                elif phi_ty != default_val.type:
                    default_val = self.builder.bitcast(default_val, phi_ty, name="def_cast")

                if not self.builder.block.is_terminated:
                    self.builder.branch(end_bb)
                    incoming.append((default_val, self.builder.block))
            else:
                if not self.builder.block.is_terminated:
                    self.builder.branch(end_bb)
                    incoming.append((ir.Constant(self.i64_ty, 0), self.builder.block))

            self.builder.position_at_end(end_bb)
            if phi_ty is None:
                phi_ty = self.i64_ty
            phi = self.builder.phi(phi_ty, name="match_res")
            for val, blk in incoming:
                phi.add_incoming(val, blk)
            return phi

        # 2. Match sobre string (strcmp encadeado)
        elif cond_val.type == self.voidptr_ty:
            strcmp_fn = next((f for f in self.module.functions if f.name == "strcmp"), None)
            if not strcmp_fn:
                strcmp_ty = ir.FunctionType(ir.IntType(32), [self.voidptr_ty, self.voidptr_ty])
                strcmp_fn = ir.Function(self.module, strcmp_ty, name="strcmp")

            end_bb = self.builder.append_basic_block(name="match_str_end")
            incoming = []
            phi_ty = None

            for case in node.cases:
                if isinstance(case, tuple):
                    val_node, res_node = case
                else:
                    val_node = case.pattern
                    res_node = case.body

                val_str = self.visit(val_node)
                cmp_res = self.builder.call(strcmp_fn, [cond_val, val_str], name="strcmp_call")
                is_eq = self.builder.icmp_signed("==", cmp_res, ir.Constant(ir.IntType(32), 0), name="str_eq")

                then_bb = self.builder.append_basic_block(name="match_str_case")
                next_bb = self.builder.append_basic_block(name="match_str_next")
                self.builder.cbranch(is_eq, then_bb, next_bb)

                self.builder.position_at_end(then_bb)
                res_val = self.visit(res_node)
                if phi_ty is None:
                    phi_ty = res_val.type
                elif phi_ty != res_val.type:
                    res_val = self.builder.bitcast(res_val, phi_ty, name="str_case_cast")

                if not self.builder.block.is_terminated:
                    self.builder.branch(end_bb)
                    incoming.append((res_val, self.builder.block))

                self.builder.position_at_end(next_bb)

            if node.default:
                default_val = self.visit(node.default)
                if phi_ty is None:
                    phi_ty = default_val.type
                elif phi_ty != default_val.type:
                    default_val = self.builder.bitcast(default_val, phi_ty, name="str_def_cast")

                if not self.builder.block.is_terminated:
                    self.builder.branch(end_bb)
                    incoming.append((default_val, self.builder.block))
            else:
                if not self.builder.block.is_terminated:
                    self.builder.branch(end_bb)
                    incoming.append((ir.Constant(self.i64_ty, 0), self.builder.block))

            self.builder.position_at_end(end_bb)
            if phi_ty is None:
                phi_ty = self.i64_ty
            phi = self.builder.phi(phi_ty, name="match_str_res")
            for val, blk in incoming:
                phi.add_incoming(val, blk)
            return phi

        # 3. Match sobre struct (destructuring)
        elif isinstance(cond_val.type, ir.PointerType) and isinstance(cond_val.type.pointee, ir.IdentifiedStructType):
            struct_name = cond_val.type.pointee.name
            end_bb = self.builder.append_basic_block(name="match_struct_end")
            incoming = []
            phi_ty = None

            for case in node.cases:
                if isinstance(case, tuple):
                    val_node, res_node = case
                else:
                    val_node = case.pattern
                    res_node = case.body

                if isinstance(val_node, StructLiteralExpr) and val_node.struct_name == struct_name:
                    then_bb = self.builder.append_basic_block(name="match_struct_case")
                    next_bb = self.builder.append_basic_block(name="match_struct_next")

                    self.builder.branch(then_bb)
                    self.builder.position_at_end(then_bb)

                    for field in val_node.fields:
                        if isinstance(field, tuple):
                            fname, fexpr = field
                        else:
                            fname = field.name
                            fexpr = field.value

                        if isinstance(fexpr, VariableExpr):
                            elem_index = self.struct_fields[struct_name].get(fname)
                            if elem_index is not None:
                                elem_ptr = self.builder.gep(cond_val, [ir.Constant(self.i32_ty, 0), ir.Constant(self.i32_ty, elem_index)])
                                field_val = self.builder.load(elem_ptr, name="bind_val")
                                var_ptr = self.builder.alloca(field_val.type, name=fexpr.name)
                                self.builder.store(field_val, var_ptr)
                                self.symbol_table[fexpr.name] = var_ptr

                    res_val = self.visit(res_node)
                    if phi_ty is None:
                        phi_ty = res_val.type
                    elif phi_ty != res_val.type:
                        res_val = self.builder.bitcast(res_val, phi_ty, name="struct_case_cast")

                    if not self.builder.block.is_terminated:
                        self.builder.branch(end_bb)
                        incoming.append((res_val, self.builder.block))

                    self.builder.position_at_end(next_bb)

            if node.default:
                default_val = self.visit(node.default)
                if phi_ty is None:
                    phi_ty = default_val.type
                elif phi_ty != default_val.type:
                    default_val = self.builder.bitcast(default_val, phi_ty, name="struct_def_cast")

                if not self.builder.block.is_terminated:
                    self.builder.branch(end_bb)
                    incoming.append((default_val, self.builder.block))
            else:
                if not self.builder.block.is_terminated:
                    self.builder.branch(end_bb)
                    incoming.append((ir.Constant(self.i64_ty, 0), self.builder.block))

            self.builder.position_at_end(end_bb)
            if phi_ty is None:
                phi_ty = self.i64_ty
            phi = self.builder.phi(phi_ty, name="match_struct_res")
            for val, blk in incoming:
                phi.add_incoming(val, blk)
            return phi

        return ir.Constant(self.i64_ty, 0)
