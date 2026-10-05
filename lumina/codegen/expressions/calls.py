"""Dispatch de chamadas de função.

Responsabilidades:
  - `visit_CallExpr` — entrada do visitor
  - `codegen_user_call` — dispatcher (macros, indirect, genéricos, builtins, enum, função normal)
  - `_call_closure` — desempacota `{fn_ptr, env_ptr}` e chama
  - `_coerce_arg` / `_zero_for_type` — helpers compartilhados

Os builtins simples ficam em `builtins.py`. Os builtins de arquivo
ficam em `io_builtins.py`. Métodos e enums ficam em `methods.py`.

ABI de `fn` (a partir de 0.4.0):
  TODO valor `fn` é um fat pointer `{fn_ptr, env_ptr}` no heap.
  O `fn_ptr` tem assinatura `i64 (i8* env, i64 a1, ..., i64 aN)`.
  - Lambda com captura: env = struct com as variáveis capturadas.
  - Lambda sem captura: env = NULL.
  - Função nomeada usada como valor: wrapped em runtime com env = NULL.
  `&fn_name` devolve o fn ptr CRU (sem env) — usado em FFI.
"""
from llvmlite import ir
from ...ast import VariableExpr, MemberExpr
from ...semantic.types import unify_type


class CallsMixin:

    def _infer_enum_type_args(self, enum_def, variant_idx, arg_nodes):
        """Infere T1, T2, ... a partir dos args da chamada do construtor.

        Para `Ok(5)` em `enum Result<T, E>: Ok(T); Err(E)`: unifica
        `T` com o tipo de `5` → `T=int`. `E` fica desconhecido → default `int`.
        """
        type_params = getattr(enum_def, 'type_params', None) or []
        if not type_params:
            return []
        variant = enum_def.variants[variant_idx]
        variant_payloads = variant[1] if len(variant) > 1 else []
        if not isinstance(variant_payloads, list):
            variant_payloads = [variant_payloads] if variant_payloads else []
        type_map = {}
        for arg_node, ptype in zip(arg_nodes, variant_payloads):
            arg_type = self._infer_arg_type_lumina(arg_node)
            if arg_type:
                unify_type(ptype, arg_type, type_map)
        return [type_map.get(tp, "int") for tp in type_params]

    def visit_CallExpr(self, node):
        func_name = None
        if isinstance(node.callee, MemberExpr):
            func_name = node.callee.member
        elif isinstance(node.callee, VariableExpr):
            func_name = node.callee.name

        if node.is_method:
            return self.codegen_method_call(node, func_name)
        else:
            return self.codegen_user_call(node, func_name)

    # ==================================================================
    # Helpers de coerção
    # ==================================================================
    def _coerce_arg(self, arg_val, expected_ty, suffix=""):
        """Coage um arg para o tipo esperado.

        Usado em chamadas normais e no preenchimento de defaults.
        """
        if arg_val.type == expected_ty:
            return arg_val
        if isinstance(expected_ty, ir.PointerType) and isinstance(arg_val.type, ir.PointerType):
            return self.builder.bitcast(arg_val, expected_ty, name=f"arg_ptr_cast{suffix}")
        if expected_ty == self.i64_ty and isinstance(arg_val.type, ir.PointerType):
            return self.builder.ptrtoint(arg_val, self.i64_ty, name=f"arg_ptr_to_int{suffix}")
        if isinstance(expected_ty, ir.PointerType) and arg_val.type == self.i64_ty:
            return self.builder.inttoptr(arg_val, expected_ty, name=f"arg_int_to_ptr{suffix}")
        if expected_ty == self.f64_ty and arg_val.type == self.i64_ty:
            return self.builder.sitofp(arg_val, self.f64_ty, name=f"arg_int_to_float{suffix}")
        if expected_ty == self.i64_ty and arg_val.type == self.f64_ty:
            return self.builder.fptosi(arg_val, self.i64_ty, name=f"arg_float_to_int{suffix}")
        if isinstance(expected_ty, ir.IntType) and isinstance(arg_val.type, ir.IntType):
            if arg_val.type.width < expected_ty.width:
                if arg_val.type.width == 1:
                    return self.builder.zext(arg_val, expected_ty, name=f"arg_zext{suffix}")
                return self.builder.sext(arg_val, expected_ty, name=f"arg_sext{suffix}")
            return self.builder.trunc(arg_val, expected_ty, name=f"arg_trunc{suffix}")
        return arg_val

    def _zero_for_type(self, ty):
        """Retorna um zero constante do tipo LLVM.

        Para tipos primitivos, usa o valor 0 apropriado. Para structs
        (LiteralStructType ou IdentifiedStructType) — que em Lumina
        aparecem sempre como ponteiro — devolve null. Nunca cria
        `ir.Constant(struct_ty, 0)`, que o llvmlite aceita sem
        validar mas quebra ao imprimir com
        "TypeError: 'int' object is not iterable".
        """
        if isinstance(ty, ir.PointerType):
            return ir.Constant(ty, None)
        if isinstance(ty, ir.DoubleType):
            return ir.Constant(ty, 0.0)
        if isinstance(ty, ir.IntType):
            return ir.Constant(ty, 0)
        if isinstance(ty, (ir.LiteralStructType, ir.IdentifiedStructType)):
            # Structs são sempre por ponteiro em Lumina. Este caminho
            # só é atingido se algum caller passou o struct direto;
            # devolve null do ponteiro para não quebrar o llvmlite.
            return ir.Constant(ty.as_pointer(), None)
        return ir.Constant(ty, None)

    # ==================================================================
    # Invocação de fat pointer
    # ==================================================================
    def _call_closure(self, name, node):
        """Desempacota `{fn_ptr, env_ptr}` e chama com env como primeiro arg.

        ABI: `i64 fn(i8* env, i64 a1, ..., i64 aN)`.

        Todos os valores `fn` são fat pointers, então toda chamada indireta
        passa por aqui — inclusive funções nomeadas usadas como valor.
        """
        slot = self.symbol_table[name]
        closure_raw = self.builder.load(slot, name=f"{name}_closure")
        closure_i8pp = self.builder.bitcast(
            closure_raw, self.voidptr_ty.as_pointer(), name=f"{name}_c8pp",
        )
        fn_raw = self.builder.load(closure_i8pp, name=f"{name}_fn")
        env_slot = self.builder.gep(
            closure_i8pp, [ir.Constant(self.i64_ty, 1)], name=f"{name}_env_slot",
        )
        env_raw = self.builder.load(env_slot, name=f"{name}_env")

        n = len(node.args)
        fn_ty = ir.FunctionType(self.i64_ty, [self.voidptr_ty] + [self.i64_ty] * n)
        fn_ptr = self.builder.bitcast(fn_raw, fn_ty.as_pointer(), name=f"{name}_cast")

        call_args = [env_raw]
        for arg_node in node.args:
            a = self.visit(arg_node)
            if a.type != self.i64_ty:
                if isinstance(a.type, ir.IntType):
                    a = self.builder.sext(a, self.i64_ty, name=f"{name}_arg_sext")
                elif a.type == self.f64_ty:
                    a = self.builder.fptosi(a, self.i64_ty, name=f"{name}_arg_fptosi")
                elif isinstance(a.type, ir.PointerType):
                    a = self.builder.ptrtoint(a, self.i64_ty, name=f"{name}_arg_ptr")
            call_args.append(a)

        return self.builder.call(fn_ptr, call_args, name=f"{name}_call")

    # ==================================================================
    # Dispatcher principal
    # ==================================================================
    def codegen_user_call(self, node, func_name):
        # 0. Macro (@macro) → expande AST no call site
        if func_name in getattr(self, 'macros', {}):
            macro_fn = self.macros[func_name]
            expanded = self._expand_macro_expr(macro_fn, node.args)
            return self.visit(expanded)

        # 1. Chamada indireta via variável local.
        #
        # Como TODO valor `fn` é um fat pointer `{fn_ptr, env_ptr}`, toda
        # invocação indireta passa por `_call_closure` — que carrega os
        # dois campos e passa o env como primeiro arg. Isso funciona
        # uniformemente para:
        #   - lambda com captura (env populado)
        #   - lambda sem captura (env = NULL)
        #   - função nomeada usada como valor (env = NULL)
        #   - parâmetro `fn` recebendo qualquer um dos anteriores
        if (func_name not in self.functions_table
                and func_name not in self.builtin_functions
                and func_name in self.symbol_table):
            return self._call_closure(func_name, node)

        # 2. Chamada a função genérica → materializa cópia especializada
        gen_def = self.function_defs.get(func_name)
        if gen_def is not None and getattr(gen_def, 'type_params', None):
            type_map = self._infer_type_map_lumina(gen_def, node)

            if type_map:
                mangled = self.materialize_generic(gen_def, type_map)
                arg_vals = None
            else:
                arg_vals = [self.visit(a) for a in node.args]
                arg_types = [v.type for v in arg_vals]
                legacy_map = {}
                for p, t in zip(gen_def.params, arg_types):
                    if p.type_ann in (gen_def.type_params or []):
                        legacy_map[p.type_ann] = self._llvm_ty_to_str(t)
                mangled = self.materialize_generic(gen_def, legacy_map)

            func, func_type = self.functions_table[mangled]

            if arg_vals is None:
                arg_vals = [self.visit(a) for a in node.args]

            final_args = []
            for i, a in enumerate(arg_vals):
                expected = func_type.args[i] if i < len(func_type.args) else None
                if expected is not None and a.type != expected:
                    if isinstance(expected, ir.IntType) and isinstance(a.type, ir.IntType):
                        if a.type.width < expected.width:
                            a = self.builder.sext(a, expected, name="gen_arg_sext")
                        else:
                            a = self.builder.trunc(a, expected, name="gen_arg_trunc")
                    elif expected == self.f64_ty and a.type == self.i64_ty:
                        a = self.builder.sitofp(a, self.f64_ty, name="gen_arg_itof")
                    elif expected == self.i64_ty and a.type == self.f64_ty:
                        a = self.builder.fptosi(a, self.i64_ty, name="gen_arg_ftoi")
                    elif isinstance(expected, ir.PointerType) and a.type == self.i64_ty:
                        a = self.builder.inttoptr(a, expected, name="gen_arg_itop")
                    elif expected == self.i64_ty and isinstance(a.type, ir.PointerType):
                        a = self.builder.ptrtoint(a, self.i64_ty, name="gen_arg_ptoi")
                    elif isinstance(expected, ir.PointerType) and isinstance(a.type, ir.PointerType):
                        a = self.builder.bitcast(a, expected, name="gen_arg_bitcast")
                final_args.append(a)

            return self.builder.call(func, final_args, name=mangled + "_call")

        # 3. Builtins simples (print, len, alloc, chr, atoi, getchar, ...)
        result = self._call_builtin_impl(func_name, node)
        if result is not None:
            return result

        # 3b. Builtins de arquivo (write_file, read_file)
        result = self._call_io_builtin(func_name, node)
        if result is not None:
            return result

        # 4. Construtor de enum
        enum_name = None
        variant_idx = None

        STANDARD_VARIANTS = {
            "Ok": ("Result", 0),
            "Err": ("Result", 1),
            "Some": ("Option", 0),
            "None": ("Option", 1),
        }
        if func_name in STANDARD_VARIANTS:
            candidate_name, candidate_idx = STANDARD_VARIANTS[func_name]
            if candidate_name in self.struct_types:
                enum_name, variant_idx = candidate_name, candidate_idx

        if enum_name is None:
            lookup = self._find_enum_variant(func_name)
            if lookup is not None:
                enum_name, variant_idx = lookup

        if enum_name is not None:
            enum_def = self.struct_defs.get(enum_name)
            type_params = getattr(enum_def, 'type_params', None) or []
            if type_params:
                args = self._infer_enum_type_args(enum_def, variant_idx, node.args)
                concrete_name = f"{enum_name}<{','.join(args)}>"
                return self._construct_enum(concrete_name, variant_idx, node.args)
            return self._construct_enum(enum_name, variant_idx, node.args)

        # 4.5 Alias de método (trait default)
        if func_name in getattr(self, 'alias_methods', set()):
            entry = self.functions_table[func_name]
            if isinstance(entry, tuple):
                func, func_type = entry
                self_ptr = self.symbol_table.get('self')
                if self_ptr is not None and len(func_type.args) >= 1:
                    self_val = self.builder.load(self_ptr, name="self_load")
                    args = [self_val]
                    for arg_node in node.args:
                        args.append(self.visit(arg_node))
                    final_args = []
                    for i, a in enumerate(args):
                        expected = func_type.args[i] if i < len(func_type.args) else None
                        if expected is not None and a.type != expected:
                            a = self._coerce_arg(a, expected, suffix=f"_alias_{i}")
                        final_args.append(a)
                    return self.builder.call(func, final_args, name=func_name + "_alias_call")

        # 5. Função normal
        if func_name in self.functions_table:
            func, func_type = self.functions_table[func_name]
            args = []
            arg_list = node.args
            if node.is_method and len(arg_list) > len(func_type.args):
                arg_list = arg_list[1:]

            for i, arg_node in enumerate(arg_list):
                arg_val = self.visit(arg_node)
                if isinstance(arg_val.type, ir.ArrayType):
                    arg_val = self.builder.bitcast(
                        arg_val, self.voidptr_ty, name="array_decay",
                    )
                if i >= len(func_type.args):
                    args.append(arg_val)
                    continue
                expected_ty = func_type.args[i]
                arg_val = self._coerce_arg(arg_val, expected_ty)
                args.append(arg_val)

            fn_def = self.function_defs.get(func_name)
            if fn_def is not None and len(args) < len(func_type.args):
                for i in range(len(args), len(func_type.args)):
                    expected_ty = func_type.args[i]
                    param = fn_def.params[i] if i < len(fn_def.params) else None
                    if param is not None and getattr(param, 'default', None) is not None:
                        default_val = self.visit(param.default)
                        default_val = self._coerce_arg(
                            default_val, expected_ty, suffix="_def",
                        )
                        args.append(default_val)
                    else:
                        args.append(self._zero_for_type(expected_ty))

            return self.builder.call(func, args, name=func_name + "_call")

        # Fallback
        return ir.Constant(self.i64_ty, 0)