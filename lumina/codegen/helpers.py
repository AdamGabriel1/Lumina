from llvmlite import ir
from .constants import CLOSURE_BLOCK_SIZE
from ..errors import LuminaError


class HelpersCodegen:

    def create_global_string(self, text):
        if not hasattr(self, 'string_counter'):
            self.string_counter = 0

        name = f"str_{self.string_counter}"
        self.string_counter += 1
        b = bytearray(text, 'utf-8') + b"\0"
        ty = ir.ArrayType(self.i8_ty, len(b))
        gv = ir.GlobalVariable(self.module, ty, name=name)
        gv.global_constant = True
        gv.initializer = ir.Constant(ty, b)
        if self.builder is None:
            return gv
        return self.builder.bitcast(gv, self.voidptr_ty)

    def to_float_if_needed(self, val):
        if val.type == self.i64_ty:
            return self.builder.sitofp(val, self.f64_ty, name="int_to_float")
        return val

    def _make_fn_wrapper(self, raw_func, name_hint):
        """Gera `i64 __wrapper(i8* env, i64 a1, ..., i64 aN)`."""
        inner_ret = raw_func.function_type.return_type
        inner_params = list(raw_func.function_type.args)
        n = len(inner_params)

        if raw_func.function_type.var_arg:
            raise LuminaError(
                message=(
                    f"Não é possível criar wrapper para função variádica "
                    f"'{raw_func.name}'. Use `&{raw_func.name}` (fn ptr cru) "
                    f"para passar à FFI."
                ),
                filename=getattr(self, 'current_filename', '<codegen>'),
                line=0, col=0, source_code='',
            )

        wrapper_param_tys = [self.voidptr_ty] + [self.i64_ty] * n
        wrapper_ty = ir.FunctionType(self.i64_ty, wrapper_param_tys)
        wrapper = ir.Function(self.module, wrapper_ty, name=f"{name_hint}__wrapper")

        entry = wrapper.append_basic_block(name="entry")
        builder = ir.IRBuilder(entry)

        call_args = []
        for i, pt in enumerate(inner_params):
            a = wrapper.args[i + 1]
            if a.type != pt:
                if pt == self.f64_ty:
                    a = builder.sitofp(a, pt, name=f"arg{i}_itof")
                elif isinstance(pt, ir.PointerType):
                    a = builder.inttoptr(a, pt, name=f"arg{i}_itop")
                elif isinstance(pt, ir.IntType) and pt.width < 64:
                    a = builder.trunc(a, pt, name=f"arg{i}_trunc")
            call_args.append(a)

        result = builder.call(raw_func, call_args)

        if inner_ret == self.void_ty:
            builder.ret(ir.Constant(self.i64_ty, 0))
        elif result.type == self.i64_ty:
            builder.ret(result)
        elif result.type == self.f64_ty:
            builder.ret(builder.fptosi(result, self.i64_ty, name="ret_ftoi"))
        elif isinstance(result.type, ir.PointerType):
            builder.ret(builder.ptrtoint(result, self.i64_ty, name="ret_ptoi"))
        elif isinstance(result.type, ir.IntType) and result.type.width < 64:
            builder.ret(builder.sext(result, self.i64_ty, name="ret_sext"))
        else:
            builder.ret(ir.Constant(self.i64_ty, 0))

        return wrapper

    # ==================================================================
    # FIX (Fase 7b): o cache `_fn_closure_blocks` foi REMOVIDO.
    #
    # Motivo: gerava IR inválido (dominance violation) quando a mesma
    # função nomeada era usada como valor em dois blocos irmãos:
    #
    #     fn sort(arr: ptr, n: int):
    #         if n <= 16:
    #             _insertion_sort(arr, n, _cmp_asc)   # block A: cria
    #         else:
    #             _quicksort_rec(arr, 0, n-1, _cmp_asc)  # block B: reusa
    #
    # `%_cmp_asc_closure = call @GC_malloc` era definido em A e reusado
    # em B — blocos irmãos não se dominam. O LLVM rejeitava o IR com
    # "Instruction does not dominate all uses!" e o clang 18 crashava.
    #
    # O cache seria seguro apenas se soubéssemos que o valor é definido
    # num bloco dominador de todos os usos — informação que o codegen
    # não tem facilmente. Alocar um bloco novo por uso custa 16 bytes e
    # é sempre correto.
    # ==================================================================
    def _wrap_fn_as_closure(self, raw_func, name_hint="fn"):
        """Retorna um bloco `{wrapper_fn, NULL}` no heap.

        Usado para (a) funções nomeadas usadas como valor e (b) lambdas
        sem captura — qualquer caso onde não há env para capturar.
        O wrapper LLVM é cacheado em `_fn_wrappers` (esse cache é
        seguro: só define a função, não cria SSA value).
        """
        key = raw_func.name
        wrapper = self._fn_wrappers.get(key)
        if wrapper is None:
            wrapper = self._make_fn_wrapper(raw_func, key)
            self._fn_wrappers[key] = wrapper

        block = self.builder.call(
            self.malloc,
            [ir.Constant(self.i64_ty, CLOSURE_BLOCK_SIZE)],
            name=f"{name_hint}_closure",
        )
        block_i8pp = self.builder.bitcast(
            block, self.voidptr_ty.as_pointer(), name=f"{name_hint}_i8pp",
        )
        fn_as_ptr = self.builder.bitcast(wrapper, self.voidptr_ty, name=f"{name_hint}_fn")
        self.builder.store(fn_as_ptr, block_i8pp)
        env_slot = self.builder.gep(
            block_i8pp, [ir.Constant(self.i64_ty, 1)],
            name=f"{name_hint}_env_slot",
        )
        self.builder.store(ir.Constant(self.voidptr_ty, None), env_slot)
        return block