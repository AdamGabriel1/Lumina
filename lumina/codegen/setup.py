"""Setup inicial: assinaturas libc/GC e globais mutáveis."""
from llvmlite import ir


class SetupMixin:

    # ==================================================================
    # Setup de funções libc/GC
    # ==================================================================
    def setup_libc_functions(self):
        printf_ty = ir.FunctionType(ir.IntType(32), [self.i8_ty.as_pointer()], var_arg=True)
        self.printf = ir.Function(self.module, printf_ty, name="printf")

        # Alocador: GC_malloc quando use_gc, malloc (libc) caso contrário.
        # Ambos têm assinatura `i8* (i64)`.
        malloc_ty = ir.FunctionType(self.i8_ty.as_pointer(), [ir.IntType(64)])
        if self.use_gc:
            self.malloc = ir.Function(self.module, malloc_ty, name="GC_malloc")

            gc_init_ty = ir.FunctionType(ir.VoidType(), [])
            self.gc_init = ir.Function(self.module, gc_init_ty, name="GC_init")

            free_ty = ir.FunctionType(ir.VoidType(), [self.i8_ty.as_pointer()])
            self.free = ir.Function(self.module, free_ty, name="GC_free")
        else:
            self.malloc = ir.Function(self.module, malloc_ty, name="malloc")

            free_ty = ir.FunctionType(ir.VoidType(), [self.i8_ty.as_pointer()])
            self.free = ir.Function(self.module, free_ty, name="free")

        strcpy_ty = ir.FunctionType(self.i8_ty.as_pointer(), [self.i8_ty.as_pointer(), self.i8_ty.as_pointer()])
        self.strcpy = ir.Function(self.module, strcpy_ty, name="strcpy")

        strcat_ty = ir.FunctionType(self.i8_ty.as_pointer(), [self.i8_ty.as_pointer(), self.i8_ty.as_pointer()])
        self.strcat = ir.Function(self.module, strcat_ty, name="strcat")

        strlen_ty = ir.FunctionType(ir.IntType(64), [self.i8_ty.as_pointer()])
        self.strlen = ir.Function(self.module, strlen_ty, name="strlen")

        snprintf_ty = ir.FunctionType(
            ir.IntType(32),
            [self.i8_ty.as_pointer(), ir.IntType(64), self.i8_ty.as_pointer()],
            var_arg=True,
        )
        self.snprintf = ir.Function(self.module, snprintf_ty, name="snprintf")

        strstr_ty = ir.FunctionType(self.i8_ty.as_pointer(), [self.i8_ty.as_pointer(), self.i8_ty.as_pointer()])
        self.strstr = ir.Function(self.module, strstr_ty, name="strstr")

        strncmp_ty = ir.FunctionType(
            ir.IntType(32),
            [self.i8_ty.as_pointer(), self.i8_ty.as_pointer(), ir.IntType(64)],
        )
        self.strncmp = ir.Function(self.module, strncmp_ty, name="strncmp")

        atoi_ty = ir.FunctionType(ir.IntType(64), [self.i8_ty.as_pointer()])
        self.atoi = ir.Function(self.module, atoi_ty, name="atoi")

        strcmp_ty = ir.FunctionType(ir.IntType(32), [self.i8_ty.as_pointer(), self.i8_ty.as_pointer()])
        self.strcmp = ir.Function(self.module, strcmp_ty, name="strcmp")

        strncpy_ty = ir.FunctionType(
            self.i8_ty.as_pointer(),
            [self.i8_ty.as_pointer(), self.i8_ty.as_pointer(), ir.IntType(64)],
        )
        self.strncpy = ir.Function(self.module, strncpy_ty, name="strncpy")

        # NOVO: FILE* globals do libc (stdin/stdout/stderr).
        # Declarados como GlobalVariable externa (sem inicializer) —
        # o linker resolve contra o libc.
        for name in ("stdin", "stdout", "stderr"):
            if name not in self.module.globals:
                gv = ir.GlobalVariable(self.module, self.voidptr_ty, name=name)
                gv.linkage = "external"

    # ==================================================================
    # Globais mutáveis (top-level `mut X = 0`)
    # ==================================================================
    def _emit_mutable_global(self, decl):
        """Emite GlobalVariable LLVM para `mut X = <expr>` no topo.

        Casos cobertos:
          - Literal (NumberExpr / BoolExpr)       → initializer LLVM direto.
          - `alloc(N)` / `alloc_bytes(N)`         → zero-init + runtime init.
          - Chamada a função do usuário            → zero-init + runtime init.
          - Anotação explícita de tipo (`mut x: T`) → zero-init + runtime init.
          - Qualquer outro caso (BinaryExpr,
            StructLiteralExpr, VariableExpr, ...)  → fallback inline (comportamento
                                                      antigo: re-avalia a cada uso).

        **Só `mut`**: `let X = ...` no topo continua inline-constante (é o
        comportamento correto — `let` de topo é uma constante de compilação,
        não uma variável global). Chamar esta função para `let` quebra
        colisão de nomes entre arquivos importados.

        **Dedup por nome**: se dois arquivos declaram `mut X`, o primeiro
        vence. Evita `DuplicatedNameError` do llvmlite.

        Runtime init é emitido no início de `main` (ver `function_body.py`),
        na ordem de declaração do AST.
        """
        from ..ast import NumberExpr, BoolExpr, CallExpr

        name = decl.name

        # Dedup: se já foi emitido como global, ignora a segunda declaração.
        if name in self.global_mut_vars:
            return

        # ---- 1. Determinar o LLVM type do slot ----
        llvm_ty = None

        if decl.var_type is not None:
            llvm_ty = self.get_llvm_type(decl.var_type)
            if isinstance(llvm_ty, ir.VoidType):
                llvm_ty = self.i64_ty

        elif isinstance(decl.value, NumberExpr):
            llvm_ty = self.f64_ty if decl.value.is_float else self.i64_ty

        elif isinstance(decl.value, BoolExpr):
            llvm_ty = ir.IntType(1)

        elif isinstance(decl.value, CallExpr):
            callee = getattr(decl.value, 'callee', None)
            cname = getattr(callee, 'name', None) or getattr(callee, 'member', None)

            if cname == "alloc":
                llvm_ty = self.i64_ty.as_pointer()
            elif cname == "alloc_bytes":
                llvm_ty = self.voidptr_ty
            else:
                fn_def = self.function_defs.get(cname)
                if fn_def is not None and fn_def.return_type != "void":
                    # Para structs, `get_llvm_param_type` devolve ponteiro,
                    # que é o que o codegen de chamada retorna.
                    llvm_ty = self.get_llvm_param_type(fn_def.return_type)
                else:
                    # Não sabemos o tipo — fallback inline.
                    self.global_var_decls[name] = decl
                    return
        else:
            # Outro tipo de expressão — fallback inline.
            self.global_var_decls[name] = decl
            return

        # ---- 2. Criar a GlobalVariable ----
        gv = ir.GlobalVariable(self.module, llvm_ty, name=f"g_{name}")
        gv.linkage = "internal"

        # ---- 3. Initializer ----
        initial = None
        if isinstance(decl.value, NumberExpr):
            if isinstance(llvm_ty, ir.DoubleType):
                initial = ir.Constant(llvm_ty, float(decl.value.value))
            elif isinstance(llvm_ty, ir.IntType):
                try:
                    initial = ir.Constant(llvm_ty, int(decl.value.value, 0))
                except (ValueError, TypeError):
                    initial = ir.Constant(llvm_ty, 0)
        elif isinstance(decl.value, BoolExpr):
            if isinstance(llvm_ty, ir.IntType):
                initial = ir.Constant(llvm_ty, 1 if decl.value.value else 0)

        if initial is not None:
            gv.initializer = initial
        else:
            if isinstance(llvm_ty, ir.PointerType):
                gv.initializer = ir.Constant(llvm_ty, None)
            elif isinstance(llvm_ty, ir.DoubleType):
                gv.initializer = ir.Constant(llvm_ty, 0.0)
            elif isinstance(llvm_ty, ir.IntType):
                gv.initializer = ir.Constant(llvm_ty, 0)
            else:
                gv.initializer = ir.Constant(llvm_ty, None)

            # Só agenda init runtime se há valor.
            if decl.value is not None:
                if not hasattr(self, '_deferred_globals'):
                    self._deferred_globals = []
                self._deferred_globals.append((gv, decl.value))

        self.global_mut_vars[name] = gv