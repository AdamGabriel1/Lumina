from llvmlite import ir
from ...ast import (
    NumberExpr, BoolExpr, StringExpr, InterpolatedStringExpr, ComptimeExpr,
    NoneExpr, NilExpr,
)


class LiteralsMixin:

    # ==================================================================
    # FIX (Fase 10d): `visit_NumberExpr` refatorado corretamente.
    #
    # A versão anterior tentava `int(v)` como fallback universal, mas
    # `int("3.14")` levanta `ValueError` (Python não trunca strings com
    # ponto). O `except ValueError: ival = 0` fazia todo float virar
    # `0.0` — 12 testes regrediram.
    #
    # Agora:
    #   - `is_float` checado PRIMEIRO → usa `float(v)` (aceita "3.14").
    #   - Inteiros: `int(v, base)` com a base correta do prefixo.
    # ==================================================================
    def visit_NumberExpr(self, node):
        v = node.value

        # Float: `float("3.14")` funciona para todos os formatos
        # aceitos pelo lexer (dígitos, ponto, expoente). Sem prefixo
        # hex/bin/oct em float.
        if node.is_float:
            return ir.Constant(self.f64_ty, float(v))

        # Inteiro: base depende do prefixo.
        if v.startswith(('0x', '0X')):
            return ir.Constant(self.i64_ty, int(v, 16))
        if v.startswith(('0b', '0B')):
            return ir.Constant(self.i64_ty, int(v, 2))
        if v.startswith(('0o', '0O')):
            return ir.Constant(self.i64_ty, int(v, 8))

        # Decimal puro.
        return ir.Constant(self.i64_ty, int(v))

    def visit_BoolExpr(self, node):
        return ir.Constant(ir.IntType(1), 1 if node.value else 0)

    def visit_StringExpr(self, node):
        return self.create_global_string(node.value)

    def visit_NoneExpr(self, node):
        """Constrói Option::None (tag=1, sem payload)."""
        if "Option" in self.struct_types:
            return self._construct_enum("Option", 1, [])
        return ir.Constant(self.i64_ty, 0)

    def visit_NilExpr(self, node):
        """`nil` produz um null pointer (i8* null)."""
        return ir.Constant(self.voidptr_ty, None)

    def visit_InterpolatedStringExpr(self, node):
        return self.codegen_fstring(node.parts)

    def codegen_fstring(self, elements):
        """Compila `$"..."` como concatenação dinâmica, sem buffer fixo."""
        i8_ptr = self.i8_ty.as_pointer()

        parts = []
        for i, el in enumerate(elements):
            if isinstance(el, StringExpr):
                sv = self.create_global_string(el.value)
                parts.append((sv, f"str_{i}"))
                continue

            v = self.visit(el)

            if isinstance(v.type, ir.PointerType):
                sv = self.builder.bitcast(v, i8_ptr, name=f"fstr_str_cast_{i}")
                parts.append((sv, f"var_{i}"))
                continue

            num_buf = self._fn_emit_alloca(
                f"fstr_num_buf_{i}",
                ir.ArrayType(self.i8_ty, 32),
            )
            num_buf_i8 = self.builder.bitcast(
                num_buf, i8_ptr, name=f"fstr_num_i8_{i}"
            )
            if isinstance(v.type, ir.DoubleType):
                fmt = self.create_global_string("%f")
            else:
                fmt = self.create_global_string("%ld")
            self.builder.call(
                self.snprintf,
                [num_buf_i8, ir.Constant(self.i64_ty, 32), fmt, v],
                name=f"fstr_snprintf_{i}",
            )
            parts.append((num_buf_i8, f"num_{i}"))

        total = ir.Constant(self.i64_ty, 1)
        for sv, label in parts:
            ln = self.builder.call(self.strlen, [sv], name=f"fstr_len_{label}")
            total = self.builder.add(total, ln, name=f"fstr_total_{label}")

        buf_raw = self.builder.call(self.malloc, [total], name="fstr_buf")
        buf = self.builder.bitcast(buf_raw, i8_ptr, name="fstr_buf_i8")

        if not parts:
            self.builder.store(ir.Constant(self.i8_ty, 0), buf)
        else:
            self.builder.call(self.strcpy, [buf, parts[0][0]], name="fstr_first")
            for sv, label in parts[1:]:
                self.builder.call(self.strcat, [buf, sv], name=f"fstr_cat_{label}")

        return buf

    def visit_ComptimeExpr(self, node):
        if getattr(node, 'folded', None) is not None:
            return self.visit(node.folded)
        return self.visit(node.expr)