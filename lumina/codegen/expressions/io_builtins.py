"""Builtins de arquivo: `write_file` e `read_file`.

Separados de `builtins.py` porque usam muitos `append_basic_block` e
`phi` — são mais pesados que os builtins de console.
"""
from llvmlite import ir


class IOBuiltinsMixin:

    def _call_io_builtin(self, func_name, node):
        if func_name == "write_file":
            path_val = self.visit(node.args[0])
            content_val = self.visit(node.args[1])
            if not isinstance(path_val.type, ir.PointerType):
                path_val = self.builder.inttoptr(
                    path_val, self.i8_ty.as_pointer(), name="wf_path_cast",
                )
            if not isinstance(content_val.type, ir.PointerType):
                content_val = self.builder.inttoptr(
                    content_val, self.i8_ty.as_pointer(), name="wf_content_cast",
                )

            fopen_ty = ir.FunctionType(
                self.voidptr_ty, [self.i8_ty.as_pointer(), self.i8_ty.as_pointer()],
            )
            fopen = self.module.globals.get("fopen") or ir.Function(
                self.module, fopen_ty, name="fopen",
            )

            fputs_ty = ir.FunctionType(self.i32_ty, [self.i8_ty.as_pointer(), self.voidptr_ty])
            fputs = self.module.globals.get("fputs") or ir.Function(
                self.module, fputs_ty, name="fputs",
            )

            fclose_ty = ir.FunctionType(self.i32_ty, [self.voidptr_ty])
            fclose = self.module.globals.get("fclose") or ir.Function(
                self.module, fclose_ty, name="fclose",
            )

            mode_w = self.create_global_string("w")
            fp = self.builder.call(fopen, [path_val, mode_w], name="wf_fopen")
            self.builder.call(fputs, [content_val, fp], name="wf_fputs")
            self.builder.call(fclose, [fp], name="wf_fclose")
            return ir.Constant(self.i64_ty, 0)

        if func_name == "read_file":
            path_val = self.visit(node.args[0])
            if not isinstance(path_val.type, ir.PointerType):
                path_val = self.builder.inttoptr(
                    path_val, self.i8_ty.as_pointer(), name="rf_path_cast",
                )

            fopen_ty = ir.FunctionType(
                self.voidptr_ty, [self.i8_ty.as_pointer(), self.i8_ty.as_pointer()],
            )
            fopen = self.module.globals.get("fopen") or ir.Function(
                self.module, fopen_ty, name="fopen",
            )

            fseek_ty = ir.FunctionType(self.i32_ty, [self.voidptr_ty, self.i64_ty, self.i32_ty])
            fseek = self.module.globals.get("fseek") or ir.Function(
                self.module, fseek_ty, name="fseek",
            )

            ftell_ty = ir.FunctionType(self.i64_ty, [self.voidptr_ty])
            ftell = self.module.globals.get("ftell") or ir.Function(
                self.module, ftell_ty, name="ftell",
            )

            fread_ty = ir.FunctionType(
                self.i64_ty,
                [self.i8_ty.as_pointer(), self.i64_ty, self.i64_ty, self.voidptr_ty],
            )
            fread = self.module.globals.get("fread") or ir.Function(
                self.module, fread_ty, name="fread",
            )

            fclose_ty = ir.FunctionType(self.i32_ty, [self.voidptr_ty])
            fclose = self.module.globals.get("fclose") or ir.Function(
                self.module, fclose_ty, name="fclose",
            )

            mode_r = self.create_global_string("r")
            fp = self.builder.call(fopen, [path_val, mode_r], name="rf_fopen")

            # Null check: fopen retorna NULL se o arquivo não existe.
            fp_int = self.builder.ptrtoint(fp, self.i64_ty, name="rf_fp_int")
            is_null = self.builder.icmp_signed(
                "==", fp_int, ir.Constant(self.i64_ty, 0), name="rf_is_null",
            )

            null_bb = self.builder.append_basic_block(name="rf_null")
            ok_bb = self.builder.append_basic_block(name="rf_ok")
            end_bb = self.builder.append_basic_block(name="rf_end")

            self.builder.cbranch(is_null, null_bb, ok_bb)

            # Caminho null: retorna string vazia
            self.builder.position_at_end(null_bb)
            empty_str = self.create_global_string("")
            empty_ptr = self.builder.bitcast(empty_str, self.i8_ty.as_pointer(), name="rf_empty")
            self.builder.branch(end_bb)

            # Caminho normal: fseek → ftell → fseek → fread → fclose
            self.builder.position_at_end(ok_bb)
            self.builder.call(
                fseek,
                [fp, ir.Constant(self.i64_ty, 0), ir.Constant(self.i32_ty, 2)],
                name="rf_seek_end",
            )
            size = self.builder.call(ftell, [fp], name="rf_size")
            self.builder.call(
                fseek,
                [fp, ir.Constant(self.i64_ty, 0), ir.Constant(self.i32_ty, 0)],
                name="rf_seek_set",
            )

            size_plus = self.builder.add(size, ir.Constant(self.i64_ty, 1), name="rf_size_plus")
            buf = self.builder.call(self.malloc, [size_plus], name="rf_buf")

            self.builder.call(
                fread, [buf, ir.Constant(self.i64_ty, 1), size, fp], name="rf_fread",
            )

            end_ptr = self.builder.gep(buf, [size], name="rf_end_ptr")
            self.builder.store(ir.Constant(self.i8_ty, 0), end_ptr)

            self.builder.call(fclose, [fp], name="rf_fclose")
            self.builder.branch(end_bb)

            # Merge point: phi escolhe empty ou buf
            self.builder.position_at_end(end_bb)
            result = self.builder.phi(self.i8_ty.as_pointer(), name="rf_result")
            result.add_incoming(empty_ptr, null_bb)
            result.add_incoming(buf, ok_bb)
            return result

        return None
